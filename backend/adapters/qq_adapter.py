"""QQ（NT 架构）半自动 Adapter —— 当前项目的**默认目标 IM**（微信 4.x 无可用采集方案）。

### 为什么只能"半自动"（2026-10-20 本机实测）
QQ NT 9.9.31（`C:\\Program Files\\Tencent\\QQNT\\QQ.exe`）窗口结构：

    class = Chrome_WidgetWin_1
    子窗口 = 1 个（'Intermediate D3D Window'）
    UIA 子树元素总数 = 2（窗口自身 + 1 个无名元素）

会话列表与消息文本全部由 D3D 渲染，**没有可读的控件树**，UIA / win32 都取不到文本。
因此走"半自动"路线（不注入、不 Hook、不读 QQ 本地数据库，符合 CLAUDE.md §7 非目标第 4 条）：

| 能力 | 实现方式 |
|---|---|
| 读消息 | 读系统剪贴板（用户在 QQ 里选中对方的话 Ctrl+C） |
| 会话列表 | 不可读 → 返回单个"QQ 当前窗口"伪会话，发送目标即当前激活的聊天窗口 |
| 填入 fill | 文本写剪贴板 → 激活 QQ 窗口 → Ctrl+V（**不回车**） |
| 发送 send | fill + Enter（**会真的发出消息**，UI 上有二次确认） |

⚠️ `steals_foreground = True`：本适配器会把 QQ 窗口拉到前台，这是粘贴的前提。
"""
from __future__ import annotations

import time

import win32api
import win32clipboard
import win32con
import win32gui
import win32process

from .base import BaseAdapter

VK_CONTROL = 0x11
VK_RETURN = 0x0D
VK_V = 0x56  # 用虚拟键码而非 ord('V')，避免依赖键盘布局
KEYEVENTF_KEYUP = 0x0002


# ---------------- 剪贴板 ----------------
def get_clipboard_text() -> str:
    try:
        win32clipboard.OpenClipboard()
        try:
            if win32clipboard.IsClipboardFormatAvailable(win32clipboard.CF_UNICODETEXT):
                return win32clipboard.GetClipboardData(win32clipboard.CF_UNICODETEXT) or ''
        finally:
            win32clipboard.CloseClipboard()
    except Exception:
        return ''
    return ''


def set_clipboard_text(text: str) -> None:
    win32clipboard.OpenClipboard()
    try:
        win32clipboard.EmptyClipboard()
        win32clipboard.SetClipboardData(win32clipboard.CF_UNICODETEXT, text)
    finally:
        win32clipboard.CloseClipboard()


# ---------------- 窗口与键盘 ----------------
def find_hwnd(target_class: str = '', target_title: str = '') -> int:
    """先按类名精确匹配，再按标题包含匹配。"""
    if target_class:
        h = win32gui.FindWindow(target_class, None)
        if h:
            return h
    if not target_title:
        return 0
    h = win32gui.FindWindow(None, target_title)
    if h:
        return h
    found = 0

    def _enum(hwnd, _):
        nonlocal found
        if not found and target_title.lower() in (win32gui.GetWindowText(hwnd) or '').lower():
            found = hwnd

    win32gui.EnumWindows(_enum, None)
    return found


def _tap(vk: int, up: bool = False) -> None:
    win32api.keybd_event(vk, 0, KEYEVENTF_KEYUP if up else 0, 0)


def _ctrl_combo(vk: int) -> None:
    _tap(VK_CONTROL)
    _tap(vk)
    time.sleep(0.03)
    _tap(vk, up=True)
    _tap(VK_CONTROL, up=True)


class QQAdapter(BaseAdapter):
    name = 'qq'
    steals_foreground = True  # 会激活 QQ 窗口

    def __init__(self, target_class: str = '', target_title: str = 'QQ') -> None:
        self.target_class = target_class
        self.target_title = target_title

    # ---------- 窗口 ----------
    def _hwnd(self) -> int:
        return find_hwnd(self.target_class, self.target_title)

    def _activate(self) -> int:
        """把 QQ 窗口拉到前台（粘贴的前提）。返回 hwnd，0 表示没找到。"""
        h = self._hwnd()
        if not h:
            return 0
        if win32gui.IsIconic(h):
            win32gui.ShowWindow(h, win32con.SW_RESTORE)
        try:
            win32gui.SetForegroundWindow(h)
        except Exception:
            pass
        if win32gui.GetForegroundWindow() == h:
            return h
        # 兜底：Windows 会拒绝非前台进程直接 SetForegroundWindow，借用 AttachThreadInput
        try:
            cur = win32api.GetCurrentThreadId()
            tgt_tid, _ = win32process.GetWindowThreadProcessId(h)
            win32process.AttachThreadInput(cur, tgt_tid, True)
            win32gui.SetForegroundWindow(h)
            win32process.AttachThreadInput(cur, tgt_tid, False)
        except Exception:
            pass
        return h if win32gui.GetForegroundWindow() == h else h

    # ---------- 状态 ----------
    def status(self) -> dict:
        h = self._hwnd()
        return {
            'ok': True,
            'mode': 'qq',
            'nickname': 'QQ',
            'wechat_version': None,
            'detail': (
                f'QQ 半自动模式（窗口已找到 hwnd={h}）：消息读取来自剪贴板，发送会激活 QQ 窗口粘贴'
                if h
                else 'QQ 半自动模式：未找到 QQ 窗口，请打开 QQ 后再操作'
            ),
        }

    # ---------- 会话 ----------
    def sessions(self) -> list[dict]:
        """QQ NT 读不到会话列表 → 返回单个伪会话，发送目标 = 当前激活的聊天窗口。"""
        return [
            {
                'name': 'QQ 当前窗口',
                'time': time.strftime('%H:%M'),
                'content': '半自动：读消息取剪贴板，发送粘贴到当前聊天窗口',
                'isnew': False,
            }
        ]

    # ---------- 消息 ----------
    def messages(self, who: str | None = None, limit: int = 50) -> list[dict]:
        """读剪贴板：在 QQ 里复制对方的话，这里就能看到并据此生成回复。"""
        text = (get_clipboard_text() or '').strip()
        if not text:
            return []
        text = text[:4000]
        return [
            {
                'type': 'friend',
                'sender': who or '对方',
                'content': text,
                'id': f'clip-{int(time.time() * 1000)}',
            }
        ]

    # ---------- 填入 / 发送 ----------
    def fill(self, who: str, text: str) -> dict:
        if not (text or '').strip():
            return {'ok': False, 'error': 'text 不能为空'}
        h = self._activate()
        if not h:
            return {'ok': False, 'error': '未找到 QQ 窗口，请先打开 QQ'}
        set_clipboard_text(text)
        time.sleep(0.1)
        _ctrl_combo(VK_V)
        return {'ok': True, 'detail': f'已粘贴到 QQ 输入框（hwnd={h}），请人工确认后再回车'}

    def send(self, who: str, text: str) -> dict:
        r = self.fill(who, text)
        if not r.get('ok'):
            return r
        time.sleep(0.15)
        _tap(VK_RETURN)
        time.sleep(0.03)
        _tap(VK_RETURN, up=True)
        return {'ok': True, 'detail': '已粘贴并回车发送（QQ 当前窗口）'}

    def poll_new(self) -> dict[str, list[dict]]:
        """QQ 读不到消息流，不做轮询（也避免不停抢前台）。"""
        return {}
