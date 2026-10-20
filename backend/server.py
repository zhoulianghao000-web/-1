"""后端 MVP 主应用（CLAUDE.md §4 接口定义 / §5 统一响应信封）。

所有响应一律为 {"code", "message", "data", "ts"}。
启动：python server.py   （等价 uvicorn server:app --host 127.0.0.1 --port 8765）
"""
from __future__ import annotations

import asyncio
import sys
import time
from contextlib import asynccontextmanager
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import uvicorn  # noqa: E402
from fastapi import FastAPI, Query, WebSocket, WebSocketDisconnect  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402

import config  # noqa: E402
import db  # noqa: E402
from adapters import create_adapter  # noqa: E402
from schemas import (  # noqa: E402
    ERR_BAD_PARAM,
    ERR_INTERNAL,
    ERR_LLM_FAILED,
    ERR_NO_CHAT,
    ERR_READ_MESSAGE,
    ERR_WECHAT_UNAVAILABLE,
    DockIn,
    ListenIn,
    ReplyIn,
    SendIn,
    clamp_limit,
    degrade,
    fail,
    ok,
)
from services import Docking, find_target_hwnd, generate_reply  # noqa: E402

state: dict = {
    'adapter': None,
    'docking': None,
    'current': None,
    'listen': False,
}


def ensure_adapter():
    if state['adapter'] is None:
        state['adapter'] = create_adapter(config.SIDEBAR_ADAPTER)
    return state['adapter']


def ensure_docking() -> Docking:
    if state['docking'] is None:
        state['docking'] = Docking(
            config.SIDEBAR_TITLE,
            width=config.SIDEBAR_WIDTH,
            target_class=config.TARGET_CLASS,
            target_title=config.TARGET_TITLE,
            # QQ 半自动模式：侧边栏要能拿到键盘焦点（让人填"补充要求"、改回复）
            no_activate=(config.SIDEBAR_ADAPTER != 'qq'),
        )
    return state['docking']


# ---------------- §4.10 幂等（防重复发送）----------------
_IDEM_TTL = 3.0
_idem: dict = {}


def _idempotent(key: tuple, executor):
    """3 秒内相同 key 直接返回上次结果，不重复执行。返回 (result, duplicated)。"""
    now = time.time()
    hit = _idem.get(key)
    if hit and now - hit[0] < _IDEM_TTL:
        return hit[1], True
    result = executor()
    _idem[key] = (now, result)
    return result, False


@asynccontextmanager
async def lifespan(app: FastAPI):
    db.init_db()
    db.seed()
    ensure_adapter()
    ensure_docking()
    yield
    d = state.get('docking')
    if d:
        d.stop()
    a = state.get('adapter')
    if a:
        a.close()


app = FastAPI(title='WeChat Sidebar Backend', version='0.1.0', lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=['*'],
    allow_methods=['*'],
    allow_headers=['*'],
)


# ---------------- §4.1 运行状态 ----------------
@app.get('/api/status')
async def status():
    try:
        a = ensure_adapter()
        d = ensure_docking()
        wechat_running = False
        try:
            wechat_running = bool(find_target_hwnd(config.TARGET_CLASS, config.TARGET_TITLE))
        except Exception:
            pass
        st = a.status()
        st.update(
            {
                'wechat_running': wechat_running,
                'docking': bool(d.running),
                'docking_error': d.last_error,
                'listen': state['listen'],
                'current': state['current'],
                'steals_foreground': a.steals_foreground,
            }
        )
        return ok(st)
    except Exception as e:
        return fail(ERR_WECHAT_UNAVAILABLE, f'{type(e).__name__}: {e}')


# ---------------- §4.2 会话列表 ----------------
@app.get('/api/sessions')
async def sessions():
    try:
        items = ensure_adapter().sessions()
        for s in items:
            if s.get('name'):
                db.upsert_chat(s['name'], s['name'], unread=1 if s.get('isnew') else 0)
        return ok({'sessions': items})
    except Exception as e:
        return fail(ERR_WECHAT_UNAVAILABLE, f'{type(e).__name__}: {e}')


# ---------------- §4.3 读取消息 ----------------
@app.get('/api/messages')
async def messages(who: str | None = None, limit: int | None = Query(default=None, ge=1, le=200)):
    limit = clamp_limit(limit)
    if who:
        state['current'] = who
    who = who or state['current']
    if not who:
        return fail(ERR_NO_CHAT)
    try:
        msgs = ensure_adapter().messages(who=who, limit=limit)
    except Exception as e:
        return fail(ERR_READ_MESSAGE, f'{type(e).__name__}: {e}')
    try:
        db.save_messages(who, msgs)
    except Exception:
        pass  # 落库失败不影响读取
    return ok({'who': who, 'messages': msgs})


# ---------------- §4.4 生成建议回复 ----------------
@app.post('/api/reply')
async def reply(body: ReplyIn):
    who = body.who or state['current']
    if not who:
        return fail(ERR_NO_CHAT)
    msgs = body.messages
    if not msgs:
        try:
            msgs = ensure_adapter().messages(who=who)
        except Exception as e:
            return fail(ERR_READ_MESSAGE, f'{type(e).__name__}: {e}')
    res = generate_reply(msgs or [], who, body.instruction)
    if not res.get('reply'):
        return fail(ERR_LLM_FAILED, '大模型未返回内容')
    data = {
        'who': who,
        'reply': res['reply'],
        'source': res.get('source', 'rule'),
        'degraded': bool(res.get('error')),
    }
    if res.get('error'):
        data['error'] = res['error']
        return degrade(data, res['error'])
    return ok(data)


# ---------------- §4.5 只填入输入框 ----------------
@app.post('/api/fill')
async def fill(body: SendIn):
    who = body.who or state['current']
    if not who:
        return fail(ERR_NO_CHAT)
    if not body.text.strip():
        return fail(ERR_BAD_PARAM, 'text 不能为空')
    try:
        r, dup = _idempotent(('fill', who, body.text), lambda: ensure_adapter().fill(who, body.text))
    except Exception as e:
        return fail(ERR_INTERNAL, f'{type(e).__name__}: {e}')
    if not r.get('ok'):
        return fail(ERR_INTERNAL, r.get('error') or '填入失败')
    data = {'ok': True, 'detail': r.get('detail') or f'已填入输入框：{who}'}
    if dup:
        data['duplicated'] = True
    return ok(data)


# ---------------- §4.6 填入并发送 ----------------
@app.post('/api/send')
async def send(body: SendIn):
    who = body.who or state['current']
    if not who:
        return fail(ERR_NO_CHAT)
    if not body.text.strip():
        return fail(ERR_BAD_PARAM, 'text 不能为空')
    def _do_send():
        r = ensure_adapter().send(who, body.text)
        if r.get('ok'):
            try:
                db.save_messages(
                    who,
                    [
                        {
                            'id': f'self-{int(time.time() * 1000)}',
                            'sender': '我',
                            'type': 'self',
                            'content': body.text,
                            'msg_ts': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
                        }
                    ],
                )
            except Exception:
                pass
        return r

    try:
        r, dup = _idempotent(('send', who, body.text), _do_send)
    except Exception as e:
        return fail(ERR_INTERNAL, f'{type(e).__name__}: {e}')
    if not r.get('ok'):
        return fail(ERR_INTERNAL, r.get('error') or '发送失败')
    data = {'ok': True, 'detail': r.get('detail') or f'已发送：{who}'}
    if dup:
        data['duplicated'] = True
    return ok(data)


# ---------------- §4.7 贴边跟随开关 ----------------
@app.post('/api/dock')
async def dock(body: DockIn):
    d = ensure_docking()
    if body.width:
        d.width = body.width
    try:
        if body.on:
            d.start()
        else:
            d.stop()
    except Exception as e:
        return fail(ERR_INTERNAL, f'{type(e).__name__}: {e}')
    return ok({'docking': d.running, 'error': d.last_error})


# ---------------- §4.8 实时监听开关 ----------------
@app.post('/api/listen')
async def listen(body: ListenIn):
    state['listen'] = bool(body.on)
    return ok({'listen': state['listen']})


# ---------------- §4.9 新消息推送 ----------------
@app.websocket('/ws/messages')
async def ws_messages(ws: WebSocket):
    await ws.accept()
    try:
        while True:
            if state['listen']:
                try:
                    new = ensure_adapter().poll_new()
                except Exception:
                    new = {}
                if new:
                    await ws.send_json({'type': 'new', 'data': new})
            await asyncio.sleep(2)
    except WebSocketDisconnect:
        return


if __name__ == '__main__':
    uvicorn.run(app, host=config.HOST, port=config.PORT, log_level='info')
