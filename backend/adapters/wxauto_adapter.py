"""基于 wxauto 3.9 的真实微信 Adapter。

约束（来自 wxauto 源码，务必遵守）：
- 仅支持微信 PC 版 3.9.11.17，系统缩放需为 100%，窗口需在前台且不被遮挡
- wxauto 内部每次操作都会 _show() 强制置顶微信，因此侧边栏必须做成"无焦点窗口"，
  否则焦点被侧边栏抢走后 SendKeys 会失效
- GetNextNewMessage() 会 DoubleClick 聊天图标并切换会话，轮询会不停抢前台，
  因此实时监听默认关闭，由前端显式开启
"""
from __future__ import annotations

from .base import BaseAdapter


class WxautoAdapter(BaseAdapter):
    name = 'wxauto'
    steals_foreground = True

    def __init__(self, language: str = 'cn') -> None:
        from wxauto import WeChat  # 导入失败即代表不可用

        self.wx = WeChat(language=language)
        self.language = language

    # ---------- 状态 ----------
    def status(self) -> dict:
        version = None
        try:
            from wxauto import VERSION

            version = VERSION
        except Exception:
            pass
        return {
            'ok': True,
            'mode': 'wxauto',
            'nickname': getattr(self.wx, 'nickname', None),
            'wechat_version': version,
            'detail': f'已连接微信（{getattr(self.wx, "nickname", "?")}）',
        }

    # ---------- 会话 ----------
    def sessions(self) -> list[dict]:
        out = []
        try:
            for s in self.wx.GetSession():
                out.append(
                    {
                        'name': getattr(s, 'name', None),
                        'time': getattr(s, 'time', None),
                        'content': getattr(s, 'content', None),
                        'isnew': bool(getattr(s, 'isnew', False)),
                    }
                )
        except Exception as e:
            out = [{'name': '(读取失败)', 'content': str(e), 'time': None, 'isnew': False}]
        return out

    # ---------- 消息 ----------
    def messages(self, who: str | None = None, limit: int = 50) -> list[dict]:
        if who:
            self.wx.ChatWith(who)
        msgs = self.wx.GetAllMessage() or []
        out = []
        for m in msgs[-limit:]:
            out.append(
                {
                    'type': getattr(m, 'type', 'friend'),
                    'sender': getattr(m, 'sender', ''),
                    'content': getattr(m, 'content', ''),
                    'id': getattr(m, 'id', None),
                }
            )
        return out

    # ---------- 发送 ----------
    def _locate_editbox(self, who: str | None = None):
        """定位当前（或指定会话的）输入框控件。"""
        if who:
            try:
                editbox = self.wx.ChatBox.EditControl(searchDepth=10)
                if who not in (self.wx.CurrentChat() or '') or who not in (editbox.Name or ''):
                    self.wx.ChatWith(who)
                    editbox = self.wx.ChatBox.EditControl(Name=who, searchDepth=10)
            except Exception:
                self.wx.ChatWith(who)
                editbox = self.wx.ChatBox.EditControl(Name=who, searchDepth=10)
        else:
            editbox = self.wx.ChatBox.EditControl(searchDepth=10)
        return editbox

    def fill(self, who: str, text: str) -> dict:
        from wxauto.utils import SetClipboardText

        try:
            editbox = self._locate_editbox(who)
            self.wx._show()
            if not editbox.HasKeyboardFocus:
                editbox.Click(simulateMove=False)
            editbox.SendKeys('{Ctrl}a', waitTime=0)
            SetClipboardText(text)
            editbox.SendKeys('{Ctrl}v')
            return {'ok': True, 'detail': f'已填入输入框：{who}'}
        except Exception as e:
            return {'ok': False, 'error': f'{type(e).__name__}: {e}'}

    def send(self, who: str, text: str) -> dict:
        try:
            self.wx.SendMsg(text, who=who)
            return {'ok': True, 'detail': f'已发送：{who}'}
        except Exception as e:
            return {'ok': False, 'error': f'{type(e).__name__}: {e}'}

    def poll_new(self) -> dict[str, list[dict]]:
        """⚠️ 会强制把微信拉到前台，只在前端显式开启实时监听时调用。"""
        try:
            new = self.wx.GetNextNewMessage() or {}
        except Exception:
            return {}
        out: dict[str, list[dict]] = {}
        for chat, msgs in new.items():
            out[chat] = [
                {
                    'type': getattr(m, 'type', 'friend'),
                    'sender': getattr(m, 'sender', ''),
                    'content': getattr(m, 'content', ''),
                    'id': getattr(m, 'id', None),
                }
                for m in msgs
                if getattr(m, 'type', None) == 'friend'
            ]
        return {k: v for k, v in out.items() if v}
