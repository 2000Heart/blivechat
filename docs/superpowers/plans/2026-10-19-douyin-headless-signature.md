# 无头进房签名与弹幕地址 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 无头引擎用 `mssdk.js` 的 `frontierSign` 签名，并在 `im/fetch` 没有弹幕地址时连到 `webcast100-ws-web-lq.douyin.com`；握手失败时停止自动重连。

**Architecture:** `loadMssdkFrontier` 把虚拟机全局对象同时当作 `window`。`getImInfo` 在空正文时返回固定 `pushServer` 和原有回退游标。`danmakuWebSocketUrl` 在无头环境没有地址时使用同一台服务器。握手被拒时上报 `connect_failed`，`LiveSupervisor` 进入 `error` 且不再发 `connect`。

**Tech Stack:** TypeScript（`tsx`、`node:test`）、Python 3（`unittest`）、现有 `DyCast` 与 `LiveSupervisor`。

## Global Constraints

- 不恢复 Vite，不调用 `BrowserDycastConnector`。
- 不连接 `frontier-im.douyin.com` 或 `frontier-pc.douyin.com`。
- 空的 `im/fetch` 正文不是登录失效。401、403、通行证地址和登录页仍走原规则。
- 空正文或解码后没有 `pushServer`、`cursor`、`internalExt` 时允许本地回退。这取代 `2026-10-16-douyin-relay-fusion-design.md` 里「不得再伪造 cursor」的条款。请求抛错仍是 `im_fetch_failed`，不得回退。
- `im_fetch_failed` 仍按 2、5、10、30、60 秒重连。`connect_failed` 不重连。
- `empty_signature` 改为 `connect_failed`，不再重连。这取代融合规格里「`empty_signature` 走异常重连」的条款。监督器只看 `state`：`state=closed` 且 `error=empty_signature` 仍会重连，路由不得再这样上报。
- 已进入 `connected` 之后的 `closed` 仍按原退避重连。
- DyCast 内置重连保持 `maxReconnectCount=0`。
- 不改映射、礼物连击和注入。
- 固定弹幕主机是 `webcast100-ws-web-lq.douyin.com`。
- `frontierSign` 的 `X-Bogus` 长度为 16。188 位结果是错误的 `a_bogus` 回退。

---

### Task 1: 无头环境使用固定弹幕主机

**Files:**
- Modify: `plugins/douyin-relay/dycast/src/sidecar/live-probe.ts`
- Modify: `plugins/douyin-relay/dycast/src/sidecar/live-probe.test.ts`

**Interfaces:**
- Consumes: 无
- Produces: `DEFAULT_WEBCAST_HOST = 'webcast100-ws-web-lq.douyin.com'`；`danmakuWebSocketUrl(pushServer, browserOrigin)` 在两者都空时返回 `wss://webcast100-ws-web-lq.douyin.com/webcast/im/push/v2/`

- [x] **Step 1: Write the failing test**

把 `live-probe.test.ts` 里名为 `empty push server does not become the vite socket` 的测试改成：

```typescript
test('headless empty push server uses the fixed webcast host', () => {
  assert.equal(
    danmakuWebSocketUrl('', null),
    'wss://webcast100-ws-web-lq.douyin.com/webcast/im/push/v2/',
  )
  assert.equal(
    danmakuWebSocketUrl('   ', null),
    'wss://webcast100-ws-web-lq.douyin.com/webcast/im/push/v2/',
  )
  assert.equal(
    danmakuWebSocketUrl(undefined, null),
    'wss://webcast100-ws-web-lq.douyin.com/webcast/im/push/v2/',
  )
  assert.equal(
    danmakuWebSocketUrl('webcast5-ws-web-lf.douyin.com', null),
    'wss://webcast5-ws-web-lf.douyin.com/webcast/im/push/v2/',
  )
  assert.equal(
    danmakuWebSocketUrl('wss://webcast100-ws-web-lq.douyin.com/', null),
    'wss://webcast100-ws-web-lq.douyin.com/webcast/im/push/v2/',
  )
  assert.equal(
    danmakuWebSocketUrl('', 'http://localhost:5173'),
    'ws://localhost:5173/socket/webcast/im/push/v2/',
  )
})
```

主机规范化断言原来和空地址断言在同一个 `test()` 里。上面这段替换必须带上这两条，避免整段替换把它们删掉。

- [x] **Step 2: Run test to verify it fails**

Run: `cd plugins/douyin-relay/dycast && node --experimental-strip-types --test src/sidecar/live-probe.test.ts`

Expected: FAIL，`danmakuWebSocketUrl('', null)` 实际为 `null`

- [x] **Step 3: Write minimal implementation**

在 `live-probe.ts` 导出常量，并在 `danmakuWebSocketUrl` 末尾用它代替 `return null`：

```typescript
export const DEFAULT_WEBCAST_HOST = 'webcast100-ws-web-lq.douyin.com'

export function danmakuWebSocketUrl(
  pushServer: string | null | undefined,
  browserOrigin: string | null,
): string | null {
  const server = String(pushServer || '').trim()
  if (server) {
    const host = server.replace(/^wss?:\/\//i, '').replace(/\/+$/, '')
    if (host) return `wss://${host}/webcast/im/push/v2/`
  }
  if (browserOrigin) {
    return `${browserOrigin.replace(/^http/, 'ws')}/socket/webcast/im/push/v2/`
  }
  return `wss://${DEFAULT_WEBCAST_HOST}/webcast/im/push/v2/`
}
```

- [x] **Step 4: Run test to verify it passes**

Run: `cd plugins/douyin-relay/dycast && node --experimental-strip-types --test src/sidecar/live-probe.test.ts`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add plugins/douyin-relay/dycast/src/sidecar/live-probe.ts plugins/douyin-relay/dycast/src/sidecar/live-probe.test.ts
git commit -m "fix: use fixed webcast host when headless has no push server"
```

---

### Task 2: 空进房正文返回回退游标和固定主机

**Files:**
- Modify: `plugins/douyin-relay/dycast/src/core/request.ts`
- Create: `plugins/douyin-relay/dycast/src/core/im-info-fallback.test.ts`

**Interfaces:**
- Consumes: `DEFAULT_WEBCAST_HOST` from `plugins/douyin-relay/dycast/src/sidecar/live-probe.ts`
- Produces: `getImInfo(roomId, uniqueId, strict)` 在正文为空时返回带 `pushServer`、`cursor`、`internalExt` 的对象，不抛错

- [x] **Step 1: Write the failing test**

```typescript
import assert from 'node:assert/strict'
import test from 'node:test'
import { getImInfo, setUpstreamOrigin } from './request.ts'

test('empty im body returns fallback cursor and webcast host', async () => {
  setUpstreamOrigin('https://live.douyin.com')
  const original = globalThis.fetch
  globalThis.fetch = async (input: RequestInfo | URL) => {
    const url = String(input)
    if (url.includes('/webcast/im/fetch')) {
      return new Response(new Uint8Array(), { status: 200, headers: { 'content-type': 'application/json' } })
    }
    return new Response('not-im', { status: 500 })
  }
  try {
    const info = await getImInfo('7000000000000000001', '7000000000000000002', true)
    assert.equal(info.pushServer, 'webcast100-ws-web-lq.douyin.com')
    assert.match(info.cursor || '', /_t-\d+/)
    assert.match(info.internalExt || '', /wss_push_room_id:7000000000000000001/)
  } finally {
    globalThis.fetch = original
  }
})
```

- [x] **Step 2: Run test to verify it fails**

Run: `cd plugins/douyin-relay/dycast && node ./node_modules/tsx/dist/cli.mjs --tsconfig tsconfig.sidecar.json --test src/core/im-info-fallback.test.ts`

Expected: FAIL，`pushServer` 为 `undefined`

- [x] **Step 3: Write minimal implementation**

在 `request.ts` 增加回退函数。`getImInfo` 在正文长度为 0，或解码结果没有 `pushServer`、`cursor`、`internalExt` 时调用它。`strict` 只保留给 `fetchImInfo` 抛错的分支。

```typescript
import { DEFAULT_WEBCAST_HOST } from '../sidecar/live-probe.ts'

function fallbackImInfo(roomId: string, uniqueId: string, reqMs: number): DyImInfo {
  const now = Date.now()
  return {
    cursor: `r-7497180536918546638_d-1_u-1_fh-7497179772733760010_t-${now}`,
    internalExt: `internal_src:dim|wss_push_room_id:${roomId}|wss_push_did:${uniqueId}|first_req_ms:${reqMs}|fetch_time:${now}|seq:1|wss_info:0-${now}-0-0|wrds_v:7497180515443673855`,
    pushServer: DEFAULT_WEBCAST_HOST,
  }
}
```

`getImInfo` 的成功分支改为：

```typescript
const bytes = new Uint8Array(buffer)
if (bytes.byteLength === 0) return fallbackImInfo(roomId, uniqueId, reqMs)
const res = decodeResponse(bytes)
if (!res.pushServer && !res.cursor && !res.internalExt) return fallbackImInfo(roomId, uniqueId, reqMs)
return {
  cursor: res.cursor,
  internalExt: res.internalExt,
  now: res.now,
  pushServer: res.pushServer,
  fetchInterval: res.fetchInterval,
  fetchType: res.fetchType,
  liveCursor: res.liveCursor,
}
```

删除原来 `catch` 里非 strict 时手写的那份游标，改为 `return fallbackImInfo(roomId, uniqueId, reqMs)`。strict 抛错分支保持不变。

- [x] **Step 4: Run test to verify it passes**

Run: `cd plugins/douyin-relay/dycast && node ./node_modules/tsx/dist/cli.mjs --tsconfig tsconfig.sidecar.json --test src/core/im-info-fallback.test.ts`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add plugins/douyin-relay/dycast/src/core/request.ts plugins/douyin-relay/dycast/src/core/im-info-fallback.test.ts
git commit -m "fix: fall back to a webcast host when im fetch body is empty"
```

---

### Task 3: 在虚拟机全局对象上加载 frontierSign

**Files:**
- Create: `plugins/douyin-relay/dycast/src/sidecar/mssdk-runtime.ts`
- Create: `plugins/douyin-relay/dycast/src/sidecar/mssdk-runtime.test.ts`
- Modify: `plugins/douyin-relay/dycast/src/sidecar/headless-router.ts` 的 `ensureCastRuntime`
- Modify: `plugins/douyin-relay/dycast/src/sidecar/engine.ts` 的 `ensureNodeRuntime`

**Interfaces:**
- Consumes: `public/mssdk.js`，`getSignature(roomId, uniqueId)` from `src/core/signature.js`
- Produces: `loadMssdkFrontier(mssdkPath: string): { frontierSign: (payload: Record<string, unknown>) => Record<string, unknown> }`

- [x] **Step 1: Write the failing test**

```typescript
import assert from 'node:assert/strict'
import path from 'node:path'
import test from 'node:test'
import { fileURLToPath } from 'node:url'
import { getSignature } from '../core/signature.js'
import { loadMssdkFrontier } from './mssdk-runtime.ts'

test('mssdk frontierSign returns a 16 char X-Bogus', () => {
  const mssdkPath = path.join(path.dirname(fileURLToPath(import.meta.url)), '../../public/mssdk.js')
  const { frontierSign } = loadMssdkFrontier(mssdkPath)
  ;(globalThis as { __dy_frontierSign?: typeof frontierSign }).__dy_frontierSign = frontierSign
  const direct = frontierSign({ 'X-MS-STUB': 'abc' })
  assert.equal(Object.keys(direct).includes('X-Bogus'), true)
  assert.equal(String(direct['X-Bogus'] || '').length, 16)
  const sign = getSignature('7000000000000000000', '7000000000000000001')
  assert.equal(sign.length, 16)
})
```

- [x] **Step 2: Run test to verify it fails**

Run: `cd plugins/douyin-relay/dycast && node ./node_modules/tsx/dist/cli.mjs --tsconfig tsconfig.sidecar.json --test src/sidecar/mssdk-runtime.test.ts`

Expected: FAIL，`loadMssdkFrontier` 不存在

- [x] **Step 3: Write minimal implementation**

`mssdk-runtime.ts`：

```typescript
import fs from 'node:fs'
import vm from 'node:vm'
import { createRequire } from 'node:module'

const LIVE_ORIGIN = 'https://live.douyin.com'

export function loadMssdkFrontier(mssdkPath: string): {
  frontierSign: (payload: Record<string, unknown>) => Record<string, unknown>
} {
  const code = fs.readFileSync(mssdkPath, 'utf8')
  const nodeRequire = createRequire(mssdkPath)
  const sandbox = {
    location: {
      origin: LIVE_ORIGIN,
      protocol: 'https:',
      host: 'live.douyin.com',
      hostname: 'live.douyin.com',
      port: '',
      href: `${LIVE_ORIGIN}/`,
    },
    navigator: {
      userAgent: 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36',
      appVersion: '5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36',
      appCodeName: 'Mozilla',
    },
    document: {
      cookie: '',
      referrer: '',
      visibilityState: 'visible',
      hidden: false,
      addEventListener() {},
      removeEventListener() {},
      createEvent: () => ({ initEvent() {} }),
    },
    setTimeout,
    clearTimeout,
    setInterval,
    clearInterval,
    require: nodeRequire,
  } as Record<string, unknown>
  sandbox.window = sandbox
  sandbox.self = sandbox
  sandbox.globalThis = sandbox
  vm.runInNewContext(code, sandbox, { filename: 'mssdk.js' })
  const crawler = sandbox.byted_acrawler as { frontierSign?: (payload: Record<string, unknown>) => Record<string, unknown> } | undefined
  if (!crawler || typeof crawler.frontierSign !== 'function') {
    throw new Error('frontierSign missing')
  }
  return { frontierSign: (payload) => crawler.frontierSign!(payload) }
}
```

`ensureCastRuntime` 删除内联的 `vm.runInNewContext`。保留现有的 `mssdkPath` 和 `existsSync` 判断。文件不存在时仍直接返回，不调用 `loadMssdkFrontier`。文件存在时：

```typescript
const mssdkPath = path.join(process.cwd(), 'public', 'mssdk.js')
if (!fs.existsSync(mssdkPath)) {
  castRuntimeReady = true
  return
}
try {
  const loaded = loadMssdkFrontier(mssdkPath)
  g.__dy_frontierSign = (payload) => loaded.frontierSign(payload)
  g.byted_acrawler = { frontierSign: loaded.frontierSign }
} catch {
  // frontierSign 缺失时不抛错，getSignature 走原回退。
}
castRuntimeReady = true
```

`engine.ts` 的 `ensureNodeRuntime` 做同样替换：先 `existsSync`，文件不存在或 `loadMssdkFrontier` 抛错时都不抛给进房，让 `getSignature` 走原回退。不要只粘贴三行赋值。`loadMssdkFrontier` 在文件缺失或没有 `frontierSign` 时会抛错，无头路径现在对缺文件是静默跳过。

- [x] **Step 4: Run test to verify it passes**

Run: `cd plugins/douyin-relay/dycast && node ./node_modules/tsx/dist/cli.mjs --tsconfig tsconfig.sidecar.json --test src/sidecar/mssdk-runtime.test.ts`

Expected: PASS，`X-Bogus` 长度为 16

- [ ] **Step 5: Commit**

```bash
git add plugins/douyin-relay/dycast/src/sidecar/mssdk-runtime.ts plugins/douyin-relay/dycast/src/sidecar/mssdk-runtime.test.ts plugins/douyin-relay/dycast/src/sidecar/headless-router.ts plugins/douyin-relay/dycast/src/sidecar/engine.ts
git commit -m "fix: load frontierSign on the mssdk vm global"
```

---

### Task 4: 握手失败停止重连

**Files:**
- Modify: `plugins/douyin-relay/dycast/src/core/dycast.ts` 的 WebSocket `error` 监听
- Modify: `plugins/douyin-relay/dycast/src/sidecar/headless-router.ts` 的 `writeTerminalStatus`
- Modify: `plugins/douyin-relay/dycast/src/sidecar/headless-router.test.ts`
- Modify: `plugins/douyin-relay/supervisor.py` 的 `on_cast_status`
- Modify: `plugins/douyin-relay/tests/test_supervisor.py`

**Interfaces:**
- Consumes: 无头状态 `connect_failed`；错误文案 `empty_signature` 与 `Unexpected server response`
- Produces: `LiveSupervisor.on_cast_status('connect_failed')` 返回 `[]`，阶段为 `error`

- [x] **Step 1: Write the failing test**

在 `headless-router.test.ts` 增加：

```typescript
test('empty signature and handshake rejection do not look like a drop', async () => {
  const lines: string[] = []
  const router = new HeadlessRouter({
    write: (line) => lines.push(line),
    launch: async () => { throw new Error('unused') },
    connectCast: async (_room, _opts, hooks) => {
      hooks.fail('error', new Error('empty_signature'))
    },
  })
  router.handle(JSON.stringify({ id: 's', cmd: 'connect', roomNum: '1', rawHeaders: 'a=b' }))
  await new Promise((resolve) => setTimeout(resolve, 0))
  const signatureStatus = JSON.parse(lines.filter((line) => line.includes('empty_signature'))[0])
  assert.equal(signatureStatus.state, 'connect_failed')

  const lines2: string[] = []
  const router2 = new HeadlessRouter({
    write: (line) => lines2.push(line),
    launch: async () => { throw new Error('unused') },
    connectCast: async (_room, _opts, hooks) => {
      hooks.fail('error', new Error('Unexpected server response: 200'))
      hooks.fail('close', 1006)
    },
  })
  router2.handle(JSON.stringify({ id: 'h', cmd: 'connect', roomNum: '1', rawHeaders: 'a=b' }))
  await new Promise((resolve) => setTimeout(resolve, 0))
  const statuses = lines2.map((line) => JSON.parse(line)).filter((row) => row.type === 'status')
  assert.equal(statuses.length, 1)
  assert.equal(statuses[0].state, 'connect_failed')
})
```

在 `test_supervisor.py` 的 `test_live_end_probes_later_and_abnormal_close_backs_off` 中，删掉对 `empty_signature` 仍会 `tick` 出 `connect` 的断言。另加：

```python
def test_connect_failed_does_not_reconnect(self):
    now = [0.0]
    sup = LiveSupervisor(interval_seconds=180, auto_refresh=False, now=lambda: now[0])
    sup.start(room_id='1', has_cookie=True)
    sup.on_probe(ok=True, living=True, error='')
    self.assertEqual(sup.on_cast_status(state='connect_failed', error='empty_signature'), [])
    self.assertEqual(sup.phase, 'error')
    now[0] = 120
    self.assertEqual(sup.tick(), [])

    sup2 = LiveSupervisor(interval_seconds=180, auto_refresh=False, now=lambda: now[0])
    sup2.start(room_id='1', has_cookie=True)
    sup2.on_probe(ok=True, living=True, error='')
    sup2.on_cast_status(state='connected')
    self.assertEqual(sup2.on_cast_status(state='closed', error='empty_signature'), [])
    now[0] = 122
    self.assertEqual(sup2.tick(), [{'cmd': 'connect', 'roomNum': '1'}])
```

这段测试放进现有的 `SupervisorTest` 类，不要新建 `LiveSupervisorTests`。路由测试断言 `empty_signature` 上报的是 `connect_failed`。监督器只在 `state='connect_failed'` 时进入 `error`；`state='closed'` 且 `error='empty_signature'` 仍退避重连。保留「已 `connected` 后再 `closed` 会重连」的现有断言。从 `test_live_end_probes_later_and_abnormal_close_backs_off` 删掉的，只是「路由已经把 `empty_signature` 报成 `closed` 之后还会重连」那一段旧预期。

- [x] **Step 2: Run test to verify it fails**

Run: `cd plugins/douyin-relay/dycast && node ./node_modules/tsx/dist/cli.mjs --tsconfig tsconfig.sidecar.json --test src/sidecar/headless-router.test.ts`

Expected: FAIL，`empty_signature` 的 `state` 仍是 `closed`

Run: `cd plugins/douyin-relay && python -m unittest tests.test_supervisor.SupervisorTest.test_connect_failed_does_not_reconnect`

Expected: FAIL，阶段不是 `error`

- [x] **Step 3: Write minimal implementation**

`dycast.ts` 的 WebSocket `error` 监听改为保留消息：

```typescript
this.ws.addEventListener('error', (ev: Event) => {
  const message = (ev as { message?: string }).message || ev.type || 'Unknown Error';
  this.emitter.emit('error', Error(message));
});
```

`writeTerminalStatus` 在 `isAuthError` 之后：

```typescript
if (message === 'empty_signature' || message.includes('Unexpected server response')) {
  this.writeLine({ type: 'status', state: 'connect_failed', error: message, id })
  return
}
```

删除原来单独把 `empty_signature` 写成 `closed` 的分支。这个 `return` 必须发生在关闭码分支之前。同一次 `error` 加关闭码 1006 只上报一条 `connect_failed`，不得再报 `closed`。

`supervisor.py` 的 `on_cast_status` 在 `state == 'closed'` 之前：

```python
if state == 'connect_failed':
    if self._held:
        return []
    self._phase = 'error'
    self._clear_due()
    return []
```

`on_cast_status` 现在有 `del error`。删掉这行，因为本任务不读 `error` 字段；`connect_failed` 已由 `state` 表达。

- [x] **Step 4: Run test to verify it passes**

Run: `cd plugins/douyin-relay/dycast && node ./node_modules/tsx/dist/cli.mjs --tsconfig tsconfig.sidecar.json --test src/sidecar/headless-router.test.ts`

Expected: PASS

Run: `cd plugins/douyin-relay && python -m unittest tests.test_supervisor`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add plugins/douyin-relay/dycast/src/core/dycast.ts plugins/douyin-relay/dycast/src/sidecar/headless-router.ts plugins/douyin-relay/dycast/src/sidecar/headless-router.test.ts plugins/douyin-relay/supervisor.py plugins/douyin-relay/tests/test_supervisor.py
git commit -m "fix: stop reconnecting when the danmaku handshake is rejected"
```

---

### Task 5: 用当前房间验证一次真实连接

**Files:**
- 不改业务代码。只在本任务失败时回到 Task 3 或 Task 4。

**Interfaces:**
- Consumes: Task 1 到 Task 4 的运行时代码，以及 `plugins/douyin-relay/data/config.ini` 里的 `douyin_room_id` 与 `douyin_cookie`
- Produces: 一次握手结果。日志只允许包含状态码、帧数和签名长度

- [x] **Step 1: 启动已有插件进程之外的一次性连接**

在 `plugins/douyin-relay/dycast` 用 `tsx` 跑一段临时脚本，不要把脚本写入仓库。脚本在已有插件进程之外连接，看不到监督器阶段，因此不检查阶段是否变为 `connected`。脚本做这些事：

1. 用 Node 读取 `plugins/douyin-relay/data/config.ini` 的 `[relay]`，取出 `douyin_room_id` 和 `douyin_cookie`。
2. 把 Cookie 赋给运行时的 `__dy_cookie`，不要打印它。
3. 调用 `loadMssdkFrontier`，对固定测试载荷取 `X-Bogus`，记下 `signatureLength`。
4. 调用 `getLiveInfo` 和 `getImInfo(roomId, uniqueId, true)`，记下 `pushServer`。
5. 调用 `DyCast.connect()`，从 WebSocket `upgrade` 或 `unexpected-response` 记下 HTTP 状态码，并统计 8 秒内收到的帧数。

只打印 `signatureLength`、`pushServer`、升级状态码和帧数。禁止打印 Cookie、URL 查询串和弹幕正文。

- [x] **Step 2: 判定**

通过：`signatureLength` 为 16，升级状态码为 101，帧数至少为 1。

失败：`signatureLength` 不是 16，升级状态码为 200，或 8 秒内帧数为 0。停止。不要改重连间隔，把状态码和 `signatureLength` 记到任务结果里。

实测：`signatureLength` 16，`pushServer` `webcast100-ws-web-lq.douyin.com`，升级状态码 200，8 秒内帧数 0。已停止，没有改重连间隔。

- [ ] **Step 3: Commit**

本任务无代码变更时不提交。Task 1 到 Task 4 的提交已经覆盖修复。
