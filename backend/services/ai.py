"""AI 建议回复：优先调用 OpenAI 兼容接口，未配置时退回本地规则模板（保证离线可用）。"""
from __future__ import annotations

import httpx

try:
    from config import OPENAI_API_KEY as API_KEY
    from config import OPENAI_BASE_URL as _BASE_URL
    from config import OPENAI_MODEL as MODEL
except ImportError:  # 作为包被导入时的兜底
    import os

    API_KEY = os.getenv('OPENAI_API_KEY', '')
    _BASE_URL = os.getenv('OPENAI_BASE_URL', 'https://api.deepseek.com/v1')
    MODEL = os.getenv('OPENAI_MODEL', 'deepseek-chat')

BASE_URL = _BASE_URL.rstrip('/')

SYSTEM_PROMPT = (
    '你是微信侧边栏里的回复助手。根据聊天记录，给出一条可以直接发送的中文回复。\n'
    '要求：口语化、简短（1-3 句）、不要解释、不要加引号、不要自称 AI。'
    '如果对方在问价格/交付/售后，且信息不足，就先给一个推进式的答复并自然地问清关键信息。'
)


def build_prompt(messages: list[dict], who: str, instruction: str = '') -> str:
    lines = [f'当前对话对象：{who}', '最近聊天记录：']
    for m in messages[-20:]:
        sender = m.get('sender') or ('我' if m.get('type') == 'self' else '对方')
        lines.append(f'{sender}: {m.get("content", "")}')
    if instruction:
        lines.append(f'\n补充要求：{instruction}')
    lines.append('\n请只输出回复内容本身。')
    return '\n'.join(lines)


def _rule_based(messages: list[dict], who: str, instruction: str) -> str:
    """无 LLM 时的兜底：抓最后一条对方消息做关键词匹配。"""
    last = ''
    for m in reversed(messages or []):
        if m.get('type') == 'friend':
            last = m.get('content', '')
            break
    last = last or ''
    if instruction:
        return f'{instruction}'
    if any(k in last for k in ('价格', '便宜', '报价', '多少钱', '预算')):
        return '价格这块我们可以聊，方便说下你们大概的量和交付时间吗？我给你配个合适的方案。'
    if any(k in last for k in ('在吗', '在么', '你好', 'hi', 'hello')):
        return '在的，你说～'
    if any(k in last for k in ('谢谢', '感谢', '好的', '收到')):
        return '不客气，有事随时找我 🙌'
    if '?' in last or '？' in last:
        return '我看下，稍后给你确认。'
    return '收到，我这边跟进一下，有进展第一时间同步你。'


def generate_reply(messages: list[dict], who: str, instruction: str = '') -> dict:
    prompt = build_prompt(messages, who, instruction)
    if not API_KEY:
        return {'reply': _rule_based(messages, who, instruction), 'source': 'rule'}

    try:
        with httpx.Client(timeout=30) as client:
            r = client.post(
                f'{BASE_URL}/chat/completions',
                headers={'Authorization': f'Bearer {API_KEY}'},
                json={
                    'model': MODEL,
                    'messages': [
                        {'role': 'system', 'content': SYSTEM_PROMPT},
                        {'role': 'user', 'content': prompt},
                    ],
                    'temperature': 0.7,
                    'max_tokens': 200,
                },
            )
            r.raise_for_status()
            reply = r.json()['choices'][0]['message']['content'].strip()
            return {'reply': reply, 'source': f'llm:{MODEL}'}
    except Exception as e:
        return {
            'reply': _rule_based(messages, who, instruction),
            'source': 'rule',
            'error': f'{type(e).__name__}: {e}',
        }
