"""V1.main — 主功能页（PRD §3）。

分区：顶部状态条 / 会话区 / 消息区 / 回复区 / 开关区 / toast。
本文件只负责"渲染与交互约定"，所有数据由 window.py 通过 set_* 方法灌入。
"""
from __future__ import annotations

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QTextEdit,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from theme import BRAND, BRAND_DARK, ERROR, LINE, PANEL, SUB, TEXT, WARN

TYPE_SYS = ('sys', 'time', 'recall')


class MainView(QWidget):
    # 交互信号（由 window.py 接线，PRD §3.6）
    generate_clicked = Signal()
    fill_clicked = Signal()
    send_clicked = Signal()
    dock_toggled = Signal(bool)
    listen_toggled = Signal(bool)
    refresh_sessions_clicked = Signal()
    session_selected = Signal(str)
    close_clicked = Signal()
    settings_clicked = Signal()
    quick_clicked = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName('mainView')
        self._docking = False
        self._listen = False
        # setItemWidget 不会持有 Python 引用，必须在实例上保留，否则控件被 GC 掉
        self._bubbles: list[QWidget] = []

        # ---------- 顶部状态条 ----------
        self.lblNickname = QLabel('微信侧边栏')
        self.lblNickname.setObjectName('lblNickname')
        self.lblNickname.setStyleSheet(f'font-size: 14px; font-weight: 600; color: {TEXT};')

        self.lblMode = QLabel('演示数据')
        self.lblMode.setObjectName('lblMode')
        self.lblMode.setStyleSheet(f'color: {WARN}; font-size: 11px;')

        self.btnSettings = QToolButton()
        self.btnSettings.setObjectName('btnSettings')
        self.btnSettings.setText('⚙')
        self.btnSettings.setToolTip('设置：API Key / 模型 / 窗口宽度 / 适配器')
        self.btnSettings.clicked.connect(self.settings_clicked.emit)

        self.btnQuick = QToolButton()
        self.btnQuick.setObjectName('btnQuick')
        self.btnQuick.setText('💬')
        self.btnQuick.setToolTip('话术库：点一条插入回复框')
        self.btnQuick.clicked.connect(self.quick_clicked.emit)

        self.btnClose = QToolButton()
        self.btnClose.setObjectName('btnClose')
        self.btnClose.setText('✕')
        self.btnClose.setToolTip('关闭侧边栏（退出应用）')
        self.btnClose.clicked.connect(self.close_clicked.emit)

        top = QHBoxLayout()
        top.addWidget(self.lblNickname)
        top.addWidget(self.lblMode)
        top.addStretch(1)
        top.addWidget(self.btnQuick)
        top.addWidget(self.btnSettings)
        top.addWidget(self.btnClose)

        self.bannerNotice = QLabel('')
        self.bannerNotice.setObjectName('bannerNotice')
        self.bannerNotice.setWordWrap(True)
        self.bannerNotice.setStyleSheet(
            f'background: {PANEL}; color: {WARN}; border: 1px solid {LINE}; '
            f'border-radius: 6px; padding: 6px; font-size: 11px;'
        )
        self.bannerNotice.hide()

        # ---------- 会话区 ----------
        self.lblSessionTitle = QLabel('会话')
        self.lblSessionTitle.setStyleSheet(f'color: {SUB}; font-size: 11px;')

        self.btnRefreshSession = QToolButton()
        self.btnRefreshSession.setObjectName('btnRefreshSession')
        self.btnRefreshSession.setText('↻')
        self.btnRefreshSession.clicked.connect(self.refresh_sessions_clicked.emit)

        head_session = QHBoxLayout()
        head_session.addWidget(self.lblSessionTitle)
        head_session.addStretch(1)
        head_session.addWidget(self.btnRefreshSession)

        self.listSessions = QListWidget()
        self.listSessions.setObjectName('listSessions')
        self.listSessions.setFixedHeight(128)
        self.listSessions.setStyleSheet(
            f'QListWidget {{ background: {PANEL}; border: 1px solid {LINE}; border-radius: 8px; }}'
            f'QListWidget::item {{ padding: 6px 8px; }}'
            f'QListWidget::item:selected {{ background: {BRAND_DARK}; color: #ffffff; }}'
        )
        self.listSessions.itemClicked.connect(
            lambda item: self.session_selected.emit(item.data(Qt.UserRole) or '')
        )
        self.listSessions.itemSelectionChanged.connect(self._sync_selection_newno)

        self.lblSessionEmpty = QLabel('暂无会话')
        self.lblSessionEmpty.setObjectName('lblSessionEmpty')
        self.lblSessionEmpty.setStyleSheet(f'color: {SUB}; font-size: 12px;')
        self.lblSessionEmpty.setAlignment(Qt.AlignCenter)
        self.lblSessionEmpty.hide()

        # ---------- 消息区 ----------
        self.listMessages = QListWidget()
        self.listMessages.setObjectName('listMessages')
        self.listMessages.setStyleSheet(
            f'QListWidget {{ background: transparent; border: none; }} QListWidget::item {{ border: none; }}'
        )
        self.listMessages.setSpacing(2)

        self.lblMsgEmpty = QLabel('暂无消息')
        self.lblMsgEmpty.setObjectName('lblMsgEmpty')
        self.lblMsgEmpty.setStyleSheet(f'color: {SUB}; font-size: 12px;')
        self.lblMsgEmpty.setAlignment(Qt.AlignCenter)
        self.lblMsgEmpty.hide()

        self.lblMsgLoading = QLabel('加载中…')
        self.lblMsgLoading.setObjectName('lblMsgLoading')
        self.lblMsgLoading.setStyleSheet(f'color: {SUB}; font-size: 12px;')
        self.lblMsgLoading.setAlignment(Qt.AlignCenter)
        self.lblMsgLoading.hide()

        # ---------- 回复区 ----------
        self.inputInstruction = QLineEdit()
        self.inputInstruction.setObjectName('inputInstruction')
        self.inputInstruction.setPlaceholderText('补充要求（可留空）：如 委婉拒绝')

        self.btnGenerate = QPushButton('生成回复')
        self.btnGenerate.setObjectName('btnGenerate')
        self.btnGenerate.setProperty('primary', True)
        self.btnGenerate.clicked.connect(self.generate_clicked.emit)

        row_inst = QHBoxLayout()
        row_inst.addWidget(self.inputInstruction)
        row_inst.addWidget(self.btnGenerate)

        self.editReply = QTextEdit()
        self.editReply.setObjectName('editReply')
        self.editReply.setPlaceholderText('点【生成回复】，结果会在这里，可手动改')
        self.editReply.setFixedHeight(90)
        self.editReply.textChanged.connect(self._sync_send_enabled)

        self.lblSource = QLabel('')
        self.lblSource.setObjectName('lblSource')
        self.lblSource.setStyleSheet(f'color: {SUB}; font-size: 11px;')

        self.btnFill = QPushButton('填入')
        self.btnFill.setObjectName('btnFill')
        self.btnFill.clicked.connect(self.fill_clicked.emit)

        self.btnSend = QPushButton('发送')
        self.btnSend.setObjectName('btnSend')
        self.btnSend.setProperty('primary', True)
        self.btnSend.clicked.connect(self.send_clicked.emit)

        row_send = QHBoxLayout()
        row_send.addWidget(self.btnFill)
        row_send.addWidget(self.btnSend)
        row_send.addStretch(1)

        # ---------- 开关区 ----------
        self.btnDock = QPushButton('贴边（关）')
        self.btnDock.setObjectName('btnDock')
        self.btnDock.setCheckable(True)
        self.btnDock.clicked.connect(lambda: self.dock_toggled.emit(self.btnDock.isChecked()))

        self.btnListen = QPushButton('实时监听（关）')
        self.btnListen.setObjectName('btnListen')
        self.btnListen.setCheckable(True)
        self.btnListen.clicked.connect(lambda: self.listen_toggled.emit(self.btnListen.isChecked()))

        row_sw = QHBoxLayout()
        row_sw.addWidget(self.btnDock)
        row_sw.addWidget(self.btnListen)
        row_sw.addStretch(1)

        self.lblToast = QLabel('')
        self.lblToast.setObjectName('lblToast')
        self.lblToast.setAlignment(Qt.AlignCenter)
        self.lblToast.setWordWrap(True)
        self.lblToast.hide()

        root = QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(8)
        root.addLayout(top)
        root.addWidget(self.bannerNotice)
        root.addLayout(head_session)
        root.addWidget(self.listSessions)
        root.addWidget(self.lblSessionEmpty)
        root.addWidget(self.listMessages, 1)
        root.addWidget(self.lblMsgEmpty)
        root.addWidget(self.lblMsgLoading)
        root.addLayout(row_inst)
        root.addWidget(self.editReply)
        root.addWidget(self.lblSource)
        root.addLayout(row_send)
        root.addLayout(row_sw)
        root.addWidget(self.lblToast)

        self._sync_send_enabled()

    # ---------------- 状态条 ----------------
    def set_status(self, data: dict) -> None:
        mode = data.get('mode')
        self.lblNickname.setText(data.get('nickname') or '微信侧边栏')
        if mode == 'qq':
            self.lblMode.setText('QQ 半自动')
            self.lblMode.setStyleSheet(f'color: {BRAND}; font-size: 11px;')
        elif mode == 'wxauto':
            self.lblMode.setText('已连微信')
            self.lblMode.setStyleSheet(f'color: {BRAND}; font-size: 11px;')
        else:
            self.lblMode.setText('演示数据')
            self.lblMode.setStyleSheet(f'color: {WARN}; font-size: 11px;')

        detail = data.get('detail') or ''
        notice = ('' if (mode == 'wxauto' and data.get('wechat_running')) else detail)
        self.bannerNotice.setText(notice)
        self.bannerNotice.setVisible(bool(notice))

        self._docking = bool(data.get('docking'))
        self._listen = bool(data.get('listen'))
        self.btnDock.setChecked(self._docking)
        self.btnDock.setText(f'贴边（{"开" if self._docking else "关"}）')
        self.btnListen.setChecked(self._listen)
        self.btnListen.setText(f'实时监听（{"开" if self._listen else "关"}）')

    def set_docking(self, on: bool) -> None:
        self._docking = on
        self.btnDock.setChecked(on)
        self.btnDock.setText(f'贴边（{"开" if on else "关"}）')

    def set_listen(self, on: bool) -> None:
        self._listen = on
        self.btnListen.setChecked(on)
        self.btnListen.setText(f'实时监听（{"开" if on else "关"}）')

    def is_listening(self) -> bool:
        return self._listen

    def mark_new(self, chat: str) -> None:
        """非当前会话来新消息：给会话 chip 加红点（PRD §3.6 G）。"""
        for i in range(self.listSessions.count()):
            item = self.listSessions.item(i)
            if item.data(Qt.UserRole) == chat and '🔴' not in item.text():
                item.setText(f'{item.data(Qt.UserRole)} 🔴')
                return

    # ---------------- 会话区 ----------------
    def show_sessions_loading(self) -> None:
        self.lblSessionEmpty.setText('加载中…')
        self.lblSessionEmpty.show()

    def set_sessions(self, sessions: list) -> None:
        self.listSessions.clear()
        if not sessions:
            self.lblSessionEmpty.setText('暂无会话')
            self.lblSessionEmpty.show()
            return
        self.lblSessionEmpty.hide()
        for s in sessions:
            name = s.get('name') or '(未知会话)'
            mark = ' 🔴' if s.get('isnew') else ''
            item = QListWidgetItem(name + mark)
            item.setData(Qt.UserRole, s.get('name') or '')
            tip = f'{s.get("time") or ""} {s.get("content") or ""}'.strip()
            item.setToolTip(tip or name)
            self.listSessions.addItem(item)

    def select_session(self, who: str) -> None:
        for i in range(self.listSessions.count()):
            item = self.listSessions.item(i)
            if item.data(Qt.UserRole) == who:
                self.listSessions.setCurrentItem(item)
                return

    # ---------------- 消息区 ----------------
    def show_messages_loading(self) -> None:
        self.listMessages.hide()
        self.lblMsgEmpty.hide()
        self.lblMsgLoading.show()

    def show_messages_empty(self, hint: str | None = None) -> None:
        self.lblMsgLoading.hide()
        self.listMessages.hide()
        self.lblMsgEmpty.setText(hint or '暂无消息')
        self.lblMsgEmpty.show()

    def set_messages(self, messages: list) -> None:
        self.lblMsgLoading.hide()
        self.listMessages.show()
        self.listMessages.clear()
        self._bubbles.clear()
        if not messages:
            self.show_messages_empty()
            return
        self.lblMsgEmpty.hide()
        for m in messages:
            self._add_bubble(m)
        self.listMessages.scrollToBottom()

    def append_messages(self, messages: list) -> None:
        if not messages:
            return
        self.lblMsgLoading.hide()
        self.lblMsgEmpty.hide()
        self.listMessages.show()
        for m in messages:
            self._add_bubble(m)
        self.listMessages.scrollToBottom()

    def _add_bubble(self, m: dict) -> None:
        text = m.get('content') or ''
        mtype = m.get('type') or 'friend'
        item = QListWidgetItem(self.listMessages)

        if mtype in TYPE_SYS:
            w = QLabel(text)
            w.setWordWrap(True)
            w.setAlignment(Qt.AlignCenter)
            w.setStyleSheet(f'color: {SUB}; font-size: 11px; background: transparent; padding: 2px;')
            self._bubbles.append(w)
            self.listMessages.addItem(item)
            self.listMessages.setItemWidget(item, w)
            item.setSizeHint(w.sizeHint())
            return

        is_self = mtype == 'self'
        bubble = QLabel(text)
        bubble.setWordWrap(True)
        bubble.setMaximumWidth(250)
        bubble.setStyleSheet(
            f'background: {BRAND_DARK}; color: #ffffff; border-radius: 8px; padding: 6px 8px;'
            if is_self
            else f'background: {PANEL}; color: {TEXT}; border-radius: 8px; padding: 6px 8px;'
        )

        container = QWidget()
        lay = QHBoxLayout(container)
        lay.setContentsMargins(4, 2, 4, 2)
        if is_self:
            lay.addStretch(1)
            lay.addWidget(bubble)
        else:
            col = QVBoxLayout()
            if m.get('sender'):
                name = QLabel(str(m['sender']))
                name.setStyleSheet(f'color: {SUB}; font-size: 11px; background: transparent;')
                col.addWidget(name)
            col.addWidget(bubble)
            lay.addLayout(col)
            lay.addStretch(1)

        self._bubbles.append(container)
        self.listMessages.addItem(item)
        self.listMessages.setItemWidget(item, container)
        item.setSizeHint(container.sizeHint())

    # ---------------- 回复区 ----------------
    def set_reply(self, text: str, source: str = '') -> None:
        self.editReply.setPlainText(text)
        if source == 'rule':
            self.lblSource.setText('来源：rule（规则兜底）')
        elif source:
            self.lblSource.setText(f'来源：{source}')
        else:
            self.lblSource.setText('')

    def reply_text(self) -> str:
        return self.editReply.toPlainText().strip()

    def instruction(self) -> str:
        return self.inputInstruction.text().strip()

    def set_generating(self, busy: bool) -> None:
        self.btnGenerate.setEnabled(not busy)
        self.btnGenerate.setText('生成中…' if busy else '生成回复')

    def set_sending(self, busy: bool) -> None:
        for b in (self.btnFill, self.btnSend):
            b.setEnabled(not busy)

    def _sync_send_enabled(self) -> None:
        ok = bool(self.reply_text())
        self.btnFill.setEnabled(ok)
        self.btnSend.setEnabled(ok)

    # ---------------- toast（非模态，不抢焦点）----------------
    def toast(self, message: str, level: str = 'info') -> None:
        color = {'ok': BRAND, 'warn': WARN, 'error': ERROR}.get(level, TEXT)
        self.lblToast.setText(message)
        self.lblToast.setStyleSheet(
            f'background: {PANEL}; color: {color}; border: 1px solid {LINE}; '
            f'border-radius: 6px; padding: 6px; font-size: 11px;'
        )
        self.lblToast.show()
        QTimer.singleShot(2600, self.lblToast.hide)

    def _sync_selection_newno(self) -> None:
        """选中会话后去掉红点标记（PRD §3.6 B）。"""
        item = self.listSessions.currentItem()
        if item and item.text().endswith(' 🔴'):
            item.setText(item.text()[:-2].strip())
