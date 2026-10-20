from .base import BaseAdapter
from .mock_adapter import MockAdapter

__all__ = ['BaseAdapter', 'MockAdapter']


def create_adapter(prefer: str = 'auto') -> BaseAdapter:
    """按优先级创建 Adapter：wxauto(真实微信) -> mock(演示)。"""
    if prefer in ('auto', 'wxauto'):
        try:
            from .wxauto_adapter import WxautoAdapter

            return WxautoAdapter()
        except Exception as e:  # 微信没开 / 版本不对 / 没装 wxauto
            if prefer == 'wxauto':
                raise
            print(f'[adapter] wxauto 不可用，降级 mock：{type(e).__name__}: {e}')
    return MockAdapter()
