# douyin-relay 无界面引擎与网页管理 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 去掉 dycast 转发层和桌面管理窗，用无界面 Node 引擎把弹幕直接交给 Python，并用网页完成登录、等待开播和断线恢复。

**Architecture:** 用 `tsx` 运行 `dycast/src/sidecar/headless.ts`。`tsx` 能编译 `enum`、无扩展名的相对导入，以及 `.ts` 与 `signature.js` / `abogus.js` 混用；`tsconfig.sidecar.json` 提供 `@/*` → `src/*`。不要用 `node --experimental-strip-types` 加载 `dycast.ts`。标准输出是一行一个 JSON，标准错误是日志。Python 的 `LiveSupervisor` 决定探测、进房和静默续期；`mapper` / `injector` 保持不变。管理页由 aiohttp 提供，只绑定回环地址。进程退出后 `main.py` 不重新拉起它。

**Tech Stack:** TypeScript（`tsx`、`node:test`；不导入 `dycast.ts` 的纯函数测试仍可用 `node --experimental-strip-types`）、Python 3（asyncio、aiohttp、`unittest.IsolatedAsyncioTestCase`）、现有 `CookieLoginSession` 与 `DyCast`。先在 `dycast/` 执行 `npm install`，保证 `pako` 和 `tsx` 存在。

## Global Constraints

- 不把抖音协议迁进 Python，不删除 dycast 的 Vue 源码，本版不启动 Vite，也不打开 dycast 页面。
- 不使用 `RelayCast`、`BrowserDycastConnector`、`relayUrl`、本地转发 WebSocket。
- 不自动弹出浏览器。交互登录只有管理页「登录抖音」会调用 `login_start interactive`。
- 管理页不提供小书签，也不提供「复制小书签链接」。手动粘贴 Cookie 仍可用。
- Node 进程崩溃后不自动拉起。
- 管理服务只绑定 `127.0.0.1` 或 `::1`。默认 `admin_host=127.0.0.1`、`admin_port=18771`。绑定失败时插件继续跑，且不打开浏览器。
- `live_probe_interval_seconds` 默认 `180`。探测只请求 `https://live.douyin.com/{房间号}`，保存 `Set-Cookie` 后再发下一次。不调用 `fetchUser`，不调用 `getImInfo`。
- 房间状态：`1` 准备中、`2` 直播中、`3` 暂停、`4` 已下播。只有 `2` 的 `living` 为 true。解析不到状态时是 `unknown`，不得默认成 `4`。
- 异常重连间隔依次为 2、5、10、30、60 秒，之后保持 60 秒。DyCast 内置重连关闭（`maxReconnectCount=0`）。
- Cookie 短于 200 字符不写入。`login_consume` 只成功一次，成功后阶段变为 `idle` 并清空 Cookie。
- `cookie_auto_refresh=false` 时启动不静默，登录失效后直接「需要登录」。
- 每个登录失效周期最多静默一次。启动静默已失败、取消或超时的，同一次启动里的连接失败不再静默。超时以 `cookie_silent_timeout_seconds` 为准，放弃前必须 `login_cancel` 并等到阶段离开 `running`。
- 登录失效只认：带 Cookie 的直播间页面或 `im/fetch` 返回 401 或 403；最终 URL 含 `/passport/` 或 `/login`；页面没有房间状态且含登录标记。`im_fetch_failed` 与 `empty_signature` 走异常重连，不走续期。探测失败保持等待。
- 未开播时登录成功只写 Cookie，下一步是 `probe_live`。连接正常时不因续期断开。用户点「断开」后停止自动探测，直到再点「连接」或重启插件。
- SSE 和日志不包含 Cookie。`GET /admin/snapshot` 可以包含 Cookie。命令日志里的 `rawHeaders` 打码。
- 点赞默认仍不注入。礼物连击只保留结束帧。映射行为不改。

---

### Task 1: 房间状态解析不得默认成已下播

**Files:**
- Create: `plugins/douyin-relay/dycast/src/sidecar/live-probe.ts`
- Create: `plugins/douyin-relay/dycast/src/sidecar/live-probe.test.ts`

**Interfaces:**
- Consumes: 无
- Produces: `extractRoomStatus(html: string): number | null`；`isLivingStatus(status: number | null): boolean`；`classifyUpstream(input: { httpStatus: number; finalUrl: string; html: string }): 'ok' | 'auth' | 'probe_fail'`

- [ ] **Step 1: Write the failing test**

```typescript
import assert from 'node:assert/strict'
import test from 'node:test'
import { classifyUpstream, extractRoomStatus, isLivingStatus } from './live-probe.ts'

test('missing status is null, not ended', () => {
  assert.equal(extractRoomStatus('<html>login</html>'), null)
  assert.equal(isLivingStatus(null), false)
  assert.equal(isLivingStatus(2), true)
  assert.equal(isLivingStatus(4), false)
})

test('status 2 is living and 1, 3, 4 are not', () => {
  const html = (n: number) => `{"state":{"roomStore":{"roomInfo":{"room":{"status":${n}}}}}}`
  assert.equal(extractRoomStatus(html(1)), 1)
  assert.equal(extractRoomStatus(html(2)), 2)
  assert.equal(extractRoomStatus(html(3)), 3)
  assert.equal(extractRoomStatus(html(9)), null)
})

test('escaped room json still yields status 2', () => {
  const html = '{\\"state\\":{\\"roomStore\\":{\\"roomInfo\\":{\\"room\\":{\\"status\\":2}}}}}'
  assert.equal(extractRoomStatus(html), 2)
})

test('401, passport url, and login markup are auth; blank html is probe_fail', () => {
  assert.equal(classifyUpstream({ httpStatus: 401, finalUrl: 'https://live.douyin.com/1', html: '' }), 'auth')
  assert.equal(classifyUpstream({ httpStatus: 403, finalUrl: 'https://live.douyin.com/webcast/im/fetch/', html: '' }), 'auth')
  assert.equal(classifyUpstream({ httpStatus: 200, finalUrl: 'https://www.douyin.com/passport/web/login', html: '登录' }), 'auth')
  assert.equal(classifyUpstream({ httpStatus: 200, finalUrl: 'https://live.douyin.com/1', html: '<html>请登录</html>' }), 'auth')
  assert.equal(classifyUpstream({ httpStatus: 200, finalUrl: 'https://live.douyin.com/1', html: '<html></html>' }), 'probe_fail')
})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd plugins/douyin-relay/dycast && node --experimental-strip-types --test src/sidecar/live-probe.test.ts`

Expected: FAIL with `Cannot find module`

- [ ] **Step 3: Write minimal implementation**

`extractRoomStatus` 先把 `\\"` 和 `\"` 还原成 `"`，再用正则 `"status"\s*:\s*([1-4])` 取值。匹配不到或值不是 1–4 时返回 `null`。不要调用 `parseLiveHtml`，那个函数会把缺状态写成 `4`。

`isLivingStatus` 只有 `status === 2` 时返回 true。

`classifyUpstream` 在下面任一情况返回 `'auth'`：`httpStatus` 为 401 或 403；`finalUrl` 包含 `/passport/` 或 `/login`；`extractRoomStatus(html)` 为 `null` 且 HTML 含 `登录` 或 `login`。没有房间状态、也没有这些登录标记时返回 `'probe_fail'`。解析出 1–4 时返回 `'ok'`。

- [ ] **Step 4: Run test to verify it passes**

Run: `cd plugins/douyin-relay/dycast && node --experimental-strip-types --test src/sidecar/live-probe.test.ts`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add plugins/douyin-relay/dycast/src/sidecar/live-probe.ts plugins/douyin-relay/dycast/src/sidecar/live-probe.test.ts
git commit -m "feat: classify douyin room status without treating missing html as ended"
```

---

### Task 2: 探测请求保存 Set-Cookie 且不进房

**Files:**
- Modify: `plugins/douyin-relay/dycast/src/sidecar/live-probe.ts`
- Modify: `plugins/douyin-relay/dycast/src/sidecar/live-probe.test.ts`

**Interfaces:**
- Consumes: `extractRoomStatus`、`classifyUpstream`
- Produces: `probeLivePage(roomNum: string, cookieHeader: string, fetchImpl: typeof fetch): Promise<{ ok: boolean; living: boolean; roomStatus: number | 'unknown'; error: string }>`

- [ ] **Step 1: Write the failing test**

```typescript
test('second request sends set-cookie from the first response', async () => {
  const seen: string[] = []
  const fetchImpl = async (_input: unknown, init?: { headers?: Headers }) => {
    seen.push(init?.headers?.get('cookie') || '')
    if (seen.length === 1) {
      return new Response('<html>nonce</html>', {
        status: 200,
        headers: { 'set-cookie': '__ac_nonce=abc; Path=/' },
      })
    }
    return new Response('{"state":{"roomStore":{"roomInfo":{"room":{"status":2}}}}}', { status: 200 })
  }
  const result = await probeLivePage('123', 'sessionid=s', fetchImpl as typeof fetch)
  assert.equal(result.living, true)
  assert.equal(result.roomStatus, 2)
  assert.match(seen[1], /__ac_nonce=abc/)
  assert.match(seen[0], /sessionid=s/)
})

test('probe does not request im fetch', async () => {
  const urls: string[] = []
  const fetchImpl = async (input: unknown) => {
    urls.push(String(input))
    return new Response('{"state":{"roomStore":{"roomInfo":{"room":{"status":4}}}}}', { status: 200 })
  }
  const result = await probeLivePage('9', '', fetchImpl as typeof fetch)
  assert.equal(result.living, false)
  assert.equal(result.roomStatus, 4)
  assert.equal(urls.some((u) => u.includes('/webcast/im/fetch')), false)
  assert.equal(urls[0], 'https://live.douyin.com/9')
})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd plugins/douyin-relay/dycast && node --experimental-strip-types --test src/sidecar/live-probe.test.ts`

Expected: FAIL with `probeLivePage is not a function`

- [ ] **Step 3: Write minimal implementation**

`probeLivePage` 最多请求两次 `https://live.douyin.com/${roomNum}`。用 `Headers` 带上调用方传入的 Cookie，并把响应 `getSetCookie()` 里的 `name=value` 合并进下一次请求的 `Cookie` 头。第一次 HTML 已能解析出 1–4 就不再请求第二次。两次都解析不到则 `{ ok: false, living: false, roomStatus: 'unknown', error: 'probe_fail' }`。`classifyUpstream` 返回 `'auth'` 时 `{ ok: false, living: false, roomStatus: 'unknown', error: 'auth' }`。不要请求其它 URL。

- [ ] **Step 4: Run test to verify it passes**

Run: `cd plugins/douyin-relay/dycast && node --experimental-strip-types --test src/sidecar/live-probe.test.ts`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add plugins/douyin-relay/dycast/src/sidecar/live-probe.ts plugins/douyin-relay/dycast/src/sidecar/live-probe.test.ts
git commit -m "feat: probe douyin room pages with a cookie jar"
```

---

### Task 3: headless 命令立刻回结果

**Files:**
- Create: `plugins/douyin-relay/dycast/src/sidecar/headless-router.ts`
- Create: `plugins/douyin-relay/dycast/src/sidecar/headless-router.test.ts`
- Modify: `plugins/douyin-relay/dycast/src/sidecar/cookie-login-session.ts`

**Interfaces:**
- Consumes: `CookieLoginSession`、`probeLivePage`
- Produces: `HeadlessRouter.handle(line: string): void`。输出经构造参数 `write(line: string)`。结果含 `type: 'result'`、`id`、`ok`、`error`，登录结果另含 `phase`、`mode`、`cookieLength`、`message`。只有成功的 `login_consume` 含 `cookie`。

- [ ] **Step 1: Write the failing test**

```typescript
test('login_start while running is busy and does not launch again', () => {
  let launches = 0
  const lines: string[] = []
  const router = new HeadlessRouter({
    write: (line) => lines.push(line),
    launch: async () => {
      launches += 1
      return { goto: async () => {}, url: () => 'https://live.douyin.com/', cookies: async () => [], close: async () => {} }
    },
  })
  router.handle(JSON.stringify({ id: 'a', cmd: 'login_start', mode: 'silent' }))
  router.handle(JSON.stringify({ id: 'b', cmd: 'login_start', mode: 'interactive' }))
  const second = JSON.parse(lines[1])
  assert.equal(second.ok, false)
  assert.equal(second.error, 'busy')
  assert.equal(launches, 1)
})

test('login_consume returns cookie once then idle', () => {
  const lines: string[] = []
  const router = new HeadlessRouter({
    write: (line) => lines.push(line),
    launch: async () => {
      throw new Error('unused')
    },
  })
  router.seedDoneCookie('sessionid=' + 'x'.repeat(210))
  router.handle(JSON.stringify({ id: 'c', cmd: 'login_consume' }))
  router.handle(JSON.stringify({ id: 'd', cmd: 'login_consume' }))
  const first = JSON.parse(lines[0])
  const second = JSON.parse(lines[1])
  assert.equal(first.ok, true)
  assert.equal(first.phase, 'idle')
  assert.ok(first.cookie.length >= 200)
  assert.equal(second.ok, false)
  assert.equal(second.error, 'not_ready')
  assert.equal(second.cookie, undefined)
})
```

`seedDoneCookie` 只供测试把会话设到 `done`。生产路径仍由 `CookieLoginSession` 进入 `done`。

- [ ] **Step 2: Run test to verify it fails**

Run: `cd plugins/douyin-relay/dycast && node --experimental-strip-types --test src/sidecar/headless-router.test.ts`

Expected: FAIL with `Cannot find module`

- [ ] **Step 3: Write minimal implementation**

`CookieLoginSession.consumeCookie()` 在返回非空 Cookie 后把 `phase` 设为 `'idle'`、`mode` 设为 `null`、`cookie` 清空。空 Cookie 时不改阶段。

`HeadlessRouter.handle` 解析一行 JSON。缺 `id` 或 `cmd` 时写 `{ type:'result', id: id || '', ok:false, error:'bad_args' }`。

`login_start`：`session.start(mode)` 的 status 为 409 时写 `ok:false, error:'busy'`，并带上 `phase`、`mode`、`message`，不带 `cookie`。status 为 202 时写 `ok:true`，`phase:'running'`。

`login_consume`：先 `status(false)`。阶段不是 `done` 时写 `ok:false, error:'not_ready'`，不带 `cookie`。是 `done` 时 `consumeCookie()`，结果写 `ok:true`、`phase:'idle'`、`cookie` 和 `cookieLength`。

`login_status` 写 `ok:true` 以及 `status(false)` 的字段，不带 `cookie`。`login_cancel` 调用 `cancel()` 后写当前 `status(false)`。每条结果都是一行 JSON 并以 `\n` 结束。

- [ ] **Step 4: Run test to verify it passes**

Run: `cd plugins/douyin-relay/dycast && node --experimental-strip-types --test src/sidecar/headless-router.test.ts src/sidecar/cookie-login-session.test.ts`

Expected: PASS。若已有 consume 测试断言阶段仍是 `done`，把断言改成消费后阶段为 `idle`、再次 `status(true).cookie` 为空字符串。

- [ ] **Step 5: Commit**

```bash
git add plugins/douyin-relay/dycast/src/sidecar/headless-router.ts plugins/douyin-relay/dycast/src/sidecar/headless-router.test.ts plugins/douyin-relay/dycast/src/sidecar/cookie-login-session.ts plugins/douyin-relay/dycast/src/sidecar/cookie-login-session.test.ts
git commit -m "feat: answer douyin headless commands with a single result line"
```

---

### Task 4: 进房不再走 Vite，也不再自带重连

**Files:**
- Modify: `plugins/douyin-relay/dycast/package.json`（devDependency 增加 `tsx`）
- Create: `plugins/douyin-relay/dycast/tsconfig.sidecar.json`
- Modify: `plugins/douyin-relay/dycast/src/core/dycast.ts`
- Modify: `plugins/douyin-relay/dycast/src/core/request.ts`
- Modify: `plugins/douyin-relay/dycast/src/sidecar/headless-router.ts`
- Modify: `plugins/douyin-relay/dycast/src/sidecar/headless-router.test.ts`
- Create: `plugins/douyin-relay/dycast/src/sidecar/headless.ts`
- Create: `plugins/douyin-relay/dycast/src/sidecar/import-check.ts`

**Interfaces:**
- Consumes: `probeLivePage`、`HeadlessRouter`
- Produces: `setUpstreamOrigin(origin: string | null): void`；`new DyCast(roomNum, { maxReconnectCount: 0, strictIm: true })`；命令先同步写 `result`，结束后再写一条终态。同一连接的 `error` 与 `close` 只合成一条 `status`。`headless.ts` 先写 `{ type: 'ready' }`。

- [ ] **Step 1: Write the failing test**

```typescript
test('probe result is immediate and connect is busy while probe is in flight', () => {
  const lines: string[] = []
  let connects = 0
  const router = new HeadlessRouter({
    write: (line) => lines.push(line),
    launch: async () => { throw new Error('unused') },
    probe: () => new Promise(() => {}),
    connectCast: async () => { connects += 1 },
  })
  router.handle(JSON.stringify({ id: 'p', cmd: 'probe_live', roomNum: '1', rawHeaders: 'a=b' }))
  router.handle(JSON.stringify({ id: 'c', cmd: 'connect', roomNum: '1', rawHeaders: 'a=b' }))
  const probeResult = JSON.parse(lines[0])
  const connectResult = JSON.parse(lines[1])
  assert.equal(probeResult.type, 'result')
  assert.equal(probeResult.ok, true)
  assert.equal(connectResult.ok, false)
  assert.equal(connectResult.error, 'busy')
  assert.equal(connects, 0)
})

test('connect passes maxReconnectCount 0 and strictIm', async () => {
  let opts: { maxReconnectCount?: number; strictIm?: boolean } | undefined
  const router = new HeadlessRouter({
    write: () => {},
    launch: async () => { throw new Error('unused') },
    connectCast: async (_room: string, options: { maxReconnectCount?: number; strictIm?: boolean }) => {
      opts = options
    },
  })
  router.handle(JSON.stringify({ id: 'c', cmd: 'connect', roomNum: '1', rawHeaders: 'a=b' }))
  await new Promise((r) => setTimeout(r, 0))
  assert.equal(opts?.maxReconnectCount, 0)
  assert.equal(opts?.strictIm, true)
})

test('error plus close becomes one status', async () => {
  const lines: string[] = []
  const router = new HeadlessRouter({
    write: (line) => lines.push(line),
    launch: async () => { throw new Error('unused') },
    connectCast: async (_room: string, _opts: unknown, hooks: { fail: (status: string) => void }) => {
      hooks.fail('error')
      hooks.fail('close')
    },
  })
  router.handle(JSON.stringify({ id: 'c', cmd: 'connect', roomNum: '1', rawHeaders: 'a=b' }))
  await new Promise((r) => setTimeout(r, 0))
  const statuses = lines.map((line) => JSON.parse(line)).filter((row) => row.type === 'status')
  assert.equal(statuses.length, 1)
})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd plugins/douyin-relay/dycast && node --experimental-strip-types --test src/sidecar/headless-router.test.ts`

Expected: FAIL，因为 `connect` 还没有立刻返回 `busy`

- [ ] **Step 3: Write minimal implementation**

在 `dycast/` 执行 `npm install` 和 `npm install -D tsx`。新增 `tsconfig.sidecar.json`：`compilerOptions.paths` 为 `{ "@/*": ["./src/*"] }`，`allowJs: true`，`module` 与 `moduleResolution` 为 `nodenext` 或 `bundler`（以 `tsx` 能解析 `@/utils/logUtil` 为准）。

`request.ts` 增加 `setUpstreamOrigin`。`resolveRequestUrl` 在 origin 已设置且路径以 `/dylive/` 开头时，去掉 `/dylive` 前缀后拼到该 origin，不要落到 `http://127.0.0.1:5173`。

`getImInfo(roomId, uniqueId, strict = false)`：`strict === true` 且 `fetchImInfo` 抛错时把错误抛出，不要返回伪造 cursor。headless 创建的 `DyCast` 必须把 `strictIm: true` 传到这次调用。页面和 `im/fetch` 的 HTTP 401/403 不要收成 `im_fetch_failed`，写成终态 `auth_failed`。

`DyCast` 构造函数改为 `constructor(roomNum: string, opts?: { maxReconnectCount?: number; strictIm?: boolean })`。`maxReconnectCount` 默认仍是 20；传入 0 时 `reconnect()` 不再 `setTimeout`。`error` 与随后的 `close` 由 router 合成一条 `status`，不要各写一条。

`HeadlessRouter` 在调用异步探测或进房之前，同步写出 `{ type:'result', id, ok:true, error:'' }`。已有在途命令时，后到的 `probe_live` 或 `connect` 同步写 `{ ok:false, error:'busy' }`。探测结束后只写一条 `{ type:'probe', id, ok, living, roomStatus, error }`。`error==='auth'` 时不要再写 `status:auth_failed`。进房成功写一条 `{ type:'status', state:'connected', id }`。`message` 写 `{ type:'messages', payload }`。签名为空写一条 `{ type:'status', state:'closed', error:'empty_signature', id }`。`strictIm` 下 `getImInfo` 失败写 `{ type:'status', state:'closed', error:'im_fetch_failed', id }`。关闭码 4001 或 1000 写 `{ type:'status', state:'live_end', code, id }`。其它异常关闭写 `{ type:'status', state:'closed', code, id }`。`disconnect` 取消在途任务并写 `{ type:'result', ok:true }` 与 `{ type:'status', state:'disconnected', id }`。

`import-check.ts` 只含 `import { DyCast } from '../core/dycast.ts'`，并在 `typeof DyCast !== 'function'` 时 `process.exit(1)`。`headless.ts` 在读 stdin 之前写 `{ type:'ready' }\n`。协议只走 stdout。

- [ ] **Step 4: Run test to verify it passes**

Run: `cd plugins/douyin-relay/dycast && npm install && npm install -D tsx && node --experimental-strip-types --test src/sidecar/headless-router.test.ts src/sidecar/live-probe.test.ts && node ./node_modules/tsx/dist/cli.mjs --tsconfig tsconfig.sidecar.json src/sidecar/import-check.ts`

Expected: PASS，且 import-check 的退出码为 0

- [ ] **Step 5: Commit**

```bash
git add plugins/douyin-relay/dycast/package.json plugins/douyin-relay/dycast/package-lock.json plugins/douyin-relay/dycast/tsconfig.sidecar.json plugins/douyin-relay/dycast/src/core/dycast.ts plugins/douyin-relay/dycast/src/core/request.ts plugins/douyin-relay/dycast/src/sidecar/headless-router.ts plugins/douyin-relay/dycast/src/sidecar/headless-router.test.ts plugins/douyin-relay/dycast/src/sidecar/headless.ts plugins/douyin-relay/dycast/src/sidecar/import-check.ts
git commit -m "feat: connect douyin from a headless process without the vite relay"
```

---

### Task 5: Python 监督器

**Files:**
- Create: `plugins/douyin-relay/supervisor.py`
- Create: `plugins/douyin-relay/tests/test_supervisor.py`

**Interfaces:**
- Consumes: 无
- Produces: `LiveSupervisor.start`、`on_login`、`on_probe`、`on_cast_status`、`tick`、`user_connect`、`user_disconnect`、`change_room`，以及只读属性 `phase`。返回的命令字典只有 `cmd`、`mode`、`roomNum`，不含 Cookie。

- [ ] **Step 1: Write the failing test**

```python
import unittest
from supervisor import LiveSupervisor

class SupervisorTest(unittest.TestCase):
    def test_offline_probe_waits_180_seconds(self):
        now = [0.0]
        sup = LiveSupervisor(interval_seconds=180, auto_refresh=False, now=lambda: now[0])
        self.assertEqual(sup.start(room_id='1', has_cookie=True), [{'cmd': 'probe_live', 'roomNum': '1'}])
        self.assertEqual(sup.on_probe(ok=True, living=False, error=''), [])
        self.assertEqual(sup.phase, 'waiting_live')
        now[0] = 179
        self.assertEqual(sup.tick(), [])
        now[0] = 180
        self.assertEqual(sup.tick(), [{'cmd': 'probe_live', 'roomNum': '1'}])

    def test_auto_refresh_without_cookie_still_starts_silent(self):
        sup = LiveSupervisor(auto_refresh=True, now=lambda: 0.0)
        self.assertEqual(sup.start(room_id='1', has_cookie=False), [{'cmd': 'login_start', 'mode': 'silent'}])

    def test_living_probe_connects_once(self):
        sup = LiveSupervisor(auto_refresh=False, now=lambda: 0.0)
        sup.start(room_id='1', has_cookie=True)
        self.assertEqual(sup.on_probe(ok=True, living=True, error=''), [{'cmd': 'connect', 'roomNum': '1'}])

    def test_unknown_probe_does_not_connect(self):
        sup = LiveSupervisor(auto_refresh=False, now=lambda: 0.0)
        sup.start(room_id='1', has_cookie=True)
        self.assertEqual(sup.on_probe(ok=False, living=False, error='probe_fail'), [])
        self.assertEqual(sup.phase, 'waiting_live')

    def test_probe_auth_silents_once_and_login_then_probes(self):
        sup = LiveSupervisor(auto_refresh=True, now=lambda: 0.0)
        self.assertEqual(sup.start(room_id='1', has_cookie=True)[0]['cmd'], 'login_start')
        self.assertEqual(sup.on_login(phase='done', cookie='x' * 200), [{'cmd': 'probe_live', 'roomNum': '1'}])
        sup.on_probe(ok=True, living=True, error='')
        sup.on_cast_status(state='connected')
        self.assertEqual(sup.on_probe(ok=False, living=False, error='auth'), [{'cmd': 'login_start', 'mode': 'silent'}])
        self.assertNotEqual(sup.phase, 'connected')
        self.assertEqual(sup.on_login(phase='done', cookie='z' * 200), [{'cmd': 'probe_live', 'roomNum': '1'}])

    def test_auth_failure_silent_once_then_need_login(self):
        sup = LiveSupervisor(auto_refresh=True, now=lambda: 0.0)
        sup.start(room_id='1', has_cookie=True)
        sup.on_login(phase='done', cookie='x' * 200)
        sup.on_probe(ok=True, living=True, error='')
        sup.on_cast_status(state='connected')
        self.assertEqual(sup.on_cast_status(state='auth_failed'), [{'cmd': 'login_start', 'mode': 'silent'}])
        self.assertEqual(sup.on_login(phase='need_login', cookie=''), [])
        self.assertEqual(sup.phase, 'need_login')
        self.assertEqual(sup.on_cast_status(state='auth_failed'), [])

    def test_connected_resets_silent_budget(self):
        sup = LiveSupervisor(auto_refresh=True, now=lambda: 0.0)
        sup.start(room_id='1', has_cookie=True)
        sup.on_login(phase='done', cookie='x' * 200)
        sup.on_probe(ok=True, living=True, error='')
        sup.on_cast_status(state='connected')
        sup.on_cast_status(state='auth_failed')
        sup.on_login(phase='need_login', cookie='')
        sup.on_login(phase='done', cookie='y' * 200)
        sup.on_probe(ok=True, living=True, error='')
        sup.on_cast_status(state='connected')
        self.assertEqual(sup.on_cast_status(state='auth_failed'), [{'cmd': 'login_start', 'mode': 'silent'}])

    def test_auto_refresh_off_auth_does_not_silent(self):
        sup = LiveSupervisor(auto_refresh=False, now=lambda: 0.0)
        sup.start(room_id='1', has_cookie=True)
        sup.on_probe(ok=True, living=True, error='')
        sup.on_cast_status(state='connected')
        self.assertEqual(sup.on_cast_status(state='auth_failed'), [])
        self.assertEqual(sup.phase, 'need_login')

    def test_login_while_waiting_only_probes(self):
        sup = LiveSupervisor(auto_refresh=False, now=lambda: 0.0)
        sup.start(room_id='1', has_cookie=False)
        self.assertEqual(sup.phase, 'need_login')
        self.assertEqual(sup.on_login(phase='done', cookie='y' * 200), [{'cmd': 'probe_live', 'roomNum': '1'}])

    def test_user_disconnect_stops_probe_until_connect(self):
        now = [0.0]
        sup = LiveSupervisor(interval_seconds=180, auto_refresh=False, now=lambda: now[0])
        sup.start(room_id='1', has_cookie=True)
        sup.on_probe(ok=True, living=False, error='')
        self.assertEqual(sup.user_disconnect(), [{'cmd': 'disconnect'}])
        now[0] = 500
        self.assertEqual(sup.tick(), [])
        cmds = sup.user_connect()
        self.assertEqual([item['cmd'] for item in cmds], ['disconnect', 'probe_live'])

    def test_live_end_probes_later_and_abnormal_close_backs_off(self):
        now = [0.0]
        sup = LiveSupervisor(interval_seconds=180, auto_refresh=False, now=lambda: now[0])
        sup.start(room_id='1', has_cookie=True)
        sup.on_probe(ok=True, living=True, error='')
        sup.on_cast_status(state='connected')
        self.assertEqual(sup.on_cast_status(state='live_end'), [])
        self.assertEqual(sup.phase, 'waiting_live')
        now[0] = 180
        self.assertEqual(sup.tick(), [{'cmd': 'probe_live', 'roomNum': '1'}])
        sup.on_probe(ok=True, living=True, error='')
        sup.on_cast_status(state='connected')
        self.assertEqual(sup.on_cast_status(state='closed', error='im_fetch_failed'), [])
        now[0] = 182
        self.assertEqual(sup.tick(), [{'cmd': 'connect', 'roomNum': '1'}])
        sup.on_cast_status(state='connected')
        self.assertEqual(sup.on_cast_status(state='closed', error='empty_signature'), [])
        now[0] = 184
        self.assertEqual(sup.tick(), [{'cmd': 'connect', 'roomNum': '1'}])
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd plugins/douyin-relay && python -m unittest tests.test_supervisor -v`

Expected: FAIL with `No module named 'supervisor'`

- [ ] **Step 3: Write minimal implementation**

时钟只有构造参数 `now()`。`tick()` 不接收时间参数，到期判断和安排下一次都读 `now()`。

`start`：房间号为空则 `phase='idle'`。`auto_refresh` 为 true 时，无论磁盘上有没有 Cookie，都先返回 `login_start silent`。`auto_refresh` 为 false 且没有 Cookie 时 `phase='need_login'`。`auto_refresh` 为 false 且有 Cookie 时立刻 `probe_live`。

`on_login`：进入此方法时先把 `phase` 从 `connected` 移开。`done` 且 Cookie 长度不少于 200 才算有 Cookie。启动静默得到 `need_login`、`error`、`cancelled` 时记下失败，同一次启动不再静默。有 Cookie 时发 `probe_live`。没有 Cookie 则 `phase='need_login'`。

`on_probe`：`error=='auth'` 与 `on_cast_status(state='auth_failed')` 共用同一次静默预算，不要对同一次探测再调用 `auth_failed`。`living` 为 true 时发一条 `connect`。其它情况 `phase='waiting_live'`，到期时间是 `now() + interval_seconds`。

`on_cast_status`：`connected` 把本周期静默标记清零，并把断线退避重置为下一次从 2 秒开始。`live_end` 设 `phase='waiting_live'`，到期时间 `now() + interval_seconds`，不发 `connect`。`closed`（含 `im_fetch_failed` 与 `empty_signature`）按 2、5、10、30、60 秒安排下一次 `connect`，之后保持 60 秒。`auth_failed` 时若 `auto_refresh` 且本周期未静默且启动静默未失败，先把 `phase` 设为 `refreshing`，再返回 `login_start silent`；否则 `phase='need_login'`。

`user_disconnect` 返回 `disconnect` 并取消定时。`user_connect` 和 `change_room` 的返回值顺序固定为 `disconnect`，然后 `probe_live`。只有房间号变化的 `change_room` 才由管理页调用。

- [ ] **Step 4: Run test to verify it passes**

Run: `cd plugins/douyin-relay && python -m unittest tests.test_supervisor -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add plugins/douyin-relay/supervisor.py plugins/douyin-relay/tests/test_supervisor.py
git commit -m "feat: supervise douyin reconnect without polling the im endpoint"
```

---

### Task 6: 配置改为管理端口和探测间隔

**Files:**
- Modify: `plugins/douyin-relay/config.py`
- Modify: `plugins/douyin-relay/data/config.example.ini`
- Modify: `plugins/douyin-relay/tests/test_cookie_config_write.py`

**Interfaces:**
- Consumes: 无
- Produces: `AppConfig.admin_host`、`admin_port`、`live_probe_interval_seconds`。本任务保留 `relay_backend`、`listen_port` 等旧字段，避免 `main.py` 在 Task 7 之前无法启动。旧字段的删除放在 Task 7，与 `main.py` 的修改同一次提交。

- [ ] **Step 1: Write the failing test**

用该测试文件已有的临时 ini 写法，内容使用假值，不要读 `data/config.ini`：

```python
def test_new_admin_keys_load_while_legacy_keys_remain(self):
    path = self._write_temp_ini("[relay]\nmode = direct\nrelay_backend = legacy\nlisten_port = 1\nadmin_port = 18771\nlive_probe_interval_seconds = 180\n")
    cfg = config.AppConfig()
    self.assertTrue(cfg.load(path))
    self.assertEqual(cfg.relay_backend, "legacy")
    self.assertEqual(cfg.listen_port, 1)
    self.assertEqual(cfg.admin_port, 18771)
    self.assertEqual(cfg.live_probe_interval_seconds, 180)
    self.assertEqual(cfg.admin_host, "127.0.0.1")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd plugins/douyin-relay && python -m unittest tests.test_cookie_config_write -v`

Expected: FAIL，因为 `admin_port` 还不存在

- [ ] **Step 3: Write minimal implementation**

在现有字段之外增加默认 `admin_host='127.0.0.1'`、`admin_port=18771`、`live_probe_interval_seconds=180`，并在 `load` 中读取。`config.example.ini` 追加这三个键。不要删除 `relay_backend` 或 `listen_port`。注释写明 Cookie 来自管理页登录或手动粘贴，不要写小书签。

- [ ] **Step 4: Run test to verify it passes**

Run: `cd plugins/douyin-relay && python -m unittest tests.test_cookie_config_write tests.test_supervisor -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add plugins/douyin-relay/config.py plugins/douyin-relay/data/config.example.ini plugins/douyin-relay/tests/test_cookie_config_write.py
git commit -m "feat: add douyin admin port without removing the relay config yet"
```

---

### Task 7: 用 headless 进程替换 Vite sidecar 和转发服务

**Files:**
- Create: `plugins/douyin-relay/engine_process.py`
- Create: `plugins/douyin-relay/tests/test_engine_process.py`
- Modify: `plugins/douyin-relay/main.py`
- Modify: `plugins/douyin-relay/tests/test_cookie_refresh_startup.py`
- Modify: `plugins/douyin-relay/tests/test_runtime_config_apply.py`

**Interfaces:**
- Consumes: `LiveSupervisor`、`config.get_config()`、`config.write_douyin_cookie_atomic`
- Produces: `EngineProcess.start`、`stop`、`send`、`feed_stdout`、`feed_stderr`、`snapshot`。`send` 给 `probe_live` 和 `connect` 补上当前配置里的 `rawHeaders`。`snapshot()` 不含 Cookie。

- [ ] **Step 1: Write the failing test**

```python
def test_stdout_events_dispatch_once(self):
    events = []
    delivered = []
    proc = EngineProcess(on_messages=delivered.append, on_event=events.append, node_exe="node", dycast_path=".")
    proc.feed_stdout('{"type":"messages","payload":[{"method":"WebcastChatMessage"}]}\n')
    proc.feed_stdout("not-json\n")
    proc.feed_stderr("stack\n")
    proc.feed_stdout('{"type":"probe","id":"p","ok":false,"living":false,"roomStatus":"unknown","error":"auth"}\n')
    proc.feed_stdout('{"type":"status","id":"c","state":"closed","error":"empty_signature"}\n')
    self.assertEqual(delivered, [[{"method": "WebcastChatMessage"}]])
    self.assertEqual([item["type"] for item in events], ["probe", "status"])
    self.assertIn("not-json", proc.log_lines)
    self.assertIn("stack", proc.log_lines)
    self.assertNotIn("sessionid", "".join(proc.log_lines))
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd plugins/douyin-relay && python -m unittest tests.test_engine_process -v`

Expected: FAIL with `No module named 'engine_process'`

- [ ] **Step 3: Write minimal implementation**

`start` 的命令是 `node ./node_modules/tsx/dist/cli.mjs --tsconfig tsconfig.sidecar.json src/sidecar/headless.ts`，工作目录为 `dycast/`。环境变量写入 `DYCAST_LOGIN_PROFILE_DIR`、`DYCAST_LOGIN_TIMEOUT_SECONDS`、`DYCAST_SILENT_TIMEOUT_SECONDS`。非 Windows 使用 `start_new_session=True`，`stop` 先对进程组 `SIGTERM`，8 秒后再 `SIGKILL`。Windows 使用 `taskkill /F /T /PID <pid>`。子进程退出后只把 `snapshot()['running']` 设为 false，不要在 `main.py` 里自动 `start`。`snapshot()['running']` 为 false 时，管理动作返回 `{ok:false, error:'engine_not_ready'}`，不要发 stdin。

静默登录的等待用 `cookie_silent_timeout_seconds`。超时先 `send({'cmd':'login_cancel'})`，等到登录阶段离开 `running`，再把 `cancelled` 交给监督器。

`send` 补 `id`。`probe_live` 与 `connect` 的 `rawHeaders` 取当前 `douyin_cookie`。写日志时只记 `cookieLength`。`feed_stdout` 把 `messages` 交给 `on_messages`。`probe` 只调用 `supervisor.on_probe` 一次。`status` 只调用 `supervisor.on_cast_status` 一次。`login` 只调用 `supervisor.on_login` 一次。`result` 只记录在途命令是否被接受，不再次触发监督器。坏行和 `feed_stderr` 进入 `log_lines`。

`main.py` 删除 `import admin_ui`、`from runtime_manager import ...`、`DouyinRelayServer` 和 `refresh_cookie_then_connect`。启动后等 `{ type: ready }`，再执行 `LiveSupervisor.start` 返回的命令。`messages` 仍进入现有映射；映射结果追加到最近 100 条，字段为 `time`、`author_name`、`kind`、`text`，礼物另有 `gift_name` 和 `num`。`login` 阶段为 `done` 时发送 `login_consume`，长度不少于 200 才原子写回。从 `AppConfig` 删除 `mode`、`relay_backend`、`listen_host`、`listen_port`、`ws_path`、`sidecar_host`、`sidecar_port`、`sidecar_start_timeout_seconds`、`sidecar_node_cmd` 以及 `get_dycast_relay_ws_url`。

重写 `test_cookie_refresh_startup.py`，断言改为：

- `auto_refresh=True` 时 `start` 的第一条是 `login_start silent`，即使 `has_cookie=False`。
- 静默 `done` 且 Cookie 长度不少于 200 时写盘，下一条是 `probe_live`，不是 `connect`。
- 静默 `need_login` 且磁盘已有长度不少于 200 的 Cookie 时不写盘，下一条是 `probe_live`。
- 房间号为空时可以静默，但不发 `probe_live` 或 `connect`。
- `cookie_auto_refresh=False` 且已有 Cookie 时不 `login_start`，直接 `probe_live`。
- `login_start` 抛错后，已有磁盘 Cookie 则 `probe_live`，不 `connect`。
- Cookie 短于 200 不写盘。

重写 `test_runtime_config_apply.py`，删除 `handle_admin_action("sidecar")`、`relay_ws_url` 和 `ws://127.0.0.1:18765/`。新断言：`redact_secrets` 仍去掉 `rawHeaders`、`cookie`、`douyin_cookie`；引擎未运行时动作结果是 `{ok:false, error:'engine_not_ready'}`，且结果文本不含 Cookie。

- [ ] **Step 4: Run test to verify it passes**

Run: `cd plugins/douyin-relay && python -m unittest tests.test_engine_process tests.test_supervisor tests.test_cookie_refresh_startup tests.test_runtime_config_apply tests.test_cookie_config_write tests.test_gift_repeat_end tests.test_star_guard_mapping -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add plugins/douyin-relay/engine_process.py plugins/douyin-relay/tests/test_engine_process.py plugins/douyin-relay/main.py plugins/douyin-relay/tests/test_cookie_refresh_startup.py plugins/douyin-relay/tests/test_runtime_config_apply.py
git commit -m "feat: drive the douyin engine over stdin instead of the relay socket"
```

---

### Task 8: 网页管理页

**Files:**
- Create: `plugins/douyin-relay/web_admin.py`
- Create: `plugins/douyin-relay/web/admin.html`
- Create: `plugins/douyin-relay/tests/test_web_admin.py`
- Modify: `plugins/douyin-relay/listener.py`
- Modify: `plugins/douyin-relay/main.py`

**Interfaces:**
- Consumes: `EngineProcess.send`、`LiveSupervisor.user_connect`、`user_disconnect`、`change_room`
- Produces: `start_admin(host, port, status_provider, action_handler)`。路由为 `GET /admin`、`GET /admin/snapshot`、`GET /admin/events`、`POST /admin/action`。

- [ ] **Step 1: Write the failing test**

```python
import asyncio
import json
import unittest

from aiohttp.test_utils import TestClient, TestServer

from web_admin import build_app, open_admin_browser, start_admin


class WebAdminTest(unittest.IsolatedAsyncioTestCase):
    async def test_snapshot_contains_cookie_and_sse_does_not(self):
        seen = []
        app = build_app(
            status_provider=lambda: {
                "running": True,
                "phase": "waiting_live",
                "sent": 1,
                "dropped": 0,
                "queue_size": 0,
                "login_phase": "idle",
                "cookie": "sessionid=secret",
                "logs": ["ready"],
                "messages": [{"time": 1, "author_name": "a", "kind": "text", "text": "hi"}],
            },
            action_handler=lambda action, payload: seen.append((action, payload)) or {"ok": True},
        )
        async with TestClient(TestServer(app)) as client:
            snapshot = await client.get("/admin/snapshot")
            body = await snapshot.json()
            self.assertEqual(body["cookie"], "sessionid=secret")
            self.assertEqual(body["messages"][0]["text"], "hi")
            self.assertEqual(body["sent"], 1)
            ws = await client.get("/admin/events")
            chunk = await ws.content.read(400)
            self.assertNotIn(b"sessionid=secret", chunk)
            posted = await client.post("/admin/action", json={"action": "login_start"})
            self.assertEqual(posted.status, 200)
            self.assertEqual(seen, [("login_start", {})])
            await client.post("/admin/action", json={"action": "login_cancel"})
            self.assertEqual(seen[-1][0], "login_cancel")

    def test_non_loopback_host_is_refused(self):
        result = asyncio.run(start_admin("0.0.0.0", 18771, status_provider=lambda: {}, action_handler=lambda a, p: {}))
        self.assertIsNone(result)

    def test_save_filters_does_not_change_room(self):
        seen = []
        app = build_app(
            status_provider=lambda: {"running": True, "cookie": "", "logs": [], "messages": [], "room_id": "1"},
            action_handler=lambda action, payload: seen.append((action, payload)) or {"ok": True, "room_changed": payload.get("room_changed", False)},
        )

        async def run():
            async with TestClient(TestServer(app)) as client:
                await client.post("/admin/action", json={"action": "save_config", "room_id": "1", "include_like": False})
                await client.post("/admin/action", json={"action": "save_config", "room_id": "2"})

        asyncio.run(run())
        self.assertFalse(seen[0][1]["room_changed"])
        self.assertTrue(seen[1][1]["room_changed"])

    def test_second_open_uses_existing_server(self):
        opened = []
        open_admin_browser(already_running=True, port=18771, opener=opened.append)
        self.assertEqual(opened, ["http://127.0.0.1:18771/admin"])

    def test_engine_not_ready(self):
        app = build_app(
            status_provider=lambda: {"running": False, "cookie": "sessionid=secret", "logs": [], "messages": []},
            action_handler=lambda action, payload: {"ok": False, "error": "engine_not_ready"},
        )

        async def run():
            async with TestClient(TestServer(app)) as client:
                resp = await client.post("/admin/action", json={"action": "connect"})
                body = await resp.json()
                self.assertEqual(body["error"], "engine_not_ready")
                self.assertNotIn("sessionid=secret", json.dumps(body))

        asyncio.run(run())
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd plugins/douyin-relay && python -m unittest tests.test_web_admin -v`

Expected: FAIL with `No module named 'web_admin'`

- [ ] **Step 3: Write minimal implementation**

`build_app` 返回 `aiohttp.web.Application`。`start_admin` 在 host 不是 `127.0.0.1` 或 `::1` 时返回 `None`。端口占用时捕获 `OSError`，记日志并返回 `None`。测试使用 `unittest.IsolatedAsyncioTestCase` 与 `aiohttp.test_utils.TestClient`，不要引入 pytest。

snapshot 含 `running`、`phase`、`sent`、`dropped`、`queue_size`、`login_phase`、最多 100 条已映射弹幕、最多 200 行日志和 Cookie。弹幕字段是 `time`、`author_name`、`kind`、`text`；礼物另有 `gift_name` 和 `num`。SSE 在序列化前删除 `cookie`、`rawHeaders`、`douyin_cookie`。

`save_config` 写房间号、Cookie 和过滤开关。只有 `room_id` 与当前配置不同时，`room_changed` 为 true，并调用 `change_room`。只改过滤时不调用 `change_room`。`login_start` 固定 `mode=interactive`。`login_cancel` 发送 `login_cancel`。`connect` 调 `user_connect`。`disconnect` 调 `user_disconnect`。`restart` 在插件事件循环里重启 headless 进程后再 `supervisor.start`。`running` 为 false 时这些动作返回 `{ok:false, error:'engine_not_ready'}`，响应里不带 Cookie。

`web/admin.html` 展示状态、房间号、Cookie、保存、登录抖音、取消登录、连接、断开、重启、内容前缀、礼物、礼物样式、点赞、进场、关注、最近弹幕和运行日志。登录成功后重新请求 snapshot 填充输入框，不自动提交整份表单。文案不出现小书签和 WebSocket 转发地址。

`open_admin_browser(already_running, port, opener=webbrowser.open_new_tab)` 在服务已监听或本次 `start_admin` 成功时打开 `http://127.0.0.1:{port}/admin`。`start_admin` 返回 `None` 时不打开。`listener.py` 调用这个函数，不再调用 `admin_ui`。

- [ ] **Step 4: Run test to verify it passes**

Run: `cd plugins/douyin-relay && python -m unittest tests.test_web_admin tests.test_engine_process tests.test_supervisor -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add plugins/douyin-relay/web_admin.py plugins/douyin-relay/web/admin.html plugins/douyin-relay/tests/test_web_admin.py plugins/douyin-relay/listener.py plugins/douyin-relay/main.py
git commit -m "feat: open douyin relay admin in the browser"
```

---

### Task 9: 去掉转发服务、桌面窗口和小书签

**Files:**
- Delete: `plugins/douyin-relay/relay_server.py`
- Delete: `plugins/douyin-relay/admin_ui.py`
- Delete: `plugins/douyin-relay/runtime_manager.py` 与 `plugins/douyin-relay/dycast_bridge_client.py`
- Modify: `plugins/douyin-relay/main.py`（确认已无 `admin_ui`、`runtime_manager`、`run_on_plugin_loop`；若 Task 7 仍留下导入，在本任务删除）
- Modify: `plugins/douyin-relay/douyin_cookie_help.py`（删除小书签函数；若不再被引用则删除文件）
- Modify: `plugins/douyin-relay/README.md`
- Modify: `plugins/douyin-relay/BUILD.md`
- Modify: `plugins/douyin-relay/tests/test_web_admin.py`

**Interfaces:**
- Consumes: Task 7 与 Task 8
- Produces: `plugins/douyin-relay/*.py` 不再出现 `relay_server`、`admin_ui`、`bookmarklet`

- [ ] **Step 1: Write the failing test**

```python
def test_plugin_package_has_no_relay_or_bookmark(self):
    root = pathlib.Path(__file__).resolve().parents[1]
    text = "\n".join(p.read_text(encoding="utf-8") for p in root.glob("*.py"))
    self.assertNotIn("relay_server", text)
    self.assertNotIn("bookmarklet", text)
    self.assertNotIn("admin_ui", text)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd plugins/douyin-relay && python -m unittest tests.test_web_admin.PluginSurfaceTest.test_plugin_package_has_no_relay_or_bookmark -v`

Expected: FAIL

- [ ] **Step 3: Write minimal implementation**

删除无引用的转发服务、桌面管理窗、Vite 运行时管理和 HTTP bridge。删除前先改 `main.py`：去掉 `import admin_ui`、`runtime_manager` 和 `admin_ui.run_on_plugin_loop`。`README.md` 与 `BUILD.md` 改为：在 `dycast/` 执行 `npm install`，用 `tsx` 与 `tsconfig.sidecar.json` 启动 headless；点管理打开 `http://127.0.0.1:18771/admin`。删掉 Vite、`sidecar_node_cmd`、`relay_backend` 和转发地址作为使用步骤的说明。

- [ ] **Step 4: Run test to verify it passes**

Run: `cd plugins/douyin-relay && python -m unittest discover -s tests -v`

然后：

Run: `cd plugins/douyin-relay/dycast && node --experimental-strip-types --test src/sidecar/live-probe.test.ts src/sidecar/headless-router.test.ts src/sidecar/cookie-login-session.test.ts src/sidecar/cookie-login-rules.test.ts src/sidecar/cookie-login-browser.test.ts && node ./node_modules/tsx/dist/cli.mjs --tsconfig tsconfig.sidecar.json src/sidecar/import-check.ts`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add plugins/douyin-relay
git commit -m "feat: remove the douyin websocket relay and desktop admin window"
```

---

## Spec coverage

- 页面探测、转义后的房间状态、登录页标记、Cookie 罐：Task 1、Task 2。
- 命令立刻返回、登录占坑、`login_consume` 一次：Task 3。消费后阶段变为 `idle`；在 Task 8 替换桌面窗之前，旧窗口可能把该阶段显示成未开始，这是预期的过渡。
- `tsx` 加载 `DyCast`、关闭内置重连、401/403 与 `im_fetch_failed` 分开、一次连接只报一条终态：Task 4。
- 180 秒等待、无 Cookie 也先静默、失效后静默一次并先离开 `connected`、下播后再探测、断开后停止探测：Task 5。
- 先增加 `18771`，旧转发配置留到 Task 7 再删：Task 6、Task 7。
- stdout 事件只分发一次、引擎未就绪、Windows `taskkill`：Task 7。
- 网页、snapshot 与 SSE、过滤不换房间、再次打开管理页：Task 8。
- 去掉小书签、桌面窗、转发入口，并改 `BUILD.md`：Task 9。
