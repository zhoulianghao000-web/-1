from .base import BaseAdapter
from .mock_adapter import MockAdapter
from .qq_adapter import QQAdapter

__all__ = ['BaseAdapter', 'MockAdapter', 'QQAdapter']


def create_adapter(prefer: str = 'auto') -> BaseAdapter:
    """按优先级创建 Adapter：**qq（默认目标 IM）-> wxauto -> mock**。

    - `qq`：QQ NT 半自动（剪贴板读消息 + 激活窗口粘贴），不要求窗口已启动
    - `wxauto`：微信 3.9.11.17（本机微信为 4.x，实际不可用，保留兼容）
    - `mock`：演示数据，永远可用，作为最后兜底
    """
    if prefer in ('auto', 'qq'):
        try:
            return QQAdapter()
        except Exception as e:
            if prefer == 'qq':
                raise
            print(f'[adapter] QQ adapter 不可用，尝试下一个：{type(e).__name__}: {e}')
    if prefer in ('auto', 'wxauto'):
        try:
            from .wxauto_adapter import WxautoAdapter

            return WxautoAdapter()
        except Exception as e:  # 微信没开 / 版本不对 / 没装 wxauto
            if prefer == 'wxauto':
                raise
            print(f'[adapter] wxauto 不可用，降级 mock：{type(e).__name__}: {e}')
    return MockAdapter()
