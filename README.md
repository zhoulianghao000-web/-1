# 微信侧边栏外挂（WeChat Sidebar）

贴在微信窗口右侧的无焦点浮窗：读取当前会话 → LLM 生成建议回复 → 一键填入微信输入框 / 直接发送。

**形态：独立进程 + 独立窗口跟随微信（不注入、不修改微信进程）。**

```
┌─────────────────┬──────────────┐
│                 │  侧边栏 UI   │  ← 无焦点置顶窗（Tauri / pywebview）
│   微信窗口       │  会话/消息   │
│                 │  AI 建议回复 │
└─────────────────┴──────────────┘
        ↑ win32 跟随位置          ↓ HTTP/WebSocket
┌────────────────────────────────────────┐
│  Python 后端（唯一碰微信的进程）         │
│  adapters/wxauto_adapter.py（真实微信） │
│  adapters/mock_adapter.py（演示数据）    │
└────────────────────────────────────────┘
```

## 目录

| 路径 | 说明 |
|---|---|
| `backend/server.py` | FastAPI 服务（REST + WS），端口 8765 |
| `backend/adapters/` | 采集/发送抽象层：`base.py`（接口）+ `wxauto_adapter.py`（真实）+ `mock_adapter.py`（演示） |
| `backend/services/ai.py` | LLM 建议回复（OpenAI 兼容接口，未配置时规则兜底） |
| `backend/services/docker.py` | win32 贴边跟随 + `WS_EX_NOACTIVATE` 无焦点 + Z 序补偿 |
| `backend/launcher.py` | 无 Rust 时的启动器：uvicorn + pywebview |
| `web/` | Vite + React + TS 侧边栏 UI |
| `src-tauri/` | Tauri 2 外壳（需 rustup） |

## 运行方式

### A. 立刻能跑（不需要 Rust）

```powershell
cd backend
python -m pip install -r requirements.txt
python -m pip install git+https://github.com/cluic/wxauto.git   # 可选，真实微信模式
python launcher.py
```

> npm 若拦截了 esbuild 的安装脚本（新版 npm 默认行为），vite build 会失败，手动补一次：
> `node node_modules/esbuild/install.js`

用 pywebview（Edge WebView2）开窗，窗口标题 `WeChat Sidebar`，启动后自动贴到微信右侧。

### B. Tauri 壳（界面更精致，需先装 Rust）

```powershell
winget install Rustlang.Rustup   # 装完重开终端
npm install                      # 根目录
npm --prefix web install
npm run tauri dev                # 会自动拉起 vite dev server
```

> 打包需要图标：把一张 1024×1024 PNG 放到任意位置后执行 `npm run tauri icon <png路径>`。
> 当前 `tauri.conf.json` 里 `bundle.active = false`，开发模式不需要图标。

## 前置条件（真实微信模式）

- Windows 10/11，**微信 PC 版 3.9.11.17**（wxauto 强绑定该版本，且已停止维护）
- 系统缩放 **100%**，微信窗口非最小化、未被遮挡
- 已登录微信，且窗口处于可交互状态

不满足时后端**自动降级为 mock 模式**，UI 照常可用（顶部显示"演示数据"）。

## 环境变量

| 变量 | 默认 | 说明 |
|---|---|---|
| `OPENAI_API_KEY` | 空 | 留空则用本地规则模板兜底 |
| `OPENAI_BASE_URL` | `https://api.openai.com/v1` | 可填 DeepSeek / 通义 / 本地 Ollama 等兼容地址 |
| `OPENAI_MODEL` | `gpt-4o-mini` | 模型名 |
| `SIDEBAR_PORT` | `8765` | 后端端口 |
| `SIDEBAR_TITLE` | `WeChat Sidebar` | 侧边栏窗口标题（贴边靠它找窗口） |
| `SIDEBAR_ADAPTER` | `auto` | `auto` / `wxauto` / `mock` |

## API

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/api/status` | 适配器模式、微信是否运行、贴边状态 |
| GET | `/api/sessions` | 会话列表 |
| GET | `/api/messages?who=张三` | 指定会话最近消息 |
| POST | `/api/reply` | `{who, instruction, messages}` → `{reply, source}` |
| POST | `/api/fill` | 只填入微信输入框，不回车 |
| POST | `/api/send` | 填入并回车发送 |
| POST | `/api/dock` | `{on: true}` 开启/关闭贴边跟随 |
| POST | `/api/listen` | 实时监听开关（⚠️ 见下） |
| WS | `/ws/messages` | 监听开启时推送新消息 |

## 三个必须知道的坑

1. **焦点争夺**：侧边栏一旦抢到键盘焦点，粘贴就会贴到自己身上。所以侧边栏被设成
   `WS_EX_NOACTIVATE`（点击不激活），代价是**侧边栏内的键盘输入可能拿不到焦点**——
   第一版交互以"点击按钮 + 编辑建议文本"为主，需要在侧边栏大量打字时再放开这个限制。
2. **实时监听会把微信拉到前台**：wxauto 的 `GetNextNewMessage()` 内部会
   `DoubleClick` 聊天图标并切换会话，轮询时微信会不停抢焦点。**默认关闭**，需要时再开。
3. **wxauto 已停止维护且只支持微信 3.9**：所有对 wxauto 的耦合都关在
   `backend/adapters/wxauto_adapter.py` 里，将来换 4.x 方案（wechatauto-replica / 自写 UIA）
   只需新增一个 Adapter，UI 与业务代码不动。

## 合规提醒

个人微信自动化违反《微信个人账号使用规范》，存在限制功能或封号风险。本项目仅用于
本机自用与技术学习，请勿用于群发、营销或任何商业用途。生产场景请走企业微信官方侧边栏 API。
