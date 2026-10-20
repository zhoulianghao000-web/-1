"""侧边栏主窗口（PRD §6 全局窗口约束）。

窗口 flags：无边框 / Tool / 置顶 / **不抢焦点**。
位置与 Z 序由后端 services/docker.py 接管，前端不调用 move/resize。
"""
from __future__ import annotations

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtWidgets import QStackedWidget, QVBoxLayout, QWidget

from api_client import ApiClient, ApiWorker
from views.connect_view import ConnectView

VIEW_CONNECT = 'connect'
VIEW_MAIN = 'main'


class SidebarWindow(QWidget):
    main_requested = Signal()

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
        self._worker: ApiWorker | None = None

        self.stack = QStackedWidget()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.stack)

        self.connect_view = ConnectView()
        self.connect_view.retry_clicked.connect(self.refresh_status)
        self.connect_view.continue_clicked.connect(self.main_requested.emit)
        self.stack.addWidget(self.connect_view)

        # 停留在 V0 时每 3 秒轮询一次 status（PRD §3 V0）
        self._timer = QTimer(self)
        self._timer.setInterval(3000)
        self._timer.timeout.connect(lambda: self.refresh_status(auto=True))

        self.refresh_status()

    # ---------------- 状态请求 ----------------
    def refresh_status(self, *, auto: bool = False) -> None:
        """auto=True 为定时轮询：保留现有错误文案，避免每 3 秒闪回"正在连接"。"""
        if not auto:
            self.connect_view.show_loading()
        self._timer.start()
        self._run(lambda: self.client.status(), self._on_status)

    def _run(self, fn, slot) -> None:
        if self._worker is not None and self._worker.isRunning():
            return
        self._worker = ApiWorker(fn, self)
        self._worker.result.connect(slot)
        self._worker.finished.connect(self._clear_worker)
        self._worker.start()

    def _clear_worker(self) -> None:
        self._worker = None

    def _on_status(self, res: dict) -> None:
        if not res.get('ok'):
            self.connect_view.show_error(res.get('message') or '未知错误')
            return
        data = res['data'] or {}
        self.connect_view.show_status(data)
        # PRD §4：全绿时自动进入主页面
        if data.get('mode') == 'wxauto' and data.get('wechat_running'):
            self._timer.stop()
            self.main_requested.emit()
