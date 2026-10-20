# IM 侧边栏助手（QQ 版）

贴在 **QQ** 窗口右侧的无焦点浮窗：读取消息 → 大模型生成建议回复 → 人工确认后一键填入 / 发送。

**形态**：独立进程 + 独立窗口跟随 IM 窗口（不注入、不修改 QQ 进程）。

```
┌─────────────────┬──────────────┐
│                 │ 侧边栏 UI    │ ← PySide6 无焦点置顶窗（不抢 IM 焦点）
│   QQ 窗口        │ 消息 / AI 建议│
│                 │ 一键填入/发送 │
└─────────────────┴──────────────┘
        ↑ win32 贴边跟随         ↓ HTTP / WebSocket (127.0.0.1:8765)
┌────────────────────────────────────────┐
│  Python 后端（打包后内嵌在同一 exe）      │
│  FastAPI + SQLite + Adapter 抽象层      │
│  adapters/qq_adapter（QQ NT，默认）      │
│  adapters/wxauto_adapter（微信 3.9）     │
│  adapters/mock_adapter（演示数据）       │
└────────────────────────────────────────┘
```

## 技术栈

Python 3.10+（本机 3.14.7）｜ PySide6 6.12.0（UI）｜ FastAPI 0.151 + uvicorn（后端）｜ SQLite（标准库，零运维）｜ DeepSeek / OpenAI 兼容 API

> 完整规范见 [`CLAUDE.md`](./CLAUDE.md)（本项目唯一规范，所有开发会话必须遵循）。

## 直接用打包好的 exe（推荐）

```powershell
# 1) 把 .env 放到 exe 旁边（配 DeepSeek Key；不配也能用，走规则兜底）
Copy-Item .env dist\.env

# 2) 双击 dist\SidebarIM.exe
```

后端已内嵌在 exe 里，双击即用，**不需要另开终端跑服务**。日志在 `dist\logs\app.log`，数据在 `dist\data\sidebar.db`。
未签名 → Windows SmartScreen 会提示"未知发布者"，选"更多信息 → 仍要运行"。

## 从源码运行

```powershell
# 1) 后端依赖
cd backend
python -m pip install -r requirements.txt

# 2) UI 依赖
python -m pip install PySide6==6.12.0

# 3) 配置（可选，留空走规则兜底）
Copy-Item .env.example .env    # 填入 OPENAI_API_KEY

# 4) 启动后端（终端 A）
python server.py               # http://127.0.0.1:8765

# 5) 启动侧边栏 UI（终端 B）
python desktop/app.py
```

## 重新打包

```powershell
python -m pip install PyInstaller
python -m PyInstaller packaging/build.spec --noconfirm --clean
# 产物 dist/SidebarIM.exe（约 55MB，单文件，不签名）
```

## 功能说明

| 功能 | 说明 |
|---|---|
| 连接状态页 | 后端未启动 / QQ 未运行 / 演示模式 三态清晰提示，不白屏 |
| 消息展示 | 按 `friend / self / sys / time / recall` 五类气泡渲染 |
| 生成回复 | 调 DeepSeek（OpenAI 兼容），可加"补充要求"；失败自动降级规则模板 |
| 一键填入 | 粘贴到 QQ 输入框，**不回车**（发送前可手改） |
| 发送 | 粘贴并回车；**3 秒幂等**，连点不会重复发送 |
| 贴边跟随 | win32 无焦点贴附 QQ 右侧，拖动/最大化自动跟随（已真机验证） |
| 实时监听 | 默认关闭；开启后新消息自动出现在侧边栏 |

## QQ 模式的能力边界（重要）

QQ NT 9.9.31 的窗口是 Chromium + D3D 渲染（实测：UIA 元素仅 2 个、子窗口仅 1 个 D3D 面），
**读不到会话列表和消息文本**，所以走**半自动**方案（不注入、不 Hook、不读 QQ 本地数据库）：

| 能力 | 实现 |
|---|---|
| 读消息 | **读剪贴板** —— 在 QQ 里选中对方的话 Ctrl+C，侧边栏刷新即可看到 |
| 会话列表 | 不可读 → 显示单个"QQ 当前窗口"，发送目标 = 当前激活的聊天窗口 |
| 填入 | 写剪贴板 → 激活 QQ → Ctrl+V（不回车） |
| 发送 | 填入 + Enter（**会真发消息，必须人工点击**） |

## 环境变量（`.env`，全部可选）

| 变量 | 默认 | 说明 |
|---|---|---|
| `OPENAI_API_KEY` | 空 | DeepSeek Key；留空走本地规则模板兜底 |
| `OPENAI_BASE_URL` | `https://api.deepseek.com/v1` | OpenAI 兼容地址 |
| `OPENAI_MODEL` | `deepseek-chat` | 模型名 |
| `SIDEBAR_PORT` | `8765` | 后端端口 |
| `SIDEBAR_TITLE` | `WeChat Sidebar` | 侧边栏窗口标题（贴边靠它找窗口，改名需同步） |
| `SIDEBAR_ADAPTER` | `qq` | `qq` / `wxauto` / `mock` / `auto` |
| `SIDEBAR_TARGET_CLASS` | 空 | 贴边目标窗口类名（微信 3.9 填 `WeChatMainWndForPC`） |
| `SIDEBAR_TARGET_TITLE` | `QQ` | 贴边目标窗口标题（类名找不到时按标题匹配） |
| `SIDEBAR_WIDTH` | `380` | 侧边栏宽度 |

## 验证

```powershell
python ../_verify_e2e.py flow      # 主流程（真实 HTTP）
python ../_verify_e2e.py boundary  # 边界（含重复发送幂等）
python ../_verify_qq.py read       # QQ 链路：状态/会话/剪贴板读消息
python ../_verify_qq.py fill      # QQ 真机粘贴（不发送）
python ../_verify_dock.py          # 贴边跟随真机验证（真实窗口几何）
```

最新结果见 [`docs/验证报告.md`](./docs/验证报告.md)；截图在 `docs/screenshots/`。

## 合规提醒

个人 IM 自动化违反《QQ 软件许可协议》/《微信个人账号使用规范》，存在限制功能或封号风险。
本项目仅限**本机自用与技术学习**，请勿用于群发、营销或任何商业用途。
生产场景请走企业微信 / QQ 官方机器人 API。
