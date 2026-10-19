# douyin-relay：浏览器页面收弹幕，管理页保持不变

日期：2026-10-19  
状态：已确认  
范围：`plugins/douyin-relay`

## 背景

管理页、登录、监督器和映射已经可用。无头 Node 直接连接弹幕服务器仍然失败。

实测房间 `492518529474`：

- `frontierSign` 已加载，`signatureLength` 为 16。
- 弹幕主机是 `webcast100-ws-web-lq.douyin.com`，路径是 `/webcast/im/push/v2/`。
- WebSocket 升级状态码是 200，约 300 毫秒后关闭码 1006。8 秒内没有弹幕帧。
- `/webcast/im/fetch/` 在 Node 里返回 HTTP 200 且正文长度为 0。
- 管理页上的再次连接来自手动操作，不是 2、5、10 秒自动重连。

重构前弹幕可用。当时 `index.html` 在浏览器里加载 `/mssdk.js`，进房请求走 Vite 的 `/dylive`，弹幕 WebSocket 走 Vite 的 `/socket`，再转到 `wss://webcast100-ws-web-lq.douyin.com`。Cookie 由 Vite 代理加到上游请求上。浏览器脚本不能设置 `Cookie` 头。

## 取代范围

连接传输以本文为准。下面这些条款被取代：

- `2026-10-16-douyin-relay-fusion-design.md`：连接不再启动 Vite；`connect` 在进程内用 Node 直连 `https://live.douyin.com`。
- `2026-10-19-douyin-headless-signature-design.md`：不恢复 Vite，不把连接搬回浏览器页面；空正文时用固定 `pushServer` 让 `DyCast` 直连 `wss://webcast100-ws-web-lq.douyin.com`。

仍然保留：

- Python 管理页是用户唯一要打开的界面。不恢复 Vue 控制台，也不提供打开它的入口。
- 开播探测仍用现在的 Node 请求。
- 登录仍用原来的浏览器 profile。收弹幕用另一个无界面浏览器，不占用这份 profile。
- 监督器仍只看 `state`。`connect_failed` 不重连。`im_fetch_failed` 仍按 2、5、10、30、60 秒重连。
- 映射、礼物连击和注入不改。

融合规格里的手工验收「不会打开 dycast Vite 页面」改成：用户不打开 Vite 页面。引擎可以在 `127.0.0.1:5173` 拉起 Vite。

## 目标

用户仍只使用现在的管理页。点击连接后，弹幕由一个无界面浏览器页面接收，帧仍进入现有解码和注入。出现 `open` 并且收到弹幕后，管理页阶段变为已连接。还没 `open`，或 `open` 之后还没收到任何弹幕就结束时，停在「错误」，不自动改回 Node 直连。

## 非目标

- 不恢复 dycast 的 Vue 控制台，管理页不提供打开它的入口。
- 不让用户填写转发地址。
- 不把登录用的浏览器 profile 同时用于收弹幕。
- 不连接 `frontier-im.douyin.com` 或 `frontier-pc.douyin.com`。
- 不改映射、礼物连击和注入。
- 不把已经收到过弹幕之后的断开改成停止重连。那种 `closed` 仍按原退避重连。

## 方案

保留 Python 管理页和现有标准输入输出协议。只有 `connect` 改到浏览器页面。探测开播仍用现在的 Node 请求。

| 方案 | 结论 |
|------|------|
| 管理页不变，Vite 只托管一个无界面收弹幕页，浏览器发出进房请求和 WebSocket | **采用** |
| 继续用 Node 的 `fetch` 和 `ws` 直连弹幕服务器 | 不采用。16 位签名下升级仍是 HTTP 200 |
| 把用户界面退回 dycast Vue 控制台 | 不采用。管理页、登录和监督器会拆开 |

## 连接

引擎进程仍由现在的 `headless.ts` 启动。它再在 `127.0.0.1:5173` 拉起 Vite，主机必须是 `127.0.0.1`，不能沿用现有配置里的 `0.0.0.0`。进程退出时关掉 Vite 和收弹幕浏览器。浏览器使用本机已安装的 Chrome 或 Edge，依赖现有的 `playwright-core`，不下载 Playwright 自带的 Chromium。

收弹幕页是新的 `cast-host.html`。在任何模块脚本之前写 `<script src="/mssdk.js"></script>`，与 `index.html` 相同。不加载 Vue。Playwright 打开 `http://127.0.0.1:5173/cast-host.html`，使用单独的无界面浏览器，不使用登录 profile。

连接前把当前 Cookie POST 到已有的 `/__api/dycast/upstream-headers`，请求体是 `{ "raw": "<cookie>" }`。`/dylive` 和 `/socket` 代理把这份 Cookie 加到上游。页面和这次连接的 Node 路径都不调用 `setUpstreamOrigin`。进房请求留在页面来源下的 `/dylive`，由浏览器发出。

收弹幕页上的弹幕 WebSocket 一律连页面来源的 `/socket/webcast/im/push/v2/`。不要因为 `pushServer` 非空就改成 `wss://` 直连。上游 `im/fetch` 没有返回真实 `pushServer` 时，收弹幕页不得使用无头签名方案里的固定主机构造直连地址；空正文可以保留本地 `cursor` 和 `internalExt`，但 `pushServer` 留空。Vite 的 `/socket` 在没有单独指定主机时，仍转到 `wss://webcast100-ws-web-lq.douyin.com`。上游返回了真实 `pushServer` 时，只把它交给 Vite，用来决定 `/socket` 的转发目标，页面地址仍然是 `/socket/webcast/im/push/v2/`。

`connect` 不再调用 Node 里的 `DyCast.connect`。`cast-host.html` 导入现有 `DyCast` 并调用 `connect`，`maxReconnectCount` 为 0，`strictIm` 为 true。Playwright 用 `exposeFunction` 或等价桥，把页面里的 `open`、`message`、`error`、`close` 送回现有无头路由：

- `open` 写成一条 `status`，`state` 为 `connected`。只有这一条表示已经连上。
- `message` 写成原来的 `messages` 行。
- 还没有 `open` 时的 `error` 或 `close`，合成一条 `status`，`state` 为 `connect_failed`。不要依赖浏览器里不存在的 `Unexpected server response` 文案，也不要再报一条 `closed`。
- `empty_signature` 同样是 `connect_failed`。
- `im/fetch` 请求抛错仍是 `im_fetch_failed`，上报 `closed`，按原规则重连。空正文不是这种错误。

`disconnect` 关闭页面里的 `DyCast`，并上报 `disconnected`。

## 失败

还没有 `open`，就上报一次 `connect_failed`。监督器进入「错误」，清掉到期任务，不再发 `connect`。

已经 `open`，但还没有收到任何弹幕就关闭，包括现有的无帧关闭，也上报一次 `connect_failed`，不再重连。

已经收到过至少一条弹幕之后的 `closed`，仍按 2、5、10、30、60 秒重连。

同一次失败不要改回 Node 直连，也不要改重连间隔。找不到本机 Chrome 或 Edge 时，上报 `connect_failed`。不要静默改走 Node WebSocket。

## 验证

单测：

- `connect` 打开的是 `cast-host.html`，不是 Node 里的 `DyCast.connect`。
- Cookie 会 POST 到 `/__api/dycast/upstream-headers`。
- 页面不调用 `setUpstreamOrigin`。
- `im/fetch` 正文为空时，页面里的弹幕地址是 `ws://127.0.0.1:5173/socket/webcast/im/push/v2/`，不是 `wss://webcast100-ws-web-lq.douyin.com/webcast/im/push/v2/`。
- 还没有 `open` 的 `close`，路由只写出一条 `connect_failed`。

手工：用当前配置的房间从管理页连接一次。通过标准是阶段变为已连接，并且收到至少一条已映射文本。还没连上，或连上后没有弹幕就结束时，阶段变为「错误」，监督器不再发出 `connect`。不打印 Cookie、URL 查询串和弹幕正文。
