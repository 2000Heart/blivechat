# douyin-relay：无头进房签名与弹幕地址

日期：2026-10-19  
状态：已确认  
范围：`plugins/douyin-relay`

## 背景

网页打开直播间时弹幕正常。重构前插件也可用。重构后无头引擎在「连接中」和「重连中」之间循环。

实测房间 `492518529474`：

- 直播页状态为开播，Cookie 能打开 `/webcast/room/web/enter/`。
- `/webcast/im/fetch/` 返回 HTTP 200 且正文长度为 0，没有 `pushServer`。
- 无头进程没有浏览器地址。`danmakuWebSocketUrl('', null)` 返回 `null`，连接以关闭码 4002、原因 `empty_push_server` 结束。
- `LiveSupervisor` 把 `closed` 排进 2、5、10、30、60 秒重连。
- `public/mssdk.js` 在 `vm` 里执行后，`frontierSign` 挂在虚拟机全局对象上。现有沙箱把 `window` 设成另一个对象，读取时得到空的 `byted_acrawler`。`getSignature()` 退回 188 位 `a_bogus`。用它握手时服务端返回 HTTP 200，不是 101。
- 把虚拟机全局对象同时当作 `window` 后，`frontierSign` 是函数，`X-Bogus` 长度为 16。

## 目标

无头引擎使用 `mssdk.js` 的 `frontierSign` 签名，并在 `im/fetch` 没有返回弹幕地址时连到固定弹幕服务器。已经连上之后的异常断开仍按原退避重连。签名为空，或握手没有升级成功时，停在一次失败，不再自动重连。

## 非目标

- 不恢复 Vite，不把进房改回 `BrowserDycastConnector`。
- 不连接 `frontier-im.douyin.com` 或 `frontier-pc.douyin.com`。那是私信和端上长连接，不是直播弹幕。
- 不把空的 `im/fetch` 当成登录失效。401、403、通行证地址和登录页仍走原有登录失效规则。
- 不改映射、礼物连击和注入。

## 方案

修无头引擎，不把连接搬回浏览器页面。

| 方案 | 结论 |
|------|------|
| 修正 `vm` 全局对象，空弹幕地址回退到 `webcast100-ws-web-lq.douyin.com` | **采用** |
| 每次连接用 Playwright 打开 Vite 页面 | 不采用。进程模型和重构目标都会倒退 |
| 只借浏览器算签名，请求仍由 Node 发出 | 不采用。签名和请求再次分开 |

## 签名

抽出 `loadMssdkFrontier`。它创建 `vm` 沙箱时让 `window`、`self` 和 `globalThis` 都指向沙箱自身，再执行 `public/mssdk.js`。成功后沙箱上的 `byted_acrawler.frontierSign` 必须是函数。

`ensureCastRuntime` 和 `ensureNodeRuntime` 都调用这个函数，并把 `frontierSign` 赋给 `__dy_frontierSign`。`public/mssdk.js` 不存在，或加载后没有 `frontierSign` 时，两个调用方都不抛错，`getSignature()` 继续走原来的回退。文件存在且 `frontierSign` 可用时，`getSignature()` 对固定房间号返回 16 位字符串，不再返回 188 位 `a_bogus`。

## 弹幕地址

`im/fetch` 正文长度为 0，或解码后没有 `pushServer`、`cursor`、`internalExt` 时，`getImInfo` 返回本地回退值，包括：

- 现有格式的 `cursor` 和 `internalExt`
- `pushServer` 为 `webcast100-ws-web-lq.douyin.com`

`strict === true` 时，请求抛错仍抛 `im_fetch_failed`；`UpstreamAuthError` 仍原样抛出。空正文不是这两种错误。

这取代 `2026-10-16-douyin-relay-fusion-design.md` 里「`getImInfo` 失败不得再伪造 cursor」的条款。该条款只约束请求抛错。空正文或三个字段都缺失时允许使用上面的本地回退。

`danmakuWebSocketUrl` 在没有 `pushServer`、也没有浏览器地址时，返回 `wss://webcast100-ws-web-lq.douyin.com/webcast/im/push/v2/`。已有浏览器地址时，仍返回该地址下的 `/socket/webcast/im/push/v2/`，供 Vite 开发页使用。

## 失败状态

`dycast.ts` 的 WebSocket `error` 监听必须把 `ErrorEvent.message` 原样交给 `error` 事件。现在它只发出 `Error(ev.type)`，正文固定是 `error`，`Unexpected server response: 200` 到不了路由。

无头路由在关闭码分支之前识别错误文案。文案是 `empty_signature`，或包含 `Unexpected server response` 时，只上报一次 `state=connect_failed`。同一次关闭码 1005 或 1006 不得再报 `closed`。不能把所有 1005 都当成 `connect_failed`：已经连上之后的异常断开也会收成 1005，那种 `closed` 仍要退避重连。

这取代融合规格里「`empty_signature` 走异常重连」的条款。`empty_signature` 不再重连。监督器只看 `state`，不看 `error` 字符串：`state=closed` 且 `error=empty_signature` 仍会重连，所以路由不得再把签名失败上报成 `closed`。`im_fetch_failed` 仍按原规则重连。

`LiveSupervisor.on_cast_status('connect_failed')` 把阶段设为 `error`，清掉到期任务，不返回命令。已经进入 `connected` 之后的 `closed` 仍按原退避重连。登录失效规则不变。

管理页已有阶段文案「错误」，不新增文案。

## 验证

- 单元测试覆盖签名函数、空弹幕地址、空进房正文和 `connect_failed` 不再重连。
- 用当前配置的房间，在已有插件进程之外实际连接一次。通过标准是 `signatureLength` 为 16、WebSocket 升级状态码为 101，并且 8 秒内至少收到一帧。这次连接看不到监督器阶段，不要求阶段变为 `connected`。握手仍是 HTTP 200，或帧数为 0 时停止，不继续改重连间隔。
