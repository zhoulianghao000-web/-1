# CLAUDE.md — 微信侧边栏外挂 项目规范

> **本文件是本项目唯一规范。任何开发会话开始前必须完整阅读本文件。**
> - 与本文件冲突的实现，以本文件为准。
> - 修改本文件前必须先向用户确认，不得自行改动。
> - 新增任何接口、表、环境变量，必须**先写进本文件，再写代码**（契约先行）。
> - 不确定时先问，不要自作主张扩展功能（尤其见 §7「非目标」）。

---

## 0. 技术栈已确定

| 位置 | 选型 | 版本 |
|---|---|---|
| 前端（桌面 UI 壳） | **PySide6**（Qt 6 官方 Python 绑定，LGPLv3） | `6.12.0` |
| 后端 | **FastAPI** + **uvicorn** | `0.151.0` / `0.54.0` |
| 数据库 | **SQLite**（Python 标准库 `sqlite3`，单文件） | `data/sidebar.db` |
| AI/LLM | **DeepSeek `deepseek-chat`**，OpenAI 兼容 `/chat/completions` | 见 §9 |

---

## 1. 项目概述

- **名称**：WeChat Sidebar（微信侧边栏外挂）
- **一句话描述**：贴在 Windows 微信窗口右侧的无焦点浮窗，接收微信消息交给大模型生成回复建议，人工确认后一键填入或发送。
- **目标用户**：本机自用、有 Python 基础但**不写前端/后端**的个人使用者；用于学习 Windows UI 自动化 + LLM 应用。
- **核心功能（仅 3 条，超出即属违规）**
  1. **收**：读取当前微信会话的最近消息（可选开启实时监听）
  2. **想**：调用大模型生成一条可直接发送的中文回复建议（LLM 不可用时规则兜底）
  3. **发**：一键填入微信输入框，或填入并回车发送（**必须人工点击**）

---

## 2. 技术栈表（版本已锁定，不得随意升级）

| 层 | 技术 | 锁定版本 | 备注 |
|---|---|---|---|
| 运行时 | Python | `3.14.7`（本机，最低兼容 3.10） | PySide6 6.12 为 `cp310-abi3` wheel，3.14 可装 |
| UI | PySide6 | `6.12.0` | 已废弃 React/Vite/Tauri/Rust，见 §7 |
| Web 框架 | FastAPI | `0.151.0` | |
| ASGI 服务器 | uvicorn | `0.54.0` | 仅本地回环 `127.0.0.1` |
| HTTP 客户端 | httpx | `0.28.1` | 调 LLM 用，超时 30s |
| 微信采集 | wxauto / **4.x Adapter（待实现）** | `39.2.1` | wxauto **不在 PyPI**，从 GitHub 源码安装；**仅支持微信 3.9.11.17**，对本机 4.1.15.13 无效 |
| Windows API | pywin32 | `312` | 窗口句柄、贴边、无焦点 |
| 数据库 | SQLite | 内置（Python 3.14 自带 sqlite3） | 不装任何数据库服务 |
| ORM | 不使用 | — | 直接写 SQL；SQLModel 属**未批准**依赖，需先改本文档 |
| LLM | DeepSeek | `deepseek-chat` | OpenAI 兼容协议 |
| 打包 | PyInstaller | **待安装，版本未锁定** | MVP 阶段不做打包，直接源码运行 |

**已废弃（下个任务删除，不得再修改）**：`web/`（React + Vite）、`src-tauri/`（Tauri 2 壳）、`backend/launcher.py`（pywebview 启动器）。

---

## 3. 目录结构（核心文件）

```
wechat-sidebar/
├─ CLAUDE.md                      ← 本文件，唯一规范
├─ backend/
│  ├─ server.py                   FastAPI 应用：路由 + 生命周期（已实现）
│  ├─ schemas.py                  【待建】统一响应信封 + Pydantic 模型
│  ├─ db.py                       【待建】SQLite 连接、建表、查询封装
│  ├─ config.py                    【待建】环境变量集中读取
│  ├─ adapters/
│  │  ├─ base.py                  Adapter 抽象基类（已实现）
│  │  ├─ wxauto_adapter.py        真实微信实现（已实现）
│  │  ├─ mock_adapter.py          演示数据实现（已实现）
│  │  └─ __init__.py              create_adapter() 工厂 + 降级逻辑（已实现）
│  ├─ services/
│  │  ├─ ai.py                    LLM 调用 + 规则兜底（已实现）
│  │  └─ docker.py                win32 贴边跟随 + 无焦点 + Z 序补偿（已实现，复用）
│  └─ requirements.txt
├─ desktop/                         【待建】PySide6 UI
│  ├─ app.py                      入口：创建窗口 + 事件循环
│  ├─ window.py                   SidebarWindow（无边框/置顶/不抢焦点）
│  ├─ widgets.py                  会话列表 / 消息区 / 回复区
│  └─ api_client.py               封装 §4 全部 HTTP 接口
├─ data/
│  └─ sidebar.db                   SQLite（首次启动自动创建）
├─ docs/
│  └─ 技术选型调研.md              选型决策依据
├─ web/                            【废弃】待删除
└─ src-tauri/                      【废弃】待删除
```

---

## 4. API 接口定义

前缀 `/api`，后端监听 `127.0.0.1:8765`。所有响应统一使用 §5 信封。

### 4.1 `GET /api/status` — 运行状态
请求体：无
响应 `data`：
```json
{
  "mode": "wxauto | mock",
  "ok": true,
  "detail": "已连接微信（张三）",
  "nickname": "张三",
  "wechat_version": "3.9.11.17",
  "wechat_running": true,
  "docking": true,
  "docking_error": null,
  "listen": false,
  "current": "文件传输助手",
  "steals_foreground": true
}
```

### 4.2 `GET /api/sessions` — 会话列表
请求体：无
响应 `data`：`{ "sessions": [ { "name": "张三", "time": "14:32", "content": "在吗", "isnew": true } ] }`
- `name` string|null、`time` string|null、`content` string|null、`isnew` boolean

### 4.3 `GET /api/messages` — 读取消息
Query：`who`（string，可选，缺省用当前会话）、`limit`（int，默认 60，1–200）
响应 `data`：
```json
{
  "who": "张三",
  "messages": [
    { "type": "friend", "sender": "张三", "content": "在吗？", "id": "42-12345" }
  ]
}
```
- `type` 枚举：`friend` / `self` / `sys` / `time` / `recall`
- 副作用：会把 `state.current` 设为 `who`

### 4.4 `POST /api/reply` — 生成建议回复
请求体：
```json
{
  "who": "张三",
  "instruction": "委婉拒绝，但保留合作余地",
  "messages": [{ "type": "friend", "sender": "张三", "content": "在吗" }]
}
```
- `who` string|null、`instruction` string（可空）、`messages` array|null（**传 null 时后端自行读取该会话消息**）
响应 `data`：
```json
{ "who": "张三", "reply": "在的，你说～", "source": "llm:deepseek-chat | rule", "degraded": false }
```
- `degraded=true` 表示 LLM 失败已降级为规则模板，此时 `data.error` 附带原因

### 4.5 `POST /api/fill` — 只填入输入框（不发送）
请求体：`{ "who": "张三", "text": "在的" }`
响应 `data`：`{ "ok": true, "detail": "已填入输入框：张三" }`

### 4.6 `POST /api/send` — 填入并回车发送
请求体：`{ "who": "张三", "text": "在的" }`
响应 `data`：`{ "ok": true, "detail": "已发送：张三" }`

### 4.7 `POST /api/dock` — 贴边跟随开关
请求体：`{ "on": true, "width": 380 }`（`width` 可选）
响应 `data`：`{ "docking": true, "error": null }`

### 4.8 `POST /api/listen` — 实时监听开关
请求体：`{ "on": false }`
响应 `data`：`{ "listen": false }`
> 开启后后端会周期性调用 wxauto，可能把微信拉到前台。**默认关闭**。

### 4.9 `WS /ws/messages` — 新消息推送
仅在 `listen=true` 时推送：`{ "type": "new", "data": { "张三": [ {…消息对象} ] } }`

### 4.10 幂等规则（防重复发送）
适用于 `POST /api/send` 与 `POST /api/fill`：
- **3 秒内**相同 `{who, text}` 视为重复提交，**不重复执行**发送/填入，直接返回上次结果
- 响应 `data` 增加 `duplicated: true`（首次为 `false`），`code` 仍为 `0`，UI 提示"已发送（忽略重复点击）"
- 实现：进程内 `{(who, text): (ts, result)}` 缓存，TTL 3 秒，不需要持久化
- 代价：3 秒内"故意连发两条相同内容"会被拦截 —— MVP 阶段优先防误触，接受该代价

---

## 5. 统一响应格式

**HTTP 状态码一律 200**（业务错误用 `code` 表达），仅 422/500 用于框架级异常。

**成功模板**
```json
{
  "code": 0,
  "message": "ok",
  "data": { },
  "ts": 1760000000
}
```

**错误模板**
```json
{
  "code": 2001,
  "message": "未选择会话",
  "data": null,
  "ts": 1760000000
}
```

**错误码表**

| code | 含义 | 处理建议 |
|---|---|---|
| 0 | 成功 | — |
| 1000 | 微信不可用 / wxauto 初始化失败 | 提示启动微信 3.9，或切 mock |
| 1001 | 读取消息失败 | 检查微信窗口是否前台、缩放 100% |
| 2001 | 未选择会话 | 前端先让用户选会话 |
| 3001 | LLM 调用失败（已降级规则模板） | `code` 仍为 0 时表示降级成功；失败则 3001 |
| 4001 | 参数错误 | 前端校验 |
| 5000 | 内部错误 | 记录日志 |

> ⚠️ **已知欠债**：现有 `backend/server.py` 仍返回裸 dict（`{sessions:[...]}`、`{reply,source}` 等），**未按信封包装**。
> 迁移 PySide6 UI 时**第一步就是新增 `backend/schemas.py` 把所有接口套上信封**，UI 侧只认信封。

---

## 6. 数据模型（SQLite）

建表 SQL 由 `backend/db.py` 在首次启动时执行（`CREATE TABLE IF NOT EXISTS`）。时间统一存 **UTC ISO8601 字符串**。

### 6.1 `chats` — 会话
| 字段 | 类型 | 约束 | 说明 |
|---|---|---|---|
| `chat_key` | TEXT | PRIMARY KEY | 会话唯一标识（微信昵称/备注名） |
| `name` | TEXT | NOT NULL | 显示名 |
| `last_msg_at` | TEXT | | 最后一条消息时间（UTC） |
| `unread` | INTEGER | NOT NULL DEFAULT 0 | 未读数 |
| `updated_at` | TEXT | NOT NULL DEFAULT CURRENT_TIMESTAMP | |

### 6.2 `messages` — 消息
| 字段 | 类型 | 约束 | 说明 |
|---|---|---|---|
| `id` | TEXT | PRIMARY KEY | wxauto 的 RuntimeId；mock 为 `mock-<chat>-<n>` |
| `chat_key` | TEXT | NOT NULL, FK→`chats.chat_key` | 所属会话 |
| `sender` | TEXT | | 发送者显示名 |
| `type` | TEXT | NOT NULL, CHECK(`type` IN ('friend','self','sys','time','recall')) | 消息类型 |
| `content` | TEXT | | 文本内容 |
| `msg_ts` | TEXT | | 消息时间（UTC，来自消息解析） |
| `created_at` | TEXT | NOT NULL DEFAULT CURRENT_TIMESTAMP | 入库时间 |

索引：`CREATE INDEX IF NOT EXISTS idx_messages_chat_ts ON messages(chat_key, msg_ts DESC);`
去重：写入用 `INSERT OR IGNORE`（靠 `id` 主键去重）。

### 6.3 `quick_replies` — 话术库
| 字段 | 类型 | 约束 | 说明 |
|---|---|---|---|
| `id` | INTEGER | PRIMARY KEY AUTOINCREMENT | |
| `tag` | TEXT | NOT NULL | 分类标签 |
| `content` | TEXT | NOT NULL | 话术正文 |
| `sort` | INTEGER | NOT NULL DEFAULT 0 | 排序 |
| `created_at` | TEXT | NOT NULL DEFAULT CURRENT_TIMESTAMP | |

### 6.4 `settings` — 配置
| 字段 | 类型 | 约束 | 说明 |
|---|---|---|---|
| `key` | TEXT | PRIMARY KEY | 如 `llm_model`、`sidebar_width` |
| `value` | TEXT | | 字符串形式存储 |

---

## 7. 架构约束与非目标

### 必须遵守的规则（5 条）

1. **采集层只能走 Adapter**：UI 与业务代码**禁止直接 import wxauto / pywin32**。所有微信读写必须经 `backend/adapters/` 的 `BaseAdapter` 实现；换微信 4.x 方案时只新增一个 Adapter。
2. **只有后端进程碰微信**：UI（PySide6）只能通过 §4 的 HTTP 接口通信，不得自己操作微信窗口/句柄。
3. **侧边栏必须"点击不抢焦点"**：窗口必须带 `WS_EX_NOACTIVATE`（win32）+ `Qt.WindowDoesNotAcceptFocus`。**禁止**在主窗口上调用 `activateWindow()` / `raise_()` / `setFocus()`，也禁止任何"自动聚焦"逻辑——一旦抢焦点，粘贴会打到侧边栏自己身上。
4. **PySide6 子线程禁止直接操作控件**：跨线程更新 UI 必须走信号槽（`Signal` → 主线程槽函数）；网络请求、轮询放在 `QThread`。
5. **契约先行**：新增接口/表/环境变量，必须先更新本文件（§4/§6/§9）再写代码；响应一律用 §5 信封。

### 本阶段不做的事（5 条 —— 违反即为自作主张）

1. **不做全自动无人值守回复**：所有发送必须由人点击触发。禁止"收到消息自动发送""定时群发""自动加好友"。
2. **不做多账号 / 多开 / 多用户 / 权限**：单微信实例、单用户、单机。
3. **不做云端化**：不部署服务器、不打包 Docker、不做 Web 控制台、不做移动端、不做远程访问。
4. **不做注入 / Hook / 协议逆向，MVP 阶段也不实现 4.x 采集代码**：只用 UI 自动化。
   - 本机真实微信版本为 **4.1.15.13**（`C:\Program Files\Tencent\Weixin`），已装 wxauto 只支持 3.9.11.17，**对 4.x 无效**
   - 因此 MVP 全程跑 **mock 模式**；真机验收（§11）需先补 4.x Adapter（候选：`wechatauto-replica`），
     架构已由 `adapters/base.py` 预留，**新增一个 Adapter 即可，UI 与业务代码不动**
   - 4.x 采集代码在"能登录微信并实测"之前不得写入仓库（无法验证的代码不入库）
5. **不做 RAG / 知识库 / 插件系统 / 多轮长期记忆 / 图片语音识别 / 消息全文检索 UI**：MVP 只有"收 → 想 → 发"。

---

## 8. 启动命令

```powershell
# 1) 安装依赖（后端）
cd backend
python -m pip install -r requirements.txt

# 2) 安装 wxauto（不在 PyPI，必须从源码装）
python -m pip install git+https://github.com/cluic/wxauto.git

# 3) 安装 UI
python -m pip install PySide6==6.12.0

# 4) 启动后端（终端 A，保持运行）
cd backend
python server.py                      # http://127.0.0.1:8765
#   等价：uvicorn server:app --host 127.0.0.1 --port 8765

# 5) 启动侧边栏 UI（终端 B）
python desktop/app.py
```

**前置条件**：Windows 10/11、微信 PC 版已登录、**系统缩放 100%**、窗口非最小化。
本机微信为 **4.1.15.13**，而已装 wxauto 只支持 3.9.11.17 → **当前必然降级 mock 模式**
（UI 顶部显示"演示数据"），**不算启动失败**，全部功能闭环仍可验证。

开发期调试 UI 可单独跑：`python desktop/app.py`（后端未启动则 UI 显示"后端未连接"）。

---

## 9. 环境变量清单

| 变量 | 默认值 | 必填 | 说明 |
|---|---|---|---|
| `OPENAI_API_KEY` | 空 | 否 | DeepSeek 的 API Key；**留空则走规则模板兜底**，功能仍可用 |
| `OPENAI_BASE_URL` | `https://api.deepseek.com/v1` | 否 | OpenAI 兼容地址，可换 DeepSeek/通义/Ollama |
| `OPENAI_MODEL` | `deepseek-chat` | 否 | 模型名 |
| `SIDEBAR_PORT` | `8765` | 否 | 后端端口，UI 的 `api_client.py` 需与之对应 |
| `SIDEBAR_TITLE` | `WeChat Sidebar` | 否 | 侧边栏窗口标题，**`docker.py` 靠它找窗口句柄，改名需同步** |
| `SIDEBAR_ADAPTER` | `auto` | 否 | `auto` / `wxauto` / `mock`；`mock` 强制演示数据 |
| `SIDEBAR_TARGET_CLASS` | `WeChatMainWndForPC` | 否 | 贴边跟随的**目标 IM 窗口类名**（微信 3.9） |
| `SIDEBAR_TARGET_TITLE` | 空 | 否 | 目标窗口标题；类名找不到时按标题匹配（换 QQ/微信 4.x 时用，不改代码） |
| `SIDEBAR_WIDTH` | `380` | 否 | 侧边栏宽度（px） |
| `SIDEBAR_DB` | `../data/sidebar.db` | 否 | SQLite 文件路径（相对 `backend/`） |
| `SIDEBAR_LOG_LEVEL` | `INFO` | 否 | 日志级别 |

---

## 10. 当前状态与下一步（每次会话开工前先看这里）

**已完成**：
- 后端：`server.py` / `schemas.py` / `config.py` / `db.py` / `adapters/`（含 mock 降级）/ `services/ai.py` / `services/docker.py`
- 后端 9 接口全部按 §5 信封返回，已通过真实 HTTP 验证（9/9），见 `docs/验证报告.md`
- 清理：`src-tauri/`、`package.json`、`backend/launcher.py`、`web/` 已全部删除（备份在 `_backup/`）
- 前端：`desktop/` 骨架 + `V0.connect`（加载/错误/正常三态已验证）

**待办（按顺序）**：
1. 开发 `V1.main`（PRD §3）：会话区 / 消息区 / 回复区 / 贴边+监听开关（T1–T6）
2. 修复重复发送：前端请求中禁用按钮 + 后端 3 秒幂等（T7，接口见 §4.10）
3. 人工验收 §11 的 5 条标准（**需真机 4.x Adapter + 已登录微信**，当前阻塞）

**QQ 探测结论（2026-10-20）**：本机 QQ NT 9.9.31（`C:\Program Files\Tencent\QQNT\QQ.exe`）
窗口类名 `Chrome_WidgetWin_1`，**UIA 子树只有 2 个元素、子窗口只有 1 个 `Intermediate D3D Window`**
→ 内容全靠 D3D 渲染，**读不到会话/消息文本**，因此 QQ 不能替代微信做完整闭环验证，
仅可用于验证「贴边跟随 / 窗口存在与位置」（T11 第 5 条）。

## 11. 验收标准（必须真人手动验证，AI 无法自测）

1. 微信收到新消息 → 开启监听后 3 秒内出现在侧边栏
2. 点"生成回复" → 5 秒内出现建议文本
3. 点"发送" → 消息确实出现在微信会话中
4. **点侧边栏任意位置后直接打字，字进的是微信输入框**（= 未抢焦点，本项目成败线）
5. 拖动 / 最大化 / 最小化微信 → 侧边栏跟随且不遮挡

---

## 12. 风险与合规

- wxauto 已停止维护且绑死微信 3.9.11.17（已用 Adapter 隔离，换方案只需新增一个 Adapter）
- 个人微信自动化违反《微信个人账号使用规范》，**存在限制功能或封号风险**；本项目仅限本机自用与技术学习，**严禁商业使用**
- LLM 输出不可信：回复必须人工确认后再发送
