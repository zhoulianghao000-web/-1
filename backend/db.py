"""SQLite 数据访问层（CLAUDE.md §6 数据模型）。

4 张表：chats / messages / quick_replies / settings
时间统一存 UTC ISO8601 字符串；消息写入用 INSERT OR IGNORE 做 id 去重。

自检：`python db.py`  → 建表 + 写入种子数据（幂等）
"""
from __future__ import annotations

import sqlite3
import time
from pathlib import Path
from typing import Any

try:
    from config import DB_PATH
except ImportError:  # 作为包被导入时的兜底
    from backend.config import DB_PATH

SCHEMA = """
CREATE TABLE IF NOT EXISTS chats (
    chat_key    TEXT PRIMARY KEY,
    name        TEXT NOT NULL,
    last_msg_at TEXT,
    unread      INTEGER NOT NULL DEFAULT 0,
    updated_at  TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS messages (
    id         TEXT PRIMARY KEY,
    chat_key   TEXT NOT NULL,
    sender     TEXT,
    type       TEXT NOT NULL CHECK (type IN ('friend','self','sys','time','recall')),
    content    TEXT,
    msg_ts     TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (chat_key) REFERENCES chats(chat_key)
);

CREATE INDEX IF NOT EXISTS idx_messages_chat_ts ON messages(chat_key, msg_ts DESC);

CREATE TABLE IF NOT EXISTS quick_replies (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    tag        TEXT NOT NULL,
    content    TEXT NOT NULL,
    sort       INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS settings (
    key   TEXT PRIMARY KEY,
    value TEXT
);
"""


def now_iso() -> str:
    return time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())


def connect() -> sqlite3.Connection:
    path = Path(DB_PATH)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    with connect() as conn:
        conn.executescript(SCHEMA)
        conn.commit()


# ---------------- chats ----------------
def upsert_chat(chat_key: str, name: str, last_msg_at: str | None = None, unread: int | None = None) -> None:
    with connect() as conn:
        if unread is None:
            conn.execute(
                """
                INSERT INTO chats (chat_key, name, last_msg_at, updated_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(chat_key) DO UPDATE SET
                    name=excluded.name,
                    last_msg_at=COALESCE(excluded.last_msg_at, chats.last_msg_at),
                    updated_at=excluded.updated_at
                """,
                (chat_key, name, last_msg_at, now_iso()),
            )
        else:
            conn.execute(
                """
                INSERT INTO chats (chat_key, name, last_msg_at, unread, updated_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(chat_key) DO UPDATE SET
                    name=excluded.name,
                    last_msg_at=COALESCE(excluded.last_msg_at, chats.last_msg_at),
                    unread=excluded.unread,
                    updated_at=excluded.updated_at
                """,
                (chat_key, name, last_msg_at, unread, now_iso()),
            )
        conn.commit()


def list_chats() -> list[dict]:
    with connect() as conn:
        rows = conn.execute('SELECT * FROM chats ORDER BY updated_at DESC').fetchall()
    return [dict(r) for r in rows]


# ---------------- messages ----------------
def save_messages(chat_key: str, messages: list[dict]) -> int:
    """批量写入消息，靠主键 id 去重，返回实际新增条数。"""
    saved = 0
    with connect() as conn:
        for m in messages:
            mid = m.get('id') or f'{chat_key}-{m.get("type")}-{hash(str(m.get("content")))}'
            cur = conn.execute(
                """
                INSERT OR IGNORE INTO messages (id, chat_key, sender, type, content, msg_ts, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    str(mid),
                    chat_key,
                    m.get('sender') or '',
                    m.get('type') or 'friend',
                    m.get('content') or '',
                    m.get('msg_ts'),
                    now_iso(),
                ),
            )
            saved += cur.rowcount
        conn.commit()
    return saved


def list_messages(chat_key: str, limit: int = 60) -> list[dict]:
    with connect() as conn:
        rows = conn.execute(
            'SELECT id, chat_key, sender, type, content, msg_ts, created_at FROM messages '
            'WHERE chat_key = ? ORDER BY created_at ASC, id ASC LIMIT ?',
            (chat_key, limit),
        ).fetchall()
    return [dict(r) for r in rows]


def count_messages() -> int:
    with connect() as conn:
        return conn.execute('SELECT COUNT(*) FROM messages').fetchone()[0]


# ---------------- quick_replies ----------------
def add_quick_reply(tag: str, content: str, sort: int = 0) -> None:
    with connect() as conn:
        conn.execute(
            'INSERT INTO quick_replies (tag, content, sort, created_at) VALUES (?, ?, ?, ?)',
            (tag, content, sort, now_iso()),
        )
        conn.commit()


def list_quick_replies() -> list[dict]:
    with connect() as conn:
        rows = conn.execute('SELECT * FROM quick_replies ORDER BY sort ASC, id ASC').fetchall()
    return [dict(r) for r in rows]


# ---------------- settings ----------------
def set_setting(key: str, value: Any) -> None:
    with connect() as conn:
        conn.execute(
            'INSERT INTO settings (key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value=excluded.value',
            (key, str(value)),
        )
        conn.commit()


def get_setting(key: str, default: str | None = None) -> str | None:
    with connect() as conn:
        row = conn.execute('SELECT value FROM settings WHERE key = ?', (key,)).fetchone()
    return row['value'] if row else default


# ---------------- 种子数据 ----------------
SEED_CHATS = [
    ('张三', '张三', '2026-10-20T06:32:00Z', 2),
    ('产品交流群', '产品交流群', '2026-10-20T06:20:00Z', 1),
    ('文件传输助手', '文件传输助手', '2026-10-19T09:00:00Z', 0),
]

SEED_MESSAGES = [
    ('seed-1', '张三', '张三', 'friend', '在吗？', '2026-10-20T06:30:00Z'),
    ('seed-2', '张三', '我', 'self', '在的，你说', '2026-10-20T06:31:00Z'),
    ('seed-3', '张三', '张三', 'friend', '上次那个报价单能再便宜点吗？预算卡得紧', '2026-10-20T06:32:00Z'),
    ('seed-4', '产品交流群', '王五', 'friend', '新版原型 v3 出来了，大家看下', '2026-10-20T06:18:00Z'),
    ('seed-5', '产品交流群', '赵六', 'friend', '侧边栏那个交互我感觉有点挤', '2026-10-20T06:19:00Z'),
    ('seed-6', '产品交流群', '我', 'self', '收到，我调整一下间距', '2026-10-20T06:20:00Z'),
    ('seed-7', '文件传输助手', '我', 'self', '会议纪要.docx', '2026-10-19T09:00:00Z'),
]

SEED_QUICK_REPLIES = [
    ('常用', '收到，我这边跟进一下，有进展第一时间同步你。', 0),
    ('常用', '在的，你说～', 1),
    ('商务', '方便说下你们大概的量和交付时间吗？我给你配个合适的方案。', 2),
]


def seed(force: bool = False) -> dict:
    """写入种子数据（幂等）。force=True 会清空重灌。"""
    init_db()
    with connect() as conn:
        if force:
            conn.executescript('DELETE FROM messages; DELETE FROM chats; DELETE FROM quick_replies;')
        conn.executemany(
            'INSERT OR IGNORE INTO chats (chat_key, name, last_msg_at, unread, updated_at) VALUES (?,?,?,?,?)',
            [(k, n, t, u, now_iso()) for k, n, t, u in SEED_CHATS],
        )
        conn.executemany(
            'INSERT OR IGNORE INTO messages (id, chat_key, sender, type, content, msg_ts, created_at) '
            'VALUES (?,?,?,?,?,?,?)',
            [(i, c, s, t, m, ts, now_iso()) for i, c, s, t, m, ts in SEED_MESSAGES],
        )
        conn.executemany(
            'INSERT OR IGNORE INTO quick_replies (id, tag, content, sort, created_at) VALUES (?,?,?,?,?)',
            [(idx + 1, tag, content, sort, now_iso())
             for idx, (tag, content, sort) in enumerate(SEED_QUICK_REPLIES)],
        )
        conn.execute(
            'INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)', ('sidebar_width', '380')
        )
        conn.execute(
            'INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)', ('llm_model', 'deepseek-chat')
        )
        conn.commit()
    return {
        'chats': len(list_chats()),
        'messages': count_messages(),
        'quick_replies': len(list_quick_replies()),
    }


if __name__ == '__main__':
    import sys

    do_force = '--force' in sys.argv
    init_db()
    stat = seed(force=do_force)
    print(f'数据库：{DB_PATH}')
    print(f'种子数据：{stat}')
