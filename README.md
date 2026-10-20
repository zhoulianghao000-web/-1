# 微信侧边栏外挂（WeChat Sidebar）

贴在微信窗口右侧的无焦点浮窗：读取当前会话 → 大模型生成建议回复 → 人工确认后一键填入 / 发送。

**形态**：独立进程 + 独立窗口跟随微信（不注入、不修改微信进程）。

```
┌─────────────────┬──────────────┐
│                 │ 侧边栏 UI    │ ← PySide6 无焦点置顶窗（不抢微信焦点）
│   微信窗口       │ 会话 / 消息  │
│                 │ AI 建议回复  │
└─────────────────┴──────────────┘
        ↑ win32 贴边跟随         ↓ HTTP / WebSocket (127.0.0.1:8765)
┌────────────────────────────────────────┐
│  Python 后端（唯一碰微信的进程）         │
│  FastAPI + SQLite + Adapter 抽象层      │
│  adapters/wxauto_adapter（微信 3.9）    │
│  adapters/mock_adapter（演示数据）      │
└────────────────────────────────────────┘
```

## 技术栈

Python 3.10+（本机 3.14.7）｜ PySide6 6.12.0（UI）｜ FastAPI 0.151 + uvicorn（后端）｜ SQLite（标准库，零运维）｜ DeepSeek / OpenAI 兼容 API

> 完整规范见 [`CLAUDE.md`](./CLAUDE.md)（本项目唯一规范，所有开发会话必须遵循）。

## 快速开始

```powershell
# 1) 后端依赖
cd backend
python -m pip install -r requirements.txt

# 2) 可选：真实微信采集（仅支持微信 3.9.11.17，wxauto 已停止维护）
python -m pip install git+https://github.com/cluic/wxauto.git

# 3) UI 依赖
python -m pip install PySide6==6.12.0

# 4) 配置环境变量（复制后按需修改）
Copy-Item .env.example .env    # 填入 OPENAI_API_KEY 即启用真实 LLM，留空走规则兜底

# 5) 启动后端（终端 A，保持运行）
python server.py               # http://127.0.0.1:8765

# 6) 启动侧边栏 UI（终端 B）
python desktop/app.py
```

## 功能说明

| 功能 | 说明 |
|---|---|
| 连接状态页 | 后端未启动 / 微信未运行 / 演示模式 三态清晰提示，不白屏 |
| 会话列表 | 实时会话 + 未读红点，点击切换 |
| 消息展示 | 按 `friend / self / sys / time / recall` 五类气泡渲染 |
| 生成回复 | 调 DeepSeek（OpenAI 兼容），可加"补充要求"；失败自动降级规则模板 |
| 一键填入 | 只填入微信输入框，不回车（发送前可手改） |
| 发送 | 填入并回车；**3 秒幂等**，连点不会重复发送 |
| 贴边跟随 | win32 无焦点贴附微信右侧，拖动/最大化自动跟随 |
| 实时监听 | 默认关闭；开启后新消息自动出现在侧边栏 |

## 环境变量（`.env`，全部可选）

| 变量 | 默认 | 说明 |
|---|---|---|
| `OPENAI_API_KEY` | 空 | DeepSeek Key；留空走本地规则模板兜底 |
| `OPENAI_BASE_URL` | `https://api.deepseek.com/v1` | OpenAI 兼容地址 |
| `OPENAI_MODEL` | `deepseek-chat` | 模型名 |
| `SIDEBAR_PORT` | `8765` | 后端端口 |
| `SIDEBAR_TITLE` | `WeChat Sidebar` | 侧边栏窗口标题（贴边靠它找窗口，改名需同步） |
| `SIDEBAR_ADAPTER` | `auto` | `auto` / `wxauto` / `mock` |
| `SIDEBAR_WIDTH` | `380` | 侧边栏宽度 |

## 当前状态（重要）

- **本机微信为 4.1.15.13，而已装 wxauto 仅支持 3.9.11.17 → 当前自动运行在 mock（演示数据）模式**
- mock 模式下完整业务闭环（选会话 → 读消息 → 生成 → 填入/发送 → 落库）均可验证
- 真实微信采集需按 `CLAUDE.md §7.4` 新增 4.x Adapter（架构已预留，UI 与业务代码零改动）

## 验证

```powershell
# 后端接口全量验证（真实 HTTP）
python ../_verify_e2e.py flow      # 主流程 9 项
python ../_verify_e2e.py boundary  # 边界 8 项（含重复发送幂等）
```

最新结果见 [`docs/验证报告.md`](./docs/验证报告.md)；截图在 `docs/screenshots/`。

## 合规提醒

个人微信自动化违反《微信个人账号使用规范》，存在限制功能或封号风险。本项目仅限
本机自用与技术学习，请勿用于群发、营销或任何商业用途。生产场景请走企业微信官方侧边栏 API。
