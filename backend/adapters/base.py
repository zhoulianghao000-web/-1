"""微信采集/发送能力抽象层。

目的：把"如何读写微信"这件事关在 Adapter 里。
wxauto 已停止维护且强绑定微信 3.9.11.17，将来换 4.x 方案（wechatauto-replica / 自写 UIA / 企业微信 API）
只需要新增一个 Adapter，UI 与业务层不用改一行。
"""
from abc import ABC, abstractmethod
from typing import Any


class BaseAdapter(ABC):
    name = 'base'
    # 该 Adapter 是否会强制把微信窗口拉到前台（影响侧边栏 UX）
    steals_foreground = False

    @abstractmethod
    def status(self) -> dict:
        """返回 Adapter 自身状态，供前端展示。"""

    @abstractmethod
    def sessions(self) -> list[dict]:
        """会话列表：[{name, time, content, isnew}]"""

    @abstractmethod
    def messages(self, who: str | None = None, limit: int = 50) -> list[dict]:
        """消息列表：[{type, sender, content, id}]"""

    @abstractmethod
    def send(self, who: str, text: str) -> dict:
        """填入并回车发送。"""

    @abstractmethod
    def fill(self, who: str, text: str) -> dict:
        """只填入输入框，不发送（让人自己检查后再回车）。"""

    def poll_new(self) -> dict[str, list[dict]]:
        """可选：轮询新消息。默认不实现（避免抢占前台）。"""
        return {}

    def close(self) -> None:
        pass
