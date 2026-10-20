"""演示用 Adapter：没有微信 / wxauto 不可用时自动启用，保证 UI 永远能跑通。"""
import random
import time
from typing import Any

from .base import BaseAdapter

DEMO_SESSIONS = [
    {'name': '张三', 'time': '14:32', 'content': '那个报价单能再便宜点吗？', 'isnew': True},
    {'name': '产品交流群', 'time': '14:20', 'content': '[图片] 新版原型 v3', 'isnew': True},
    {'name': '文件传输助手', 'time': '昨天', 'content': '会议纪要.docx', 'isnew': False},
    {'name': '李四', 'time': '昨天', 'content': '好的，收到', 'isnew': False},
]

DEMO_MSGS = {
    '张三': [
        {'type': 'time', 'sender': 'Time', 'content': '14:30'},
        {'type': 'friend', 'sender': '张三', 'content': '在吗？'},
        {'type': 'self', 'sender': '我', 'content': '在的，你说'},
        {'type': 'friend', 'sender': '张三', 'content': '上次那个报价单能再便宜点吗？预算卡得紧'},
        {'type': 'friend', 'sender': '张三', 'content': '我们这边一次性下单 50 套'},
    ],
    '产品交流群': [
        {'type': 'time', 'sender': 'Time', 'content': '14:18'},
        {'type': 'friend', 'sender': '王五', 'content': '新版原型 v3 出来了，大家看下'},
        {'type': 'friend', 'sender': '赵六', 'content': '侧边栏那个交互我感觉有点挤'},
        {'type': 'self', 'sender': '我', 'content': '收到，我调整一下间距'},
    ],
}


class MockAdapter(BaseAdapter):
    name = 'mock'
    steals_foreground = False

    def __init__(self) -> None:
        self._sent: list[dict] = []
        self._current = DEMO_SESSIONS[0]['name']

    def status(self) -> dict:
        return {
            'ok': True,
            'mode': 'mock',
            'nickname': '演示账号',
            'wechat_version': None,
            'detail': '未检测到微信/wxauto，当前为演示数据',
        }

    def sessions(self) -> list[dict]:
        return [dict(s) for s in DEMO_SESSIONS]

    def messages(self, who: str | None = None, limit: int = 50) -> list[dict]:
        if who:
            self._current = who
        msgs = DEMO_MSGS.get(self._current, DEMO_MSGS['张三'])
        out = []
        for i, m in enumerate(msgs[-limit:]):
            item = dict(m)
            item['id'] = f'mock-{self._current}-{i}'
            out.append(item)
        return out

    def send(self, who: str, text: str) -> dict:
        self._sent.append({'who': who, 'text': text, 'ts': time.time()})
        return {'ok': True, 'detail': f'(演示) 已发送给 {who}'}

    def fill(self, who: str, text: str) -> dict:
        return {'ok': True, 'detail': f'(演示) 已填入输入框：{who}'}

    def poll_new(self) -> dict[str, list[dict]]:
        # 5% 概率伪造一条新消息，用来演示实时刷新
        if random.random() < 0.05:
            return {'张三': [{'type': 'friend', 'sender': '张三', 'content': '还在吗？', 'id': f'mock-{time.time()}'}]}
        return {}
