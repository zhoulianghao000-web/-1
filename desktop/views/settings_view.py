"""V2.settings — 设置页（PRD §3 V2，实现决策 grill 2026-10-21）。

生效策略（全部即时）：
- Key / BaseURL / 模型名：后端每次生成前从 DB 读 → 保存即生效
- 窗口宽度：保存后 UI 立即 setFixedWidth，贴边线程同步改
- 适配器：热切换（后端惰性重建 + 自动关监听，在途请求跑完不报错）
"""
from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from theme import BRAND, ERROR, LINE, PANEL, SUB, TEXT, WARN

ADAPTER_TIPS = {
    'qq': 'QQ NT 半自动：读剪贴板 / 粘贴发送（默认）',
    'wxauto': '微信 3.9.11.17（wxauto，本机 4.x 用不了）',
    'mock': '演示数据，不碰任何 IM 窗口',
    'auto': 'qq → wxauto → mock 自动降级',
}


class SettingsView(QWidget):
    back_clicked = Signal()
    save_clicked = Signal()  # window.py 收集表单后调 API

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName('settingsView')

        self.btnBack = QToolButton()
        self.btnBack.setText('←')
        self.btnBack.setToolTip('返回')
        self.btnBack.clicked.connect(self.back_clicked.emit)

        self.lblTitle = QLabel('设置')
        self.lblTitle.setStyleSheet(f'font-size: 14px; font-weight: 600; color: {TEXT};')

        top = QVBoxLayout()
        head = self._row(self.btnBack, self.lblTitle)
        top.addLayout(head)

        # ---- 表单 ----
        self.inputApiKey = QLineEdit()
        self.inputApiKey.setEchoMode(QLineEdit.Password)
        self.inputApiKey.setPlaceholderText('sk-…（留空 = 未配置，走规则兜底）')

        self.inputBaseUrl = QLineEdit()
        self.inputBaseUrl.setPlaceholderText('https://api.deepseek.com/v1')

        self.inputModel = QLineEdit()
        self.inputModel.setPlaceholderText('deepseek-chat')

        self.spinWidth = QSpinBox()
        self.spinWidth.setRange(300, 600)
        self.spinWidth.setSingleStep(10)
        self.spinWidth.setSuffix(' px')

        self.cmbAdapter = QComboBox()
        for name, tip in ADAPTER_TIPS.items():
            self.cmbAdapter.addItem(name)
            self.cmbAdapter.setItemData(self.cmbAdapter.count() - 1, tip, 1)  # Qt.ToolTipRole
        self.cmbAdapter.currentTextChanged.connect(self._adapter_tip)

        self.lblAdapterTip = QLabel('')
        self.lblAdapterTip.setWordWrap(True)
        self.lblAdapterTip.setStyleSheet(f'color: {SUB}; font-size: 11px;')

        form = QFormLayout()
        form.addRow('API Key', self.inputApiKey)
        form.addRow('Base URL', self.inputBaseUrl)
        form.addRow('模型名', self.inputModel)
        form.addRow('窗口宽度', self.spinWidth)
        form.addRow('适配器', self.cmbAdapter)
        form.addRow('', self.lblAdapterTip)

        self.btnSave = QPushButton('保存')
        self.btnSave.setProperty('primary', True)
        self.btnSave.clicked.connect(self.save_clicked.emit)

        self.lblToast = QLabel('')
        self.lblToast.setWordWrap(True)
        self.lblToast.hide()

        top.addLayout(form)
        top.addWidget(self.btnSave)
        top.addWidget(self.lblToast)
        top.addStretch(1)
        self.setLayout(top)

    # ---------------- 渲染 ----------------
    def _row(self, *widgets) -> object:
        from PySide6.QtWidgets import QHBoxLayout

        lay = QHBoxLayout()
        for w in widgets:
            lay.addWidget(w)
        lay.addStretch(1)
        return lay

    def _adapter_tip(self, name: str) -> None:
        self.lblAdapterTip.setText(ADAPTER_TIPS.get(name, ''))

    def set_settings(self, data: dict) -> None:
        self.inputApiKey.setText(data.get('api_key') or '')
        self.inputBaseUrl.setText(data.get('base_url') or '')
        self.inputModel.setText(data.get('model') or '')
        self.spinWidth.setValue(int(data.get('width') or 380))
        idx = self.cmbAdapter.findText(data.get('adapter') or 'qq')
        self.cmbAdapter.setCurrentIndex(max(0, idx))
        self._adapter_tip(self.cmbAdapter.currentText())

    def values(self) -> dict:
        return {
            'api_key': self.inputApiKey.text().strip(),
            'base_url': self.inputBaseUrl.text().strip(),
            'model': self.inputModel.text().strip(),
            'width': self.spinWidth.value(),
            'adapter': self.cmbAdapter.currentText(),
        }

    def set_saving(self, busy: bool) -> None:
        self.btnSave.setEnabled(not busy)
        self.btnSave.setText('保存中…' if busy else '保存')

    def toast(self, message: str, level: str = 'ok') -> None:
        color = {'ok': BRAND, 'warn': WARN, 'error': ERROR}.get(level, TEXT)
        self.lblToast.setStyleSheet(
            f'background: {PANEL}; color: {color}; border: 1px solid {LINE}; '
            f'border-radius: 6px; padding: 6px; font-size: 11px;'
        )
        self.lblToast.setText(message)
        self.lblToast.show()
