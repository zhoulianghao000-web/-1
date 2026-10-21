"""V0.connect — 连接状态页（PRD §3 V0）。

三态必须齐全：
- 加载中：灰色圆点 + "正在连接后端…"
- 错误：红点 + 可读文案（绝不显示堆栈）
- 正常：绿/黄点 + 后端返回的 detail
"""
from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QToolButton, QVBoxLayout, QWidget

from theme import BRAND, ERROR, PANEL, SUB, TEXT, WARN

HINT_TEXT = (
    'QQ 半自动模式：在 QQ 里选中对方的话按 Ctrl+C，再点侧边栏【刷新】即可读到消息；\n'
    '发送时会把 QQ 拉到前台粘贴（回车由你手动按）。打包版把 .env 放在 exe 同目录。'
)


class ConnectView(QWidget):
    """用途：后端未就绪 / 微信未运行 / 降级 mock 时的兜底页。"""

    retry_clicked = Signal()
    continue_clicked = Signal()
    refresh_requested = Signal()
    close_clicked = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName('connectView')

        self.lblIcon = QLabel('●')
        self.lblIcon.setObjectName('lblIcon')
        self.lblIcon.setStyleSheet(f'color: {SUB}; font-size: 20px;')

        self.lblTitle = QLabel('正在连接后端…')
        self.lblTitle.setObjectName('lblTitle')
        self.lblTitle.setStyleSheet(f'font-size: 15px; font-weight: 600; color: {TEXT};')

        self.btnClose = QToolButton()
        self.btnClose.setObjectName('btnClose')
        self.btnClose.setText('✕')
        self.btnClose.setToolTip('关闭侧边栏（退出应用）')
        self.btnClose.clicked.connect(self.close_clicked.emit)

        head = QHBoxLayout()
        head.addWidget(self.lblIcon)
        head.addSpacing(6)
        head.addWidget(self.lblTitle)
        head.addStretch(1)
        head.addWidget(self.btnClose)

        self.lblDetail = QLabel('正在请求 /api/status')
        self.lblDetail.setObjectName('lblDetail')
        self.lblDetail.setStyleSheet(f'color: {SUB};')
        self.lblDetail.setWordWrap(True)

        self.lblHint = QLabel(HINT_TEXT)
        self.lblHint.setObjectName('lblHint')
        self.lblHint.setStyleSheet(
            f'color: {SUB}; background: {PANEL}; border: 1px solid #242a34; '
            f'border-radius: 8px; padding: 8px; font-size: 11px;'
        )
        self.lblHint.setWordWrap(True)

        self.btnRetry = QPushButton('重新连接')
        self.btnRetry.setObjectName('btnRetry')
        self.btnRetry.setProperty('primary', True)
        self.btnRetry.clicked.connect(self.retry_clicked.emit)

        self.btnContinue = QPushButton('仍以演示模式进入')
        self.btnContinue.setObjectName('btnContinue')
        self.btnContinue.clicked.connect(self.continue_clicked.emit)

        btns = QHBoxLayout()
        btns.addWidget(self.btnRetry)
        btns.addWidget(self.btnContinue)
        btns.addStretch(1)

        root = QVBoxLayout(self)
        root.setContentsMargins(16, 18, 16, 18)
        root.setSpacing(10)
        root.addLayout(head)
        root.addWidget(self.lblDetail)
        root.addWidget(self.lblHint)
        root.addLayout(btns)
        root.addStretch(1)

    # ---------------- 三态渲染 ----------------
    def show_loading(self) -> None:
        self.lblIcon.setStyleSheet(f'color: {SUB}; font-size: 20px;')
        self.lblTitle.setText('正在连接后端…')
        self.lblDetail.setText('正在请求 /api/status')
        self.btnRetry.setEnabled(False)
        self.btnContinue.hide()

    def show_error(self, message: str) -> None:
        """网络异常 / 信封异常：给可读文案，不显示堆栈。"""
        self.lblIcon.setStyleSheet(f'color: {ERROR}; font-size: 20px;')
        self.lblTitle.setText('后端未启动')
        self.lblDetail.setText(message)
        self.btnRetry.setEnabled(True)
        self.btnContinue.hide()

    def show_status(self, data: dict) -> None:
        """GET /api/status 成功：按 PRD §3 V0 状态映射表渲染。"""
        mode = data.get('mode')
        nickname = data.get('nickname') or 'QQ 侧边栏'
        running = bool(data.get('wechat_running'))

        if mode == 'qq' and running:
            self.lblIcon.setStyleSheet(f'color: {BRAND}; font-size: 20px;')
            self.lblTitle.setText('QQ 已就绪（半自动模式）')
            self.btnContinue.hide()
        elif mode == 'qq':
            self.lblIcon.setStyleSheet(f'color: {WARN}; font-size: 20px;')
            self.lblTitle.setText('QQ 未运行')
            self.btnContinue.show()
        elif mode == 'wxauto' and running:
            self.lblIcon.setStyleSheet(f'color: {BRAND}; font-size: 20px;')
            self.lblTitle.setText(f'已连接 {nickname}')
            self.btnContinue.hide()
        elif mode == 'wxauto':
            self.lblIcon.setStyleSheet(f'color: {WARN}; font-size: 20px;')
            self.lblTitle.setText('微信未运行')
            self.btnContinue.show()
        else:
            self.lblIcon.setStyleSheet(f'color: {WARN}; font-size: 20px;')
            self.lblTitle.setText('演示数据')
            self.btnContinue.show()

        self.lblDetail.setText(data.get('detail') or '')
        self.btnRetry.setEnabled(True)
