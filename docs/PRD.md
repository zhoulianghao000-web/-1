# PRD — 微信侧边栏外挂（PySide6 桌面 UI）

> 版本 v0.1 ｜ 依据：`CLAUDE.md`（唯一规范）+ 已验证可用的后端接口
> 适用：`desktop/`（PySide6 6.12.0）｜ 后端 `http://127.0.0.1:8765`
>
> **适配说明**：本项目是 Windows 桌面单窗口应用（宽 380px，贴附微信右侧），**没有 URL 路由**。
> 本 PRD 中的"页面"= `QStackedWidget` 的一个视图，**"路径"字段填写的是视图 ID**，与 Web URL 等价物。

---

## 1. 后端能力清单（已验证，前端直接照抄，不要再问后端）

统一信封（**所有接口一律 HTTP 200**，业务错误看 `code`）：

```json
{ "code": 0, "message": "ok", "data": { }, "ts": 1792490854 }
```

| 接口 | 方法 | 请求 | 响应 `data` 字段 |
|---|---|---|---|
| `/api/status` | GET | 无 | `mode`(wxauto\|mock) `ok` `detail` `nickname` `wechat_version` `wechat_running` `docking` `docking_error` `listen` `current` `steals_foreground` |
| `/api/sessions` | GET | 无 | `sessions[]`：`name` `time` `content` `isnew` |
| `/api/messages` | GET | query `who`, `limit`(1-200,默认60) | `who`, `messages[]`：`type`(friend\|self\|sys\|time\|recall) `sender` `content` `id` |
| `/api/reply` | POST | `{who, instruction, messages?}` | `who` `reply` `source`(llm:xxx\|rule) `degraded` `error?` |
| `/api/fill` | POST | `{who, text}` | `ok` `detail` |
| `/api/send` | POST | `{who, text}` | `ok` `detail` |
| `/api/dock` | POST | `{on, width?}` | `docking` `error` |
| `/api/listen` | POST | `{on}` | `listen` |
| `/ws/messages` | WS | — | 推送 `{type:"new", data:{ "<会话名>": [消息对象...] }}`，仅 `listen=true` 时推送 |

**错误码**：`2001` 未选择会话 ｜ `4001` 参数错误 ｜ `1000` 微信不可用 ｜ `1001` 读取消息失败 ｜ `3001` 大模型失败 ｜ `5000` 内部错误

真实样例（可直接用于 mock 前端）：

```jsonc
// GET /api/status
{"code":0,"message":"ok","data":{"ok":true,"mode":"mock","nickname":"演示账号",
 "wechat_version":null,"detail":"未检测到微信/wxauto，当前为演示数据",
 "wechat_running":false,"docking":false,"docking_error":null,"listen":false,
 "current":null,"steals_foreground":false},"ts":1792490854}

// GET /api/messages?who=zhangsan&limit=3
{"code":0,"message":"ok","data":{"who":"zhangsan","messages":[
 {"type":"self","sender":"我","content":"在的，你说","id":"mock-zhangsan-0"},
 {"type":"friend","sender":"张三","content":"上次那个报价单能再便宜点吗？","id":"mock-zhangsan-1"}]},"ts":1792490870}

// POST /api/reply  {"who":"zhangsan","instruction":""}
{"code":0,"message":"ok","data":{"who":"zhangsan","reply":"收到，我这边跟进一下，有进展第一时间同步你。",
 "source":"rule","degraded":false},"ts":1792490879}

// POST /api/fill  {"who":"zhangsan","text":"  "}
{"code":4001,"message":"text 不能为空","data":null,"ts":1792490886}
```

---

## 2. 页面清单

| 视图 ID | 用途 | 类比路径 | 优先级 |
|---|---|---|---|
| `V0.connect` | 连接状态页：后端未就绪 / 微信未运行 / 降级 mock 时的兜底页 | `/connect` | P0 |
| `V1.main` | 主功能页：选会话 → 看消息 → 生成建议 → 填入/发送 | `/` （默认页） | P0 |
| `V2.settings` | 设置页：LLM 配置、窗口宽度、适配器模式 | `/settings` | **P1（需先补接口，见 §8）** |
| `V3.quick_replies` | 话术库页：常用话术的查看与插入 | `/quick-replies` | **P1（需先补接口，见 §8）** |

窗口通用规格：宽 380px（可配置）、高度跟随微信窗口、无边框、置顶、**点击不抢焦点**（`Qt.WindowDoesNotAcceptFocus` + `WS_EX_NOACTIVATE`）。

---

## 3. 页面详细规格

### V0 `connect` — 连接状态页

**用途**：后端不可达或环境不满足时，给用户明确的状态和下一步动作，避免白屏。

**元素**

| 元素 | 类型 | objectName | 内容 | 行为 |
|---|---|---|---|---|
| 状态图标 | QLabel | `lblIcon` | ● 绿/黄/红三色圆点 | 绿=wxauto 已连；黄=mock 演示；红=后端不可达 |
| 状态标题 | QLabel | `lblTitle` | 见下方状态映射表 | 单行，超长省略 |
| 状态详情 | QLabel | `lblDetail` | `data.detail` | 换行显示，最多 3 行 |
| 环境提示 | QLabel | `lblHint` | 静态文案 | 见下方"环境提示文案" |
| 重试按钮 | QPushButton | `btnRetry` | 重新连接 | 点击 → 重新 `GET /api/status` |
| 继续使用按钮 | QPushButton | `btnContinue` | 仍以演示模式进入 | **仅 mock 状态可见** → 跳 `V1.main` |

**数据来源**：`GET /api/status`（每 3 秒轮询一次，仅在 V0 时轮询）

| 状态判定 | 条件 | 图标 | 标题 | `btnContinue` |
|---|---|---|---|---|
| 后端不可达 | 请求异常/超时 | 红 | 后端未启动 | 隐藏 |
| 已连真实微信 | `mode == "wxauto"` | 绿 | `已连接 {nickname}` | 隐藏（自动跳 V1） |
| 微信未运行 | `mode=="wxauto" && wechat_running==false` | 黄 | 微信未运行 | 显示 |
| 演示模式 | `mode == "mock"` | 黄 | 演示数据 | 显示 |

**环境提示文案**（`lblHint`，固定文本）：
> 前置条件：微信 PC 版 3.9.11.17 已登录、系统缩放 100%、窗口未最小化。
> 启动后端：在 `backend/` 目录执行 `python server.py`

**跳转**：`status.code==0 && mode=="wxauto" && wechat_running==true` → 自动切 `V1.main`；其余停留 V0，用户可点"仍以演示模式进入"。

**错误处理**：请求超时 3s → 红点 + "后端未启动"；连续失败不弹窗，仅更新文案（避免打断）。

---

### V1 `main` — 主功能页（默认页）

**用途**：核心闭环。选会话 → 读消息 → 生成建议 → 填入/发送。

#### 3.1 顶部状态条

| 元素 | 类型 | objectName | 内容 | 行为 |
|---|---|---|---|---|
| 昵称/标题 | QLabel | `lblNickname` | `data.nickname` 或 "微信侧边栏" | 超长省略 |
| 模式徽标 | QLabel | `lblMode` | `已连微信` / `演示数据` | `mode=="wxauto"`→绿底；`mock`→黄底 |
| 设置按钮 | QToolButton | `btnSettings` | ⚙ | → `V2.settings`（P1 未开放时置灰并 tooltip "后续开放"） |
| 话术按钮 | QToolButton | `btnQuick` | 💬 | → `V3.quick_replies`（同上） |

状态条下方（**仅 `mode=="mock"` 或 `wechat_running==false` 时显示**）一条提示条 `bannerNotice`：黄底，文案取自 `data.detail`。

#### 3.2 会话区

| 元素 | 类型 | objectName | 内容 |
|---|---|---|---|
| 区域标题 | QLabel | `lblSessionTitle` | "会话" |
| 刷新按钮 | QToolButton | `btnRefreshSession` | ↻ → 重新 `GET /api/sessions` |
| 会话列表 | QListWidget（横向 chip 样式） | `listSessions` | 每项 = `data.sessions[]` |

列表项渲染规则：
- 文本：`name`（`name` 为 null 时显示 `(未知会话)`）
- 有新消息（`isnew == true`）→ 名称后加红点
- 副标题/tooltip：`{time} {content}`
- 选中项高亮（绿底白字）；`data.current` 对应的项默认选中

#### 3.3 消息区

| 元素 | 类型 | objectName | 内容 |
|---|---|---|---|
| 消息列表 | QListWidget / QScrollArea | `listMessages` | 每项 = `data.messages[]` |
| 空态 | QLabel | `lblMsgEmpty` | "暂无消息"（列表为空时显示） |

气泡渲染规则（按 `type`）：

| `type` | 对齐 | 气泡样式 | 显示内容 |
|---|---|---|---|
| `friend` | 左 | 深灰底 | 上方小字 `sender`，下方 `content` |
| `self` | 右 | 绿底白字 | `content` |
| `sys` / `time` / `recall` | 居中 | 无气泡，灰小字 | `content` |

`content` 需 `setWordWrap(True)`；`sys/time/recall` 不显示 `sender`。

#### 3.4 回复区（底部固定）

| 元素 | 类型 | objectName | 占位/初始值 | 行为 |
|---|---|---|---|---|
| 补充要求输入 | QLineEdit | `inputInstruction` | "补充要求（可留空）：如 委婉拒绝" | 用户可编辑 |
| 生成按钮 | QPushButton | `btnGenerate` | "生成回复" | → `POST /api/reply` |
| 建议回复框 | QTextEdit | `editReply` | "点【生成回复】，结果会在这里，可手动改" | 可编辑 |
| 来源标签 | QLabel | `lblSource` | `来源：{source}` | `source=="rule"` 时显示"（规则兜底）" |
| 填入按钮 | QPushButton | `btnFill` | "填入" | → `POST /api/fill` |
| 发送按钮 | QPushButton | `btnSend` | "发送" | → `POST /api/send` |
| 贴边开关 | QPushButton（可切换） | `btnDock` | "贴边（开/关）" | → `POST /api/dock` |
| 监听开关 | QPushButton（可切换） | `btnListen` | "实时监听（开/关）" | → `POST /api/listen` |
| 提示条 | QLabel | `lblToast` | 底部浮层，2.6s 自动消失 | 成功绿 / 失败红 |

按钮启用规则：`btnFill` / `btnSend` 在 `editReply` 为空（strip 后）时 `setEnabled(False)`；`btnGenerate` 在请求中禁用并显示"生成中"。

#### 3.5 数据来源汇总（V1）

| UI 元素 | 接口 | 取数路径 |
|---|---|---|
| `lblNickname` / `lblMode` / `bannerNotice` / 两个开关的初态 | `GET /api/status` | `nickname` `mode` `detail` `docking` `listen` |
| `listSessions` | `GET /api/sessions` | `sessions[].name/.isnew/.time/.content` |
| `listMessages` | `GET /api/messages?who={name}&limit=60` | `who` `messages[].type/.sender/.content/.id` |
| `editReply` | `POST /api/reply` | `reply`；`lblSource` ← `source` |
| `lblToast` | `/api/fill` `/api/send` `/api/dock` `/api/listen` | `detail` / `docking` / `listen` |
| 消息增量 | `WS /ws/messages` | `data.{会话名}[ ]` 追加到 `listMessages` |

#### 3.6 交互行为（逐步）

**A. 打开应用**
1. 窗口创建 → 立即 `GET /api/status`（异步线程）
2. `code!=0` 或请求异常 → 显示 `V0.connect`
3. `mode=="mock"` 或 `wechat_running==false` → 停留 V0（用户点"仍以演示模式进入"进 V1）
4. 正常 → 切 `V1.main`，同时发 `GET /api/sessions` 和 `GET /api/messages`（`who` 取 `data.current`，为 null 则取 `sessions[0].name`）

**B. 点击会话项**
1. `listSessions.itemClicked` → 取 `name`
2. 若与当前 `who` 相同则不请求
3. `GET /api/messages?who={name}&limit=60`；期间 `listMessages` 显示"加载中"
4. `code==0` → 清空列表并按规则渲染气泡、自动滚到底部
5. `code==2001` → toast "未选择会话"；`code==1001` → toast "读取消息失败，检查微信窗口是否在前台"

**C. 点击【生成回复】**
1. 禁用按钮 + 文案"生成中"
2. `POST /api/reply` body `{"who": 当前会话, "instruction": inputInstruction.text(), "messages": null}`
   （`messages` 传 null = 让后端自己读最新消息，前端不必传整包）
3. `code==0` → `editReply.setText(data.reply)`；`lblSource` ← `data.source`
4. `data.degraded==true` → toast 黄字 "模型调用失败，已用规则兜底"；仍展示 `reply`
5. `code==3001` → toast 红字 "大模型调用失败"；`editReply` 保持原值
6. `code==2001` → toast "请先选择会话"
7. 无论成败，恢复按钮

**D. 点击【填入】**
1. 校验 `editReply` 非空，否则按钮本就禁用
2. `POST /api/fill` body `{"who": 当前会话, "text": editReply.text()}`
3. `code==0` → toast 绿字 `data.detail`
4. `code==4001` → toast "内容不能为空"；`code==5000` → toast "填入失败：{message}"
5. **不改 UI 数据**（填入只是把文本放进微信输入框，不发消息）

**E. 点击【发送】**
1. 同上校验 → `POST /api/send` body `{"who","text"}`
2. `code==0` → toast 绿字 `data.detail`；**延迟 800ms** 后重新 `GET /api/messages?who=` 刷新列表（让发出的消息显示出来）
3. 失败码处理同 D

**F. 开关【贴边】**
1. 读当前 `data.docking` 状态，取反
2. `POST /api/dock` body `{"on": !docking, "width": 380}`
3. 成功 → 更新按钮文案"贴边（开/关）"；失败 → 回滚按钮态 + toast

**G. 开关【实时监听】**
1. 取反 → `POST /api/listen` body `{"on": !listen}`
2. 开启成功 → 建立 `WS /ws/messages` 连接；关闭 → 断开 WS
3. 收到 WS 帧 `{type:"new", data:{chat:[msgs]}}` → 若 `chat == 当前会话` 则追加气泡到 `listMessages` 并滚到底；否则仅更新该会话 chip 的红点
4. 开启时 toast 提示"实时监听已开启（微信可能被拉到前台）"
5. WS 断开 → 自动重连，间隔 5s，最多 3 次；仍失败则 toast "推送连接中断" 并关闭监听开关

**H. 点击【会话刷新】**：重新 `GET /api/sessions`，重绘列表，保持当前选中项。

---

### V2 `settings` — 设置页（P1，接口待补）

**用途**：在 UI 内改 LLM 配置与窗口参数，不用手改 `.env` 重启。

| 元素 | 类型 | objectName | 内容 | 目标字段 |
|---|---|---|---|---|
| 返回按钮 | QToolButton | `btnBack` | ← | → `V1.main` |
| API Key | QLineEdit（密码模式） | `inputApiKey` | `OPENAI_API_KEY` | settings |
| Base URL | QLineEdit | `inputBaseUrl` | `OPENAI_BASE_URL` | settings |
| 模型名 | QLineEdit | `inputModel` | `OPENAI_MODEL` | settings |
| 窗口宽度 | QSpinBox(300-600) | `spinWidth` | `SIDEBAR_WIDTH` | settings |
| 适配器 | QComboBox(`auto`/`wxauto`/`mock`) | `cmbAdapter` | 当前值 | settings |
| 保存按钮 | QPushButton | `btnSave` | 保存 | `PUT /api/settings` |
| 结果提示 | QLabel | `lblSaveToast` | — | — |

> ⚠️ **阻塞项**：`CLAUDE.md §4` 目前**没有** settings 读写接口，数据模型 §6.4 有 `settings` 表。
> 按 §7.5「契约先行」，**必须先更新 CLAUDE.md §4 增加 `GET/PUT /api/settings` 并实现后端，前端才可开工**。
> 在接口就绪前，V2 的入口按钮 `btnSettings` 置灰 + tooltip「后续开放」。

---

### V3 `quick_replies` — 话术库页（P1，接口待补）

**用途**：点一条话术，直接把文本塞进 `editReply`（不自动发送）。

| 元素 | 类型 | objectName | 内容 |
|---|---|---|---|
| 返回按钮 | QToolButton | `btnBack` | ← → `V1.main` |
| 分类筛选 | QComboBox | `cmbTag` | 全部 / `tag` 去重列表 |
| 话术列表 | QListWidget | `listQuick` | 每项 = `content`，副标题 `tag` |
| 插入按钮 | QPushButton | `btnInsert` | 插入到回复框 → 把 `content` 写入 `V1.editReply` 并跳回 `V1.main` |

> ⚠️ **阻塞项**：同上，`quick_replies` 表已建（种子 3 条），但 **无 HTTP 接口**。
> 需先为 `CLAUDE.md §4` 增加 `GET /api/quick-replies`；在接口就绪前 `btnQuick` 置灰。

---

## 4. 页面跳转逻辑

```
启动
 └─> V0.connect ──(status.code==0 且 mode=="wxauto" 且 wechat_running==true)──> V1.main
        │                                                                          │
        └─(点"仍以演示模式进入")──────────────────────────────────────────────────┘
V1.main ──btnSettings──> V2.settings ──btnBack──> V1.main
V1.main ──btnQuick──────> V3.quick_replies ──btnInsert──> V1.main（并填充 editReply）
```

触发条件表：

| 起点 | 触发 | 条件 | 终点 | 附带动作 |
|---|---|---|---|---|
| 启动 | — | — | V0 | 轮询 status |
| V0 | `status` 全绿 | `mode==wxauto && wechat_running` | V1 | 拉 sessions + messages |
| V0 | `btnContinue` | `mode==mock` | V1 | 同上 |
| V0 | `btnRetry` | 任意 | V0 | 重新 status |
| V1 | `btnSettings` | 接口已就绪 | V2 | 加载设置 |
| V1 | `btnQuick` | 接口已就绪 | V3 | 加载话术 |
| V2 | `btnBack` | — | V1 | 若有未保存改动 → toast 提示"未保存"（不拦截） |
| V3 | `btnInsert` | 选中一项 | V1 | 写入 `editReply` |
| V1 | status 轮询发现后端失联 | 连续 2 次失败 | V0 | 保留当前会话状态 |

---

## 5. 交互行为总则

1. **所有网络请求放子线程**（`QThread` / `QThreadPool`），结果通过 `Signal(dict)` 回主线程改 UI，禁止子线程直接操作控件（CLAUDE.md §7.4）。
2. **超时**：status 3s，其余接口 10s，LLM 生成 30s（后端自身 30s）。
3. **请求中态**：按钮禁用 + 文案变化；消息区/会话区显示"加载中"，不弹模态框。
4. **错误统一走 toast**，不弹 `QMessageBox`（抢焦点会破坏"不抢焦点"约束）。
5. **错误码 → 文案**：

| code | toast 文案 | 颜色 |
|---|---|---|
| 0 | `data.detail` 或 "操作成功" | 绿 |
| 1000 | 微信不可用，请启动微信 3.9 后重试 | 红 |
| 1001 | 读取消息失败：确认微信窗口在前台、缩放 100% | 红 |
| 2001 | 请先选择一个会话 | 红 |
| 3001 | 大模型调用失败 | 红 |
| 4001 | `data.message`（如"text 不能为空"） | 红 |
| 5000 | 操作失败：{message} | 红 |
| 网络异常 | 后端未连接，请在 backend/ 执行 python server.py | 红 |
| `degraded==true` | 模型失败，已用规则兜底（仍可发送） | 黄 |

6. **重试**：仅 `btnRetry` 与"会话刷新"提供手动重试；不自动重试写操作（fill/send），避免重复发送。
7. **焦点铁律**：任何交互后**不得**调用 `activateWindow()` / `raise_()` / `setFocus()`；toast 用 `Qt.ToolTip` 风格的浮层（`Qt.WindowDoesNotAcceptFocus`），不用 `QMessageBox`。

---

## 6. 全局窗口约束（所有页面通用）

| 项 | 要求 |
|---|---|
| 窗口 flag | `Qt.FramelessWindowHint \| Qt.Tool \| Qt.WindowStaysOnTopHint \| Qt.WindowDoesNotAcceptFocus` |
| 额外 win32 样式 | `WS_EX_NOACTIVATE \| WS_EX_TOOLWINDOW`（由 `services/docker.py` 施加） |
| 尺寸 | 宽 380（可配置），高跟随微信窗口 |
| 位置 / Z 序 | 由后端 `docker.py` 线程按窗口标题 `WeChat Sidebar` 跟随，**前端不要自己 move/resize** |
| 样式 | 深色：`#0f1115` 背景、`#161a21` 面板、`#07c160` 主色；字号 13px |
| 滚动条 | 隐藏横向滚动条，纵向细样式 |

---

## 7. 不做的事（与 CLAUDE.md §7「非目标」严格一致）

1. **不做自动发送**：任何页面不得出现"自动回复""收到即发""定时群发"开关；发送只能由人点【发送】触发。
2. **不做多账号 / 多开 / 多用户 / 登录页 / 权限页**：无登录视图、无账号切换、无用户管理。
3. **不做云端化页面**：无部署页、无远程配置、无 Web 控制台、无移动端适配、不显示服务器地址配置（后端固定 `127.0.0.1:8765`）。
4. **不做微信 4.x 相关 UI**：无版本切换、无协议/注入方式选择、无"切换采集引擎"入口（`cmbAdapter` 仅 `auto/wxauto/mock`）。
5. **不做 RAG / 知识库 / 插件 / 多轮记忆 / 图片语音识别 / 消息搜索**：无搜索框、无附件上传、无知识库管理页、无插件页。
6. **不做**会话删除、消息删除、导出、统计报表、聊天分析等次要功能页。

---

## 8. 接口缺口（阻塞 P1，需先改 CLAUDE.md 再实现）

| 缺失接口 | 建议定义 | 阻塞页面 |
|---|---|---|
| `GET /api/settings` | → `data: {key: value}` | V2 |
| `PUT /api/settings` | ← `{key, value}` → `data: {key, value}` | V2 |
| `GET /api/quick-replies` | → `data: {items:[{id,tag,content,sort}]}` | V3 |

按 CLAUDE.md §7.5，这三接口**必须先写入 §4 再实现**；未写入前前端**不得**调用，对应入口置灰。

---

## 9. 验收对照（对应 CLAUDE.md §11，须真人手动验）

| # | 验收项 | 对应 PRD 位置 |
|---|---|---|
| 1 | 新消息 3s 内出现（开启监听） | §3.6 G |
| 2 | 点生成 5s 内出建议 | §3.6 C |
| 3 | 点发送后消息出现在微信 | §3.6 E |
| 4 | **点侧边栏后打字进微信输入框**（未抢焦点） | §6 全局窗口约束 |
| 5 | 拖/最大化/最小化微信，侧边栏跟随 | §6（由 docker.py 负责，前端不干预） |
