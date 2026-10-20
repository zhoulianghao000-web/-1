"""集中读取环境变量（CLAUDE.md §9）。

优先级：系统环境变量 > .env 文件 > 默认值。
python-dotenv 为可选依赖，装了才自动加载 .env。
"""
from __future__ import annotations

from pathlib import Path

try:
    from dotenv import load_dotenv

    load_dotenv(Path(__file__).resolve().parent.parent / '.env')
except Exception:
    pass

import os  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
BACKEND = ROOT / 'backend'


def _str(name: str, default: str = '') -> str:
    return os.getenv(name, default)


def _int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, '') or default)
    except ValueError:
        return default


# ---- 服务 ----
PORT = _int('SIDEBAR_PORT', 8765)
HOST = _str('SIDEBAR_HOST', '127.0.0.1')

# ---- 侧边栏窗口 ----
SIDEBAR_TITLE = _str('SIDEBAR_TITLE', 'WeChat Sidebar')
SIDEBAR_WIDTH = _int('SIDEBAR_WIDTH', 380)
SIDEBAR_ADAPTER = _str('SIDEBAR_ADAPTER', 'auto').lower()

# ---- 贴边跟随的目标 IM 窗口（先按类名找，再按标题找）----
# 默认微信 3.9 窗口类名；换成其他 IM（如 QQ NT）时用 SIDEBAR_TARGET_TITLE 指定窗口标题
TARGET_CLASS = _str('SIDEBAR_TARGET_CLASS', 'WeChatMainWndForPC')
TARGET_TITLE = _str('SIDEBAR_TARGET_TITLE', '')

# ---- 数据库 ----
DB_PATH = Path(os.getenv('SIDEBAR_DB', '') or (ROOT / 'data' / 'sidebar.db'))

# ---- LLM ----
OPENAI_API_KEY = _str('OPENAI_API_KEY', '')
OPENAI_BASE_URL = _str('OPENAI_BASE_URL', 'https://api.deepseek.com/v1')
OPENAI_MODEL = _str('OPENAI_MODEL', 'deepseek-chat')
