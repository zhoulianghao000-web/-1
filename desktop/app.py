"""入口：python desktop/app.py"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from PySide6.QtWidgets import QApplication  # noqa: E402

import theme  # noqa: E402
from window import SidebarWindow  # noqa: E402


def main() -> None:
    app = QApplication(sys.argv)
    app.setStyleSheet(theme.QSS)

    win = SidebarWindow()
    win.show()
    sys.exit(app.exec())


if __name__ == '__main__':
    main()
