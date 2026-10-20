"""侧边栏主窗口（PRD §6 全局窗口约束）。

窗口 flags：无边框 / Tool / 置顶 / **不抢焦点**。
未贴边时默认停靠在**屏幕右侧垂直居中**，可用鼠标按住空白处拖动（无边框窗口必须自己实现拖动）。
贴边开启后位置与 Z 序交由后端 services/docker.py 接管，前端不调用 move/resize。
所有网络请求走子线程，结果通过 Signal 回主线程（CLAUDE.md §7.4）。
WS 用 PySide6 自带 QWebSocket，不引入新依赖。
"""
from __future__ import annotations

import json

from PySide6.QtCore import Qt, QTimer, QUrl
from PySide6.QtGui import QGuiApplication
from PySide6.QtWebSockets import QWebSocket
from PySide6.QtWidgets import QStackedWidget, QVBoxLayout, QWidget

from api_client import ApiClient, ApiWorker
from views.connect_view import ConnectView
from views.main_view import MainView

VIEW_CONNECT = 'connect'
VIEW_MAIN = 'main'

# PRD §5 错误码 → 用户可读文案（不出现堆栈）
ERR_TEXT = {
    1000: '目标 IM 不可用，请启动 QQ 后重试',
    1001: '读取消息失败：确认 QQ 窗口已打开、缩放 100%',
    2001: '请先选择一个会话',
    3001: '大模型调用失败',
    5000: '操作失败',
}


class SidebarWindow(QWidget):
    def __init__(self, width: int = 380, height: int = 760):
        super().__init__()
        self.setObjectName('sidebarWindow')
        self.setWindowTitle('WeChat Sidebar')
        self.setFixedWidth(width)
        self.resize(width, height)
        self.setWindowFlags(
            Qt.FramelessWindowHint
            | Qt.Tool
            | Qt.WindowStaysOnTopHint
            | Qt.WindowDoesNotAcceptFocus
        )

        self.client = ApiClient()
        self._workers: list[ApiWorker] = []
        self._last_status: dict = {}
        self.current: str | None = None
        self._placed = False  # 首次显示时定一次默认位置，之后不抢位置
        self._drag_pos = None
        self._accept_focus = False  # 当前窗口 flags 是否允许拿到键盘焦点

        self.stack = QStackedWidget()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.stack)

        # ---- V0 ----
        self.connect_view = ConnectView()
        self.connect_view.retry_clicked.connect(lambda: self.refresh_status(auto=False))
        self.connect_view.continue_clicked.connect(self.show_main)
        self.stack.addWidget(self.connect_view)

        # ---- V1 ----
        self.main_view = MainView()
        self.main_view.refresh_sessions_clicked.connect(self.load_sessions)
        self.main_view.session_selected.connect(self.on_session_selected)
        self.main_view.generate_clicked.connect(self.on_generate)
        self.main_view.fill_clicked.connect(self.on_fill)
        self.main_view.send_clicked.connect(self.on_send)
        self.main_view.dock_toggled.connect(self.on_dock_toggle)
        self.main_view.listen_toggled.connect(self.on_listen_toggle)
        self.stack.addWidget(self.main_view)

        # 停留在 V0 时每 3 秒轮询一次 status（PRD §3 V0）
        self._timer = QTimer(self)
        self._timer.setInterval(3000)
        self._timer.timeout.connect(lambda: self.refresh_status(auto=True))

        # ---- WS（监听开启时才连接）----
        self._ws: QWebSocket | None = None
        self._ws_attempts = 0
        self._ws_timer = QTimer(self)
        self._ws_timer.setInterval(5000)
        self._ws_timer.timeout.connect(self._ws_retry)

        self.refresh_status(auto=False)

    # ---------------- 视图切换 ----------------
    def show_main(self) -> None:
        self._timer.stop()
        self.stack.setCurrentWidget(self.main_view)
        if self._last_status:
            self.main_view.set_status(self._last_status)
        self.load_sessions()

    # ---------------- 默认位置与拖动 ----------------
    def showEvent(self, e) -> None:
        super().showEvent(e)
        if not self._placed:
            self._placed = True
            g = QGuiApplication.primaryScreen().availableGeometry()
            # 屏幕右侧垂直居中：不贴边也不挡在屏幕中间
            self.move(g.right() - self.width() - 24, g.top() + (g.height() - self.height()) // 2)

    def mousePressEvent(self, e) -> None:
        if e.button() == Qt.LeftButton:
            self._drag_pos = e.globalPosition().toPoint() - self.frameGeometry().topLeft()
        super().mousePressEvent(e)

    def mouseMoveEvent(self, e) -> None:
        if self._drag_pos is not None and (e.buttons() & Qt.LeftButton):
            self.move(e.globalPosition().toPoint() - self._drag_pos)
        super().mouseMoveEvent(e)

    def mouseReleaseEvent(self, e) -> None:
        self._drag_pos = None
        super().mouseReleaseEvent(e)

    def _set_accept_focus(self, on: bool) -> None:
        """按 Adapter 决定是否允许侧边栏拿到键盘焦点。

        - wxauto（微信 3.9）：**必须不抢焦点**，否则点击侧边栏会让微信输入框失焦、SendKeys 打空
        - QQ 半自动：**必须能拿焦点**，否则"补充要求"填不进去、生成的回复改不了
          （适配器自己会激活 QQ 窗口粘贴，不依赖"QQ 一直持焦点"）
        """
        if self._accept_focus == on:
            return
        self._accept_focus = on
        flags = self.windowFlags()
        flags = (flags & ~Qt.WindowDoesNotAcceptFocus) if on else (flags | Qt.WindowDoesNotAcceptFocus)
        pos = self.pos()
        self.setWindowFlags(flags)  # 改 flags 后必须重新 show，位置会被重置
        self.show()
        self.move(pos)

    # ---------------- 通用：子线程跑请求 ----------------
    def _spawn(self, fn, slot) -> None:
        w = ApiWorker(fn, self)
        w.result.connect(slot)
        w.finished.connect(lambda: self._drop(w))
        self._workers.append(w)
        w.start()

    def _drop(self, w: ApiWorker) -> None:
        if w in self._workers:
            self._workers.remove(w)

    def _fail(self, res: dict) -> str:
        code = res.get('code')
        text = ERR_TEXT.get(code, res.get('message') or '未知错误')
        return f'{text}（{code}）' if code else text

    # ---------------- status ----------------
    def refresh_status(self, *, auto: bool = False) -> None:
        """auto=True 为定时轮询：保留现有错误文案，避免每 3 秒闪回"正在连接"。"""
        if not auto:
            self.connect_view.show_loading()
        self._timer.start()
        self._spawn(lambda: self.client.status(), self._on_status)

    def _on_status(self, res: dict) -> None:
        if not res.get('ok'):
            if self.stack.currentWidget() is self.main_view:
                self.main_view.toast(self._fail(res), 'error')
            else:
                self.connect_view.show_error(self._fail(res))
            return
        data = res['data'] or {}
        self._last_status = data
        self._set_accept_focus(data.get('mode') == 'qq')
        self.connect_view.show_status(data)
        if self.stack.currentWidget() is self.main_view:
            self.main_view.set_status(data)
        # PRD §4：全绿时自动进入主页面（qq 半自动模式窗口已找到也算就绪）
        if data.get('mode') in ('wxauto', 'qq') and data.get('wechat_running'):
            self.show_main()

    # ---------------- sessions ----------------
    def load_sessions(self) -> None:
        self.main_view.show_sessions_loading()
        self._spawn(lambda: self.client.sessions(), self._on_sessions)

    def _on_sessions(self, res: dict) -> None:
        if not res.get('ok'):
            self.main_view.toast(self._fail(res), 'error')
            self.main_view.set_sessions([])
            return
        sessions = (res['data'] or {}).get('sessions') or []
        self.main_view.set_sessions(sessions)
        who = self._last_status.get('current') or (sessions[0].get('name') if sessions else None)
        if who:
            self.main_view.select_session(who)
            self.load_messages(who)

    def on_session_selected(self, who: str) -> None:
        if not who or who == self.current:
            return
        self.load_messages(who)

    # ---------------- messages ----------------
    def load_messages(self, who: str) -> None:
        self.current = who
        self.main_view.show_messages_loading()
        self._spawn(lambda: self.client.messages(who=who, limit=60), self._on_messages)

    def _on_messages(self, res: dict) -> None:
        if not res.get('ok'):
            self.main_view.toast(self._fail(res), 'error')
            self.main_view.show_messages_empty()
            return
        data = res['data'] or {}
        msgs = data.get('messages') or []
        if not msgs and self._last_status.get('mode') == 'qq':
            # QQ 读不到消息流，空态要告诉人下一步怎么操作，而不是干巴巴一句"暂无消息"
            self.main_view.show_messages_empty('在 QQ 里选中对方的话按 Ctrl+C，再点"会话"右侧 ↻ 刷新')
            return
        self.main_view.set_messages(msgs)

    # ---------------- 生成建议回复（PRD §3.6 C）----------------
    def on_generate(self) -> None:
        who = self.current
        if not who:
            self.main_view.toast(ERR_TEXT[2001], 'error')
            return
        self.main_view.set_generating(True)
        instruction = self.main_view.instruction()
        self._spawn(lambda: self.client.reply(who, instruction), self._on_reply)

    def _on_reply(self, res: dict) -> None:
        self.main_view.set_generating(False)
        if not res.get('ok'):
            self.main_view.toast(self._fail(res), 'error')
            return
        d = res['data'] or {}
        self.main_view.set_reply(d.get('reply') or '', d.get('source') or '')
        if d.get('degraded'):
            self.main_view.toast('模型失败，已用规则兜底（仍可发送）', 'warn')

    # ---------------- 填入 / 发送（PRD §3.6 D / E）----------------
    def on_fill(self) -> None:
        who, text = self._ready_to_send()
        if not (who and text):
            return
        self.main_view.set_sending(True)
        self._spawn(lambda: self.client.fill(who, text), lambda r: self._on_sent(r, '已粘贴到 QQ 输入框', refresh=False))

    def on_send(self) -> None:
        who, text = self._ready_to_send()
        if not (who and text):
            return
        self.main_view.set_sending(True)
        self._spawn(lambda: self.client.send(who, text), lambda r: self._on_sent(r, '已发送', refresh=True))

    def _ready_to_send(self) -> tuple[str | None, str]:
        text = self.main_view.reply_text()
        if not text:
            return None, ''
        who = self.current
        if not who:
            self.main_view.toast(ERR_TEXT[2001], 'error')
            return None, text
        return who, text

    def _on_sent(self, res: dict, verb: str, refresh: bool) -> None:
        self.main_view.set_sending(False)
        if not res.get('ok'):
            self.main_view.toast(self._fail(res), 'error')
            return
        d = res['data'] or {}
        if d.get('duplicated'):
            self.main_view.toast('已发送（忽略重复点击）', 'warn')
        else:
            self.main_view.toast(verb, 'ok')
        if refresh:
            QTimer.singleShot(800, self._reload_current)

    def _reload_current(self) -> None:
        if self.current:
            self.load_messages(self.current)

    # ---------------- 贴边 / 监听开关（PRD §3.6 F / G）----------------
    def on_dock_toggle(self, on: bool) -> None:
        self._spawn(lambda: self.client.dock(on, 380), lambda r: self._on_dock(r, on))

    def _on_dock(self, res: dict, on: bool) -> None:
        if not res.get('ok'):
            self.main_view.set_docking(not on)  # 回滚按钮态
            self.main_view.toast(self._fail(res), 'error')
            return
        d = res['data'] or {}
        self.main_view.set_docking(bool(d.get('docking')))
        if d.get('error'):
            self.main_view.toast(f'贴边异常：{d["error"]}', 'warn')
        else:
            self.main_view.toast('贴边已开启' if d.get('docking') else '贴边已关闭', 'ok')

    def on_listen_toggle(self, on: bool) -> None:
        self._spawn(lambda: self.client.listen(on), lambda r: self._on_listen(r, on))

    def _on_listen(self, res: dict, on: bool) -> None:
        if not res.get('ok'):
            self.main_view.set_listen(not on)  # 回滚按钮态
            self.main_view.toast(self._fail(res), 'error')
            return
        listen = bool((res['data'] or {}).get('listen'))
        self.main_view.set_listen(listen)
        if listen:
            self.main_view.toast('实时监听已开启', 'ok')
            self._ws_connect()
        else:
            self.main_view.toast('实时监听已关闭', 'ok')
            self._ws_close()

    # ---------------- WS 推送（PRD §3.6 G）----------------
    def _ws_url(self) -> QUrl:
        port = self.client.base.rsplit(':', 1)[-1]
        return QUrl(f'ws://127.0.0.1:{port}/ws/messages')

    def _ws_connect(self) -> None:
        self._ws_close()
        self._ws_attempts = 0
        self._ws = QWebSocket()
        self._ws.textMessageReceived.connect(self._on_ws_text)
        self._ws.disconnected.connect(self._ws_disconnected)
        self._ws.open(self._ws_url())

    def _ws_disconnected(self) -> None:
        # 自动重连：5 秒间隔，最多 3 次（PRD §3.6 G）
        if self.main_view.is_listening() and self._ws_attempts < 3:
            self._ws_attempts += 1
            self._ws_timer.start()

    def _ws_retry(self) -> None:
        self._ws_timer.stop()
        if self.main_view.is_listening() and self._ws is not None:
            self._ws.open(self._ws_url())

    def _ws_close(self) -> None:
        self._ws_timer.stop()
        if self._ws is not None:
            try:
                self._ws.textMessageReceived.disconnect(self._on_ws_text)
                self._ws.disconnected.disconnect(self._ws_disconnected)
            except Exception:
                pass
            self._ws.close()
            self._ws.deleteLater()
            self._ws = None

    def _on_ws_text(self, text: str) -> None:
        try:
            payload = json.loads(text)
        except Exception:
            return
        if payload.get('type') != 'new':
            return
        data = payload.get('data') or {}
        for chat, msgs in data.items():
            if chat == self.current:
                self.main_view.append_messages(msgs)
            else:
                self.main_view.mark_new(chat)
