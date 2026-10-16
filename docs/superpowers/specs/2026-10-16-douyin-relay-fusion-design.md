# douyin-relay：无界面引擎与网页管理

日期：2026-10-16  
状态：已按审阅修订  
范围：`plugins/douyin-relay`

## 背景与目标

当前插件把内置 dycast 当作转发层：Vite 拉起整套页面，dycast 连上抖音后再把 JSON 推到插件本地 WebSocket，Python 才做映射和注入。用户要填转发地址，或依赖 sidecar 去连那条 WebSocket。管理界面是 PySide6 窗口。

未开播时 `DyCast.connect()` 在打完进房请求后发出 `LIVE_END`（4001）并停止，不会再试。准备中、暂停、已下播都走这个关闭码。WebSocket 异常关闭时引擎自己最多重连 20 次、间隔 1 秒，次数用尽只报错。Cookie 失效后同样停住，必须重启插件。

**目标**

1. 用户只面对插件管理页。不再填写 WebSocket，不再打开 dycast 页面，不再提供外部 dycast 转发。
2. 协议解码仍用现有 JavaScript 引擎。消息经子进程标准输出进入 Python，再走现有映射与注入。
3. 管理页用浏览器打开，包含连接、过滤、最近弹幕和运行日志。弹幕列表只展示已映射的文本，不做完整直播预览。
4. 配置好房间号并完成首次登录后，开播、下播、断线和普通 Cookie 续期自动恢复。只有登录态彻底失效时才需要再点一次「登录抖音」。

**非目标**

- 不把抖音协议迁进 Python，不去掉 Node 进程。
- 不删除 dycast 的 Vue 源码；本版只是不再启动它，管理页也不提供打开入口。
- 不自动弹出浏览器。静默续期失败时只在管理页提示。
- 等待开播期间不做完整进房（不请求 `im/fetch`，不建弹幕 WebSocket）。
- Node 进程崩溃后本版不自动拉起。管理页显示已停止，由用户点「重启引擎」。
- 管理页不提供小书签，也不再提供「复制小书签链接」和书签说明。手动往输入框粘贴 Cookie 仍可用。

Cookie 登录的阶段语义沿用 `2026-10-16-douyin-cookie-auto-login-design.md`：静默与交互共用同一浏览器 profile，进入 `running` 前占坑，离开 `running` 前先关掉浏览器并释放 profile 锁，Cookie 短于 200 字符不写入，写入仍走原子替换。该文里的 HTTP 控制接口、「dycast 控制台作为管理界面」和小书签由本文替换。该文「连房运行中不做 Cookie 失效恢复」由本文的「每个失效周期静默续期一次，确认仍在播后再重连」替换；仍不自动弹窗。

## 方案

采用无界面 Node 进程加 Python 管理页。

| 方案 | 结论 |
|------|------|
| 无界面引擎，标准输入输出传命令和事件，Python 提供管理页 | **采用** |
| 继续用 Vite，只把转发地址藏起来 | 转发层还在，且 `/dylive` 代理会留下来 |
| 管理页放在 Node，Python 只注入 | 配置、Cookie 与 blcsdk 被拆开 |

## 结构

```text
用户点「管理」
    → 浏览器打开 http://127.0.0.1:<admin_port>/admin

Python 插件
    ├─ 管理页、监督循环（等待开播 / 需要登录只存在于这里）
    ├─ mapper / 去重 / injector → blcsdk
    └─ 子进程：tsx dycast/src/sidecar/headless.ts
           标准输入：一行一个命令 JSON
           标准输出：一行一个协议 JSON
           标准错误：引擎日志原文
```

新增 `dycast/src/sidecar/headless.ts`。依赖增加 `tsx`，并为 `@/` 配置与 Vite 相同的路径别名。工作目录为 `dycast/`，以便读取 `public/mssdk.js`。

headless 直接在 Node 里调用现有解码，不启动 Vite，不使用 `BrowserDycastConnector`，不使用 `RelayCast`，也不再要求 `relayUrl`。`SidecarEngine.connect()` 不能原样复用：它强制要转发地址，并会打开 Vite 页面。

`probe_live` 由 headless 用自带 Cookie 罐请求 `https://live.douyin.com/{房间号}`。响应里的 `Set-Cookie`（含 `__ac_nonce`）必须写入罐子后再发下一次请求。解析沿用 `parseLiveHtml` 的房间状态字段。不调用 `fetchUser`，不调用 `getImInfo`。

`connect` 才在进程内创建 `DyCast`，并关闭它的内置重连（不再自己重试 20 次）。一次连接只上报一次打开、关闭、错误和关闭码。同一时刻只允许一个在途的 `probe_live` 或 `connect`。

删除 `relay_server.py`、`relay_backend`、本地转发端口、PySide6 / tkinter 窗口。`listener.py` 改为用系统浏览器打开管理页。`cookie-login-session` 的占坑与关浏览器再改阶段保留，由 headless 直接调用，不再经过 Vite 中间件。

Node 只负责连抖音和吐事件。Python 负责配置、监督、管理页、映射和注入。

## 进程协议

标准输出每行一个 JSON，写完即刷出。`CLog`、堆栈和其它引擎日志走标准错误，由 Python 收进日志环，不进入 JSON 解析。命令和日志里的 `rawHeaders`、Cookie 原文打码。无法解析的标准输出行丢掉并记一条插件日志，后续行继续处理。

每条命令带字符串 `id`。每条命令都立刻回一条结果，不等待浏览器或进房结束：

```json
{"type":"result","id":"<同一 id>","ok":true,"error":""}
```

失败时 `ok` 为 false，`error` 为稳定错误码。`login_start`、`login_cancel`、`login_status`、`login_consume` 的结果还带 `phase`、`mode`、`cookieLength`、`message`。只有 `login_consume` 成功时额外带 `cookie`。终态和弹幕用后续事件表达，事件里带回同一个 `id`（弹幕和直播间信息除外，它们属于当前连接）。Python 按 `id` 匹配，不按「下一条输出」匹配。

标准输入命令：

| cmd | 立刻结果 | 之后的事件 |
|-----|----------|------------|
| `probe_live` | 参数缺失时 `ok:false`，`error:bad_args` | `probe` |
| `connect` | 已有在途探测或连接时 `ok:false`，`error:busy` | `status`、`live_info`、`messages`、关闭 |
| `disconnect` | 取消在途探测、连接和定时器后 `ok:true` | `status:disconnected` |
| `login_start` | 立刻返回。空闲时 `ok:true` 且阶段变为 `running`，然后后台登录。已是 `running` 时 `ok:false`，`error:busy`，不得再开浏览器 | 终态 `login` |
| `login_cancel` | 立刻接受 | 阶段变为 `cancelled` 且 profile 锁释放后的 `login` |
| `login_status` | 结果内带 `phase`、`mode`、`cookieLength`、`message`，不带 Cookie | 无 |
| `login_consume` | 仅当阶段为 `done` 且尚未消费时 `ok:true`，并带 `cookie`。随后清空保存的 Cookie，阶段改为 `idle`。其它阶段 `ok:false`，`error:not_ready`，不带 Cookie | 无 |

`probe` 事件字段：`id`、`ok`、`living`、`roomStatus`。房间状态只用这些值：`1` 准备中、`2` 直播中、`3` 暂停、`4` 已下播。只有 `2` 表示 `living:true`。解析不到状态、状态不是 1–4、或页面请求失败时：`ok:false` 或 `roomStatus:unknown`，`living:false`。不得把解析失败默认成已下播。

`login` 事件字段：`id`、`phase`、`mode`、`cookieLength`、`message`。不带 Cookie 原文。阶段为 `idle`、`running`、`done`、`need_login`、`error`、`cancelled`。

连接状态由 Python 监督器命名，并通过管理页展示：`idle`、`waiting_live`、`connecting`、`connected`、`reconnecting`、`disconnected`、`need_login`、`error`。`waiting_live` 和 `need_login` 不由 DyCast 产生。

Node 进程退出时插件不退出，管理页显示引擎已停止和最后一条错误。本版不自动拉起。

## 进房与下播

`connect` 在进程内调用 `DyCast`，请求直接发往 `https://live.douyin.com`，不经过 `http://127.0.0.1:5173/dylive`。`getImInfo` 失败必须作为连接失败上报（`error:im_fetch_failed`），不得再伪造 cursor 假装成功。签名为空同样视为这次连接失败（`error:empty_signature`），这两类都不是登录态失效。

关闭含义：

| 信号 | 监督器动作 |
|------|------------|
| 探测 `roomStatus` 为 1、3、4、`unknown`，或探测 `ok:false` | 留在「等待开播」，180 秒后再探测 |
| 探测 `roomStatus` 为 2 | 发一次 `connect` |
| 连接过程中房间已不在播，关闭码 4001 | 回到「等待开播」，不走快速重连 |
| 已连接后收到场控关闭或 `PayloadType.Close`（正常关闭码 1000） | 回到「等待开播」 |
| WebSocket 异常关闭（无状态码、异常关闭、无法接收） | 按 2、5、10、30、60 秒完整重连，封顶 60 秒，插件运行期间持续重试 |
| 登录态失效（见下节） | 停止快速重连，进入续期或「需要登录」 |

DyCast 内置的 20 次重连关闭。监督器是唯一会再次 `connect` 的一方。

## 自动恢复

已配置房间号且 Cookie 可用时，插件启动后自行维持连接。管理页的连接、断开和重启用于换房间或排障。断开、重启、保存新房间号、登录终态都会取消在途命令和定时器。

1. `cookie_auto_refresh=true` 时，启动先 `login_start silent`。阶段为 `done` 且 Cookie 长度不少于 200 时原子写回 `douyin_cookie`，并用新 Cookie 继续。阶段为 `need_login`、`error`、`cancelled` 或超时时，用磁盘上已有 Cookie 继续；若没有可用 Cookie，状态为「需要登录」，不连房间。超时以 `cookie_silent_timeout_seconds` 为准。放弃前必须 `login_cancel`，并等到阶段离开 `running`、profile 锁释放，才能再发 `login_start`。`cookie_auto_refresh=false` 时启动不做静默，直接用磁盘 Cookie。
2. 有 Cookie 时发 `probe_live`。未开播则状态为「等待开播」，每 `live_probe_interval_seconds`（默认 180）秒再探测一次。探测只请求直播间页面。
3. 只有「直播中」才发一次 `connect`。
4. 直播中异常断开时按上一节的退避完整重连。
5. 下播后回到「等待开播」，下一场仍按探测间隔等待。
6. 登录态失效只认下面的稳定信号，不认「房间连接前出错」「已超过最大重连次数」或签名为空的日志：携带 Cookie 的直播间页面或 `im/fetch` 返回 401 或 403；最终页面落入登录或通行证地址；页面没有房间数据且被识别为登录页。探测失败（打不开、解析不到状态）保持「等待开播」，不算登录失效。`im_fetch_failed` 与 `empty_signature` 走异常重连，不走续期。
7. 每个登录失效周期最多静默续期一次。一次成功的 `connect` 之后，计数清零，下次失效可以再静默一次。启动静默已经失败、取消或超时的，同一次启动里的连接失败不再静默。`cookie_auto_refresh=false` 时失效后直接「需要登录」。静默成功则写回 Cookie，然后按当前状态决定下一步，不无条件 `connect`。
8. 未开播或正在等待时，登录成功只写回 Cookie，下一轮仍是 `probe_live`。连接正常时不因为续期打断当前直播。当前连接已因登录失效断开时，先探测，确认仍在播再完整重连。
9. 用户点「连接」、保存了新房间号、或点「重启引擎」：先断开并取消定时器，再从探测开始。用户点「断开」后停在断开，不再自动探测，直到再次连接或重启插件。
10. 房间号为空时不探测、不连接，管理页显示未配置房间号。

180 秒页面探测是为了避免未开播期间反复调用 `im/fetch` 和弹幕 WebSocket。完整进房只发生在确认开播之后，以及直播中的断线重连。

## 管理页

由插件内 aiohttp 提供。点击插件「管理」时，若服务已在监听，用系统浏览器新标签打开 `http://127.0.0.1:<admin_port>/admin`。这和排队机一样使用系统浏览器，端口独立。默认 `127.0.0.1:18771`（`18766` 已被数据分析插件占用，`18866` 是排队机）。

管理服务只绑定回环地址。配置的 `admin_host` 不是 `127.0.0.1` 或 `::1` 时拒绝启动管理服务并写日志。端口绑定失败时插件继续运行，不打开浏览器。

接口：

| 方法 | 路径 | 内容 |
|------|------|------|
| GET | `/admin` | 管理页 |
| GET | `/admin/snapshot` | 状态、最近 100 条弹幕、最近 200 行日志，以及当前 Cookie，供输入框显示 |
| GET | `/admin/events` | SSE：状态、新弹幕、日志。不包含 Cookie |
| POST | `/admin/action` | `save_config`、`login_start`、`login_cancel`、`connect`、`disconnect`、`restart` |

登录成功后页面重新拉取 snapshot，用其中的 Cookie 刷新输入框。登录完成本身不提交整份表单，避免用输入框里的旧 Cookie 覆盖刚刚写回的配置。

页面内容：

- **状态**：引擎是否在跑、连接状态、已发送、丢弃、队列长度、登录阶段。
- **连接**：房间号、Cookie、保存、登录抖音、取消登录、连接、断开、重启引擎。
- **过滤**：内容前缀，以及礼物、礼物样式、点赞、进场、关注。保存后作用于后续消息。
- **最近弹幕**：已映射、进入注入队列的内容，保留最近 100 条。每条包含时间、昵称、类型和文本；礼物包含名称和数量。
- **运行日志**：插件与引擎最近 200 行。

## 配置

保留：`douyin_room_id`、`douyin_cookie`、`cookie_auto_refresh`、浏览器 profile 目录、登录超时、`cookie_silent_timeout_seconds`、内容前缀、各类 `include_*`、`native_gift`、去重和注入队列。

新增：`admin_host`、`admin_port`（默认 `127.0.0.1` 与 `18771`）、`live_probe_interval_seconds`（默认 `180`）。

删除：`mode`、`relay_backend`、`listen_host`、`listen_port`、`ws_path`、`sidecar_host`、`sidecar_port`、`sidecar_start_timeout_seconds`、`sidecar_node_cmd`。Node 可执行文件仍可配置，用于启动 `tsx`。

旧配置文件里多余的键忽略，不再读取。

## 异常

- 注入队列满时丢弃并计数，管理页显示丢弃数，不堵住引擎输出。
- 关闭插件时结束 Node 进程组。
- 标准输入命令在引擎未就绪时，管理接口返回错误，页面显示失败原因。
- 引擎未就绪或 `result.ok` 为 false 时，页面显示 `error`，不把失败当成已连接。

## 验收

单元测试使用假时钟，不真等 180 秒。

- 输出行解析：合法消息进入映射，坏行被跳过。标准错误里的日志不进入 JSON 解析。
- 监督：未开播只发 `probe_live`，间隔 180 秒；`roomStatus=2` 后发一次 `connect`；准备中、暂停、已下播和解析失败都继续等待，不把解析失败当成已下播。
- 已连接后的正常关闭回到等待；异常关闭按退避完整重连；DyCast 内置 20 次重连不再发生。
- 登录态失效：本周期尚未静默过且允许自动续期时，静默一次，成功后先探测再决定是否连接。静默失败、或本周期已经静默失败，则停在需要登录，且不自动开始交互登录。
- `cookie_auto_refresh=false` 时启动不静默。静默超时会取消登录并等到离开 `running`。
- 未开播时交互登录成功只写 Cookie，不发 `connect`。
- 短 Cookie 不写入。`login_consume` 只成功一次。SSE 与日志不含 Cookie；snapshot 可以含 Cookie。
- 现有映射与礼物连击结束帧行为保持不变。

手工验收：

1. 启用插件，打开管理页。填写房间号并完成一次登录。页面没有小书签入口。
2. 未开播时页面为「等待开播」。开播后无需重启，房间页出现抖音弹幕，管理页最近弹幕和日志同时更新。
3. 下播后再开播，仍能自动连上。
4. 断开后停住；再点连接会重新探测。重启引擎后插件进程不退出。
5. 点赞默认仍不注入。
6. 页面上没有转发地址，也不会打开 dycast 的 Vite 页面。
