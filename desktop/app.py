"""入口：`python desktop/app.py`，打包后即为单个 exe 的入口。

打包形态下**后端内嵌在本进程里**（uvicorn 跑在守护线程），双击 exe 即可用，
不需要另外开终端跑 `server.py`。若本机已有后端在跑（端口已占用），就直接复用它。
"""
from __future__ import annotations

import socket
import sys
import threading
from pathlib import Path

DESKTOP_DIR = Path(__file__).resolve().parent
BACKEND_DIR = DESKTOP_DIR.parent / 'backend'
sys.path.insert(0, str(DESKTOP_DIR))
# 静态 import，保证 PyInstaller 能把整个后端依赖树打进包
sys.path.insert(0, str(BACKEND_DIR))

from PySide6.QtWidgets import QApplication  # noqa: E402

import theme  # noqa: E402
from window import SidebarWindow  # noqa: E402

FROZEN = bool(getattr(sys, 'frozen', False))


def root_dir() -> Path:
    """打包后根目录 = exe 所在目录（.env / data / logs 都在它旁边）。"""
    if FROZEN:
        return Path(sys.executable).resolve().parent
    return DESKTOP_DIR.parent


def _redirect_stdio() -> None:
    """windowed 打包没有控制台，把输出落盘，否则排错时两眼一抹黑。"""
    if not FROZEN:
        return
    log_dir = root_dir() / 'logs'
    log_dir.mkdir(parents=True, exist_ok=True)
    f = open(log_dir / 'app.log', 'a', encoding='utf-8')
    sys.stdout = sys.stderr = f


def port_open(host: str, port: int, timeout: float = 0.4) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def start_embedded_backend() -> bool:
    """端口空闲才起内嵌后端；已有人在跑就复用，避免抢端口。返回是否由本进程启动。"""
    try:
        import config
    except Exception:
        return False
    if port_open(config.HOST, config.PORT):
        print(f'[app] 复用已运行的后端 {config.HOST}:{config.PORT}')
        return False

    def run() -> None:
        try:
            import uvicorn
            from server import app as fastapi_app

            uvicorn.run(fastapi_app, host=config.HOST, port=config.PORT, log_level='warning')
        except Exception as e:  # 后端挂了也不能拖死 UI
            print(f'[app] 内嵌后端启动失败: {type(e).__name__}: {e}')

    threading.Thread(target=run, daemon=True).start()
    print(f'[app] 内嵌后端启动中 {config.HOST}:{config.PORT}')
    return True


def main() -> None:
    _redirect_stdio()
    started = start_embedded_backend()
    if started:
        # 等等后端就绪，否则首屏会闪一下"后端未启动"
        for _ in range(60):
            try:
                import config

                if port_open(config.HOST, config.PORT):
                    break
            except Exception:
                break
            import time

            time.sleep(0.1)

    app = QApplication(sys.argv)
    app.setStyleSheet(theme.QSS)

    win = SidebarWindow()
    win.show()
    sys.exit(app.exec())


if __name__ == '__main__':
    main()
