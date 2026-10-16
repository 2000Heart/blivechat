# douyin-relay Cookie 自动登录 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 用 sidecar 里已有的 Playwright 打开系统浏览器登录抖音，自动写入含 HttpOnly 的 Cookie；启动时先静默续期再连房。

**Architecture:** 纯判定函数与登录状态机放在 dycast sidecar。`POST /login/start` 占坑后立刻返回 202，Python 轮询 status。持久 profile 与弹幕用的 headless 浏览器分开。只有 Python 用临时文件替换写 `douyin_cookie`，然后再 disconnect + connect。

**Tech Stack:** TypeScript（Vite sidecar + playwright-core）、Python 3（插件 config / bridge / Tk 与 PySide6 管理页）、Node 内置 `node:test`。

## Global Constraints

- 不申请抖音 OAuth，不读系统日常 Chrome 用户目录，不新增 Python Playwright。
- 登录浏览器与 `BrowserDycastConnector` 不是同一个 Browser 实例。
- Cookie 只来自 `browserContext.cookies()`，domain 含 `douyin.com`；禁止 `document.cookie`。
- 会话 Cookie 白名单：`sessionid`、`sessionid_ss`、`sid_tt`、`uid_tt`、`uid_tt_ss`。导出串长度必须 ≥ 200。
- 交互判定两次间隔至少 1 秒。
- 用户取消 → `cancelled`；超时 → `need_login` 且 message 写明超时。
- `POST /__api/dycast/login/start` 立刻 202，body 不含 Cookie。请求体只有 `mode`。
- profile 目录与超时来自进程环境变量，忽略请求体里的路径。
- 新 login 路由拒绝非回环 `remoteAddress`（允许 `127.0.0.1`、`::1`、`::ffff:127.0.0.1`）。
- 离开 `running` 之前必须 `close()` persistent context。`running` 时再次 start 返回 409。
- 静默超时默认 30 秒；交互超时默认 300 秒。
- `cookie_auto_refresh=true` 且 `relay_backend=sidecar` 时：sidecar ready → silent → 写配置 → disconnect + connect。失败则用磁盘上已有 cookie 再 connect。不自动弹出有头窗口。
- `relay_backend` 不是 sidecar 时登录相关逻辑 no-op。
- 管理页 status 不得包含 Cookie 正文或 `rawHeaders`。日志只打 `cookieLength`。
- macOS 管理页是 Tk，与 PySide6 使用同一套 `sidecar` action：`login_start`、`login_cancel`。
- profile 相对 `config.BASE_PATH`，默认 `data/douyin-browser-profile`。
- 浏览器查找：`CHROME_PATH` → Playwright channel `chrome` 再 `msedge` → 平台路径。

---

### Task 1: Cookie 判定纯函数

**Files:**
- Create: `plugins/douyin-relay/dycast/src/sidecar/cookie-login-rules.ts`
- Create: `plugins/douyin-relay/dycast/src/sidecar/cookie-login-rules.test.ts`

**Interfaces:**
- Consumes: 无
- Produces:
  - `export const MIN_COOKIE_LENGTH = 200`
  - `export type CookieRecord = { name: string; value: string; domain: string }`
  - `export function isLoginUrl(url: string): boolean`
  - `export function serializeDouyinCookies(cookies: CookieRecord[]): string`
  - `export function judgeDouyinLogin(input: { cookies: CookieRecord[]; url: string; mode: 'interactive' | 'silent' }): { ok: boolean; reason: string }`

- [ ] **Step 1: Write the failing test**

```ts
import assert from 'node:assert/strict'
import test from 'node:test'
import { judgeDouyinLogin, serializeDouyinCookies } from './cookie-login-rules.ts'

const session = { name: 'sessionid', value: 'abc', domain: '.douyin.com' }
const filler = { name: 'ttwid', value: 'x'.repeat(220), domain: 'live.douyin.com' }

test('serialize keeps douyin cookies only', () => {
  const raw = serializeDouyinCookies([
    session,
    filler,
    { name: 'other', value: 'no', domain: '.example.com' },
  ])
  assert.equal(raw.includes('sessionid=abc'), true)
  assert.equal(raw.includes('other=no'), false)
})

test('silent login url is need_login', () => {
  const result = judgeDouyinLogin({
    cookies: [session, filler],
    url: 'https://www.douyin.com/passport/web/login',
    mode: 'silent',
  })
  assert.equal(result.ok, false)
  assert.match(result.reason, /login/i)
})

test('interactive accepts session cookie and length', () => {
  const result = judgeDouyinLogin({
    cookies: [session, filler],
    url: 'https://live.douyin.com/123',
    mode: 'interactive',
  })
  assert.equal(result.ok, true)
})

test('short cookie string fails', () => {
  const result = judgeDouyinLogin({
    cookies: [session],
    url: 'https://live.douyin.com/',
    mode: 'interactive',
  })
  assert.equal(result.ok, false)
})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd plugins/douyin-relay/dycast && node --experimental-strip-types --test src/sidecar/cookie-login-rules.test.ts`

Expected: FAIL，找不到模块或 `judgeDouyinLogin` 未定义。

- [ ] **Step 3: Write minimal implementation**

`cookie-login-rules.ts`：

- `isLoginUrl`：URL 的 host+path 小写后包含 `login`、`passport` 或 `sso` 则为 true。解析失败返回 false。
- `serializeDouyinCookies`：只保留 `domain` 包含 `douyin.com` 的项，输出 `name=value`，用 `; ` 连接。跳过空 name。
- `judgeDouyinLogin`：`mode==='silent'` 且 `isLoginUrl` 为 true 时 `{ ok:false, reason:'login_url' }`。白名单名一个都没有时 `{ ok:false, reason:'missing_session_cookie' }`。序列化长度 `< 200` 时 `{ ok:false, reason:'cookie_too_short' }`。否则 `{ ok:true, reason:'ok' }`。

- [ ] **Step 4: Run test to verify it passes**

Run: `cd plugins/douyin-relay/dycast && node --experimental-strip-types --test src/sidecar/cookie-login-rules.test.ts`

Expected: 4 passed。

- [ ] **Step 5: Commit**

```bash
git add plugins/douyin-relay/dycast/src/sidecar/cookie-login-rules.ts plugins/douyin-relay/dycast/src/sidecar/cookie-login-rules.test.ts
git commit -m "test: add douyin cookie login judgment rules"
```

---

### Task 2: 登录状态机（可注入浏览器，不启动 Chromium）

**Files:**
- Create: `plugins/douyin-relay/dycast/src/sidecar/cookie-login-session.ts`
- Create: `plugins/douyin-relay/dycast/src/sidecar/cookie-login-session.test.ts`

**Interfaces:**
- Consumes: `judgeDouyinLogin`、`serializeDouyinCookies`、`CookieRecord`
- Produces:
  - `export type LoginPhase = 'idle' | 'running' | 'done' | 'need_login' | 'error' | 'cancelled'`
  - `export class CookieLoginSession`
  - `start(mode: 'interactive' | 'silent'): { status: number; body: { phase: LoginPhase; mode: string | null; message: string } }`
  - `status(includeCookie: boolean): { phase; mode; cookieLength; message; updatedAt; cookie?: string }`
  - `consumeCookie(): string`
  - `cancel(): void`
  - 构造参数：`{ launch: (mode: 'interactive' | 'silent') => Promise<FakeBrowser>; now?: () => number; interactiveTimeoutMs: number; silentTimeoutMs: number }`
  - `FakeBrowser`：`{ goto(url: string): Promise<void>; url(): string; cookies(): Promise<CookieRecord[]>; close(): Promise<void> }`

- [ ] **Step 1: Write the failing test**

`cookie-login-session.test.ts` 使用下面的假浏览器与断言（时钟固定，避免真实等待 1 秒：interactive 用例把 `now` 做成可推进函数，两次 judge 之间 session 内部若发现间隔不足就再次读取 `now`；测试在 `cookies()` 里把 `now` 增加 1000）：

```ts
function readyCookies() {
  return [
    { name: 'sessionid', value: 'abc', domain: '.douyin.com' },
    { name: 'ttwid', value: 'x'.repeat(220), domain: 'live.douyin.com' },
  ]
}

test('start returns 202 before launch resolves', () => {
  let release: (b: any) => void = () => {}
  const session = new CookieLoginSession({
    launch: () => new Promise(resolve => { release = resolve }),
    interactiveTimeoutMs: 300_000,
    silentTimeoutMs: 30_000,
  })
  const res = session.start('silent')
  assert.equal(res.status, 202)
  assert.equal(res.body.phase, 'running')
  assert.equal(session.start('silent').status, 409)
  release({
    goto: async () => {},
    url: () => 'https://live.douyin.com/1',
    cookies: async () => readyCookies(),
    close: async () => {},
  })
})
```

同文件再写三个测试：成功路径里 `close` 的实现断言 `session.status(false).phase === 'running'`，`await` run 结束后 `status(false)` 无 `cookie` 字段、`consumeCookie()` 往返一次后变空；`cancel()` 后 phase 为 `cancelled` 且 `close` 被调用；silent + `url()` 返回 `https://www.douyin.com/passport/web/login` 时 phase 为 `need_login`。interactive 成功用例的 `cookies()` 第一次调用把注入时钟 `+= 1000`，保证两次判定间隔不少于 1 秒。

- [ ] **Step 2: Run test to verify it fails**

Run: `cd plugins/douyin-relay/dycast && node --experimental-strip-types --test src/sidecar/cookie-login-session.test.ts`

Expected: FAIL，模块不存在。

- [ ] **Step 3: Write minimal implementation**

`CookieLoginSession`：

- `start` 若 `this.phase==='running'` 返回 409，message `login already running`。
- 否则同步设 `phase='running'`、清空 cookie、记录 `startedAt`，然后 `void this.run(mode)`，立刻返回 202。
- `run`：`browser = await launch(mode)`，`await browser.goto('https://live.douyin.com/')`。异常则先 `close`（若已创建）再 `phase='error'`。
- 循环直到超时或成功。interactive 需要连续两次 `judgeDouyinLogin.ok`，两次间隔 ≥ 1000ms。silent 一次成功即可。超时用构造参数里的毫秒数，时钟用注入的 `now()`。
- 成功：先 `await browser.close()`，再 `phase='done'` 并保存 cookie 字符串。
- 超时：先 close，再 `phase='need_login'`，message `timeout`。
- silent 且 reason 为 `login_url` 或 `missing_session_cookie`：先 close，再 `need_login`。
- `cancel`：若 running，设 abort 标志；循环看见后先 close，再 `phase='cancelled'`。
- `status(includeCookie)`：`includeCookie===false` 时不带 `cookie` 字段。
- `consumeCookie` 返回当前 cookie 并清空保存值，phase 保持 `done`。

- [ ] **Step 4: Run test to verify it passes**

Run: `cd plugins/douyin-relay/dycast && node --experimental-strip-types --test src/sidecar/cookie-login-session.test.ts src/sidecar/cookie-login-rules.test.ts`

Expected: PASS。

- [ ] **Step 5: Commit**

```bash
git add plugins/douyin-relay/dycast/src/sidecar/cookie-login-session.ts plugins/douyin-relay/dycast/src/sidecar/cookie-login-session.test.ts
git commit -m "feat: add douyin cookie login session state machine"
```

---

### Task 3: Playwright 启动器、本机路由、浏览器路径

**Files:**
- Create: `plugins/douyin-relay/dycast/src/sidecar/cookie-login-browser.ts`
- Create: `plugins/douyin-relay/dycast/src/sidecar/cookie-login-browser.test.ts`
- Modify: `plugins/douyin-relay/dycast/vite.douyin-proxy-cookie.ts`
- Modify: `plugins/douyin-relay/dycast/src/sidecar/engine.ts`

**Interfaces:**
- Consumes: `CookieLoginSession`、`chromium` from `playwright-core`
- Produces:
  - `export function isLoopbackAddress(remoteAddress: string | undefined): boolean`
  - `export function resolveBrowserExecutablePath(): string | null`
  - `export function createCookieLoginSessionFromEnv(): CookieLoginSession`
  - HTTP：`POST /__api/dycast/login/start`、`GET /__api/dycast/login/status`、`POST /__api/dycast/login/consume`、`POST /__api/dycast/login/cancel`

- [ ] **Step 1: Write the failing test**

```ts
import assert from 'node:assert/strict'
import test from 'node:test'
import { isLoopbackAddress } from './cookie-login-browser.ts'

test('loopback addresses', () => {
  assert.equal(isLoopbackAddress('127.0.0.1'), true)
  assert.equal(isLoopbackAddress('::1'), true)
  assert.equal(isLoopbackAddress('::ffff:127.0.0.1'), true)
  assert.equal(isLoopbackAddress('192.168.1.8'), false)
  assert.equal(isLoopbackAddress(undefined), false)
})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd plugins/douyin-relay/dycast && node --experimental-strip-types --test src/sidecar/cookie-login-browser.test.ts`

Expected: FAIL。

- [ ] **Step 3: Write implementation**

`isLoopbackAddress` 只接受 `127.0.0.1`、`::1`、`::ffff:127.0.0.1`。

`resolveBrowserExecutablePath`：`process.env.CHROME_PATH` 存在且文件存在则返回该路径，否则返回 null。

`launchPersistentDouyin(mode)`：

1. `profileDir = process.env.DYCAST_LOGIN_PROFILE_DIR`。空字符串则抛出 `Error('DYCAST_LOGIN_PROFILE_DIR missing')`。
2. `headless = mode === 'silent'`。
3. 有 `resolveBrowserExecutablePath()` 时：`chromium.launchPersistentContext(profileDir, { headless, executablePath })`。
4. 否则依次尝试 `channel: 'chrome'`、`channel: 'msedge'`。
5. 仍失败则按平台探测这些路径，存在才作为 `executablePath`：
   - macOS：`/Applications/Google Chrome.app/Contents/MacOS/Google Chrome`、`/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge`
   - Windows：`path.join(process.env.LOCALAPPDATA || '', 'Google/Chrome/Application/chrome.exe')`、`path.join(process.env.PROGRAMFILES || '', 'Google/Chrome/Application/chrome.exe')`，以及 Edge 的 `Microsoft/Edge/Application/msedge.exe`
   - Linux：`/usr/bin/google-chrome`、`/usr/bin/chromium`、`/usr/bin/chromium-browser`
6. 都没有：抛出 `Error('未找到浏览器，请设置 CHROME_PATH')`。
7. 返回的对象实现 `goto` / `url` / `cookies` / `close`。`cookies()` 调用 `context.cookies()` 后只保留 `name`、`value`、`domain`。`url()` 读当前 page 的 url。`goto` 使用 `waitUntil: 'domcontentloaded'`。

`createCookieLoginSessionFromEnv` 把上述 launch 注入 `CookieLoginSession`。超时：`DYCAST_LOGIN_TIMEOUT_SECONDS` 默认 300，`DYCAST_SILENT_TIMEOUT_SECONDS` 默认 30，乘 1000。

在 `douyinUpstreamCookieApiMiddleware` 开头处理 login 路径：

- 非回环：403 `{ ok:false, error:'forbidden' }`。
- `POST /__api/dycast/login/start`：body 只读 `mode`。非法 → 400 `{ ok:false, error:'invalid_mode' }`。否则按 `session.start` 的 status 写 JSON，不含 cookie。
- `GET /__api/dycast/login/status`：`session.status(false)`。
- `POST /__api/dycast/login/consume`：`{ ok:true, cookie: session.consumeCookie(), cookieLength }`。
- `POST /__api/dycast/login/cancel`：`session.cancel()` 后返回 `session.status(false)`。

`engine.ts` 删除本地 `resolveBrowserExecutablePath`，改为从 `cookie-login-browser.ts` import。`BrowserDycastConnector` 仍用它找 executablePath，找不到时保持现有错误 `未找到可用浏览器可执行文件，请设置 CHROME_PATH`。登录流程自己还会再试 channel，弹幕连接器保持显式 executablePath，避免无头连房突然改用 channel 行为。

- [ ] **Step 4: Run tests**

Run: `cd plugins/douyin-relay/dycast && node --experimental-strip-types --test src/sidecar/cookie-login-rules.test.ts src/sidecar/cookie-login-session.test.ts src/sidecar/cookie-login-browser.test.ts`

Expected: PASS。

- [ ] **Step 5: Commit**

```bash
git add plugins/douyin-relay/dycast/src/sidecar/cookie-login-browser.ts plugins/douyin-relay/dycast/src/sidecar/cookie-login-browser.test.ts plugins/douyin-relay/dycast/src/sidecar/engine.ts plugins/douyin-relay/dycast/vite.douyin-proxy-cookie.ts
git commit -m "feat: expose localhost douyin cookie login API"
```

---

### Task 4: 配置项与原子写入 Cookie

**Files:**
- Modify: `plugins/douyin-relay/config.py`
- Modify: `plugins/douyin-relay/data/config.example.ini`
- Create: `plugins/douyin-relay/tests/test_cookie_config_write.py`
- Modify: `.gitignore`

**Interfaces:**
- Consumes: `AppConfig`、`BASE_PATH`、`DATA_PATH`
- Produces:
  - `AppConfig.cookie_auto_refresh: bool = True`
  - `AppConfig.douyin_browser_profile_dir: str = 'data/douyin-browser-profile'`
  - `AppConfig.cookie_login_timeout_seconds: int = 300`
  - `AppConfig.cookie_silent_timeout_seconds: int = 30`
  - `def resolve_douyin_browser_profile_dir(cfg: AppConfig) -> str`
  - `def write_douyin_cookie_atomic(cookie: str, path: str | None = None) -> bool`

- [ ] **Step 1: Write the failing test**

```python
import os
import tempfile
import unittest

import config as plugin_config


class WriteDouyinCookieTests(unittest.TestCase):
    def test_atomic_write_replaces_only_cookie(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, 'config.ini')
            with open(path, 'w', encoding='utf-8') as f:
                f.write('[relay]\ndouyin_room_id = 9527\ndouyin_cookie = old\n')
            ok = plugin_config.write_douyin_cookie_atomic(
                'sessionid=abc; ttwid=' + ('x' * 220),
                path=path,
            )
            self.assertTrue(ok)
            text = open(path, encoding='utf-8').read()
            self.assertIn('douyin_room_id = 9527', text)
            self.assertIn('sessionid=abc', text)
            self.assertNotIn('douyin_cookie = old', text)
```

`write_douyin_cookie_atomic` 在传入 `path` 时不要调用 `reload()`，避免测试污染全局配置。`path is None` 时用 `_preferred_config_path()` 并 `return reload()`。

- [ ] **Step 2: Run test to verify it fails**

Run: `cd plugins/douyin-relay && python -m unittest tests.test_cookie_config_write -v`

Expected: FAIL，函数不存在。

- [ ] **Step 3: Implement**

`load()` 读取四个新键。`resolve_douyin_browser_profile_dir`：若配置值是绝对路径则用之，否则 `os.path.join(BASE_PATH, cfg.douyin_browser_profile_dir)`，并 `os.makedirs(..., exist_ok=True)`。

`write_douyin_cookie_atomic`：`ConfigParser(interpolation=None)` 读取，只设置 `douyin_cookie`，写到 `path + '.tmp'`，`os.replace`。日志不打印 cookie。

`config.example.ini` 在 `douyin_cookie =` 下增加：

```ini
cookie_auto_refresh = true
douyin_browser_profile_dir = data/douyin-browser-profile
cookie_login_timeout_seconds = 300
cookie_silent_timeout_seconds = 30
```

仓库 `.gitignore` 增加：`plugins/douyin-relay/data/douyin-browser-profile/`

- [ ] **Step 4: Run test to verify it passes**

Run: `cd plugins/douyin-relay && python -m unittest tests.test_cookie_config_write tests.test_runtime_config_apply -v`

Expected: PASS。

- [ ] **Step 5: Commit**

```bash
git add plugins/douyin-relay/config.py plugins/douyin-relay/data/config.example.ini plugins/douyin-relay/tests/test_cookie_config_write.py .gitignore
git commit -m "feat: persist douyin cookie with atomic config write"
```

---

### Task 5: 启动顺序与 bridge 客户端

**Files:**
- Modify: `plugins/douyin-relay/dycast_bridge_client.py`
- Modify: `plugins/douyin-relay/runtime_manager.py`
- Modify: `plugins/douyin-relay/main.py`
- Create: `plugins/douyin-relay/tests/test_cookie_refresh_startup.py`

**Interfaces:**
- Consumes: `write_douyin_cookie_atomic`、`resolve_douyin_browser_profile_dir`
- Produces:
  - `DycastBridgeClient.login_start(mode: str) -> dict`
  - `DycastBridgeClient.login_status() -> dict`
  - `DycastBridgeClient.login_consume() -> dict`
  - `DycastBridgeClient.login_cancel() -> dict`
  - `async def refresh_cookie_then_connect(client, cfg) -> None` 定义在 `main.py`

- [ ] **Step 1: Write the failing test**

把 `refresh_cookie_then_connect` 抽到可测签名：`async def refresh_cookie_then_connect(client, cfg, relay_ws_url: str) -> None`。

假 client 记录 calls。用例 1：`cookie_auto_refresh=True`、`douyin_room_id='9527'`、status 第一次就是 `done`。顺序必须是 `('start','silent')`、`consume`、`disconnect`、`connect`。connect 的 raw_headers 以 `sessionid=abc` 开头。consume 返回的 cookie 要先写入，测试里 mock `write_douyin_cookie_atomic` 返回 True，并让函数使用 consume 返回值作为 connect headers（不要再读未更新的 cfg 对象）。

用例 2：status `phase='need_login'`。不得调用 consume。connect 的 headers 等于原来的 `cfg.douyin_cookie`。

用例 3：`douyin_room_id=''`。silent 仍执行，但不 connect。

用例 4：`cookie_auto_refresh=False`。不得调用 `login_start`。有房间号时直接 `connect`，headers 为 `cfg.douyin_cookie`。

- [ ] **Step 2: Run test to verify it fails**

Run: `cd plugins/douyin-relay && python -m unittest tests.test_cookie_refresh_startup -v`

Expected: FAIL。

- [ ] **Step 3: Implement**

`DycastBridgeClient`：

```python
def login_start(self, mode: str) -> Dict[str, Any]:
    return self._request_json('POST', '/__api/dycast/login/start', {'mode': mode})

def login_status(self) -> Dict[str, Any]:
    return self._request_json('GET', '/__api/dycast/login/status')

def login_consume(self) -> Dict[str, Any]:
    return self._request_json('POST', '/__api/dycast/login/consume', {})

def login_cancel(self) -> Dict[str, Any]:
    return self._request_json('POST', '/__api/dycast/login/cancel', {})
```

`_request_json` 的 `HTTPError` 改为 `raise RuntimeError(f'HTTP {e.code} {path}')`，不要把 body 拼进异常。

`SidecarRuntimeConfig` 增加 `env_extra: Dict[str, str]`，默认空 dict。`start()` 使用 `env = os.environ.copy(); env.update(self._cfg.env_extra)`。

`main.py` 构造 `SidecarRuntimeConfig` 时传入：

```python
env_extra={
    'DYCAST_LOGIN_PROFILE_DIR': config.resolve_douyin_browser_profile_dir(cfg),
    'DYCAST_LOGIN_TIMEOUT_SECONDS': str(cfg.cookie_login_timeout_seconds),
    'DYCAST_SILENT_TIMEOUT_SECONDS': str(cfg.cookie_silent_timeout_seconds),
}
```

`refresh_cookie_then_connect` 逻辑与 Step 1 的三个用例一致。轮询 `await asyncio.sleep(1)`，最长 `cfg.cookie_silent_timeout_seconds`。日志格式：`douyin cookie refresh phase=%s cookieLength=%s`，不打印 cookie。

替换 sidecar 启动成功后直接 `connect` 的代码（`main.py` 约 157–173 行）为 `await refresh_cookie_then_connect(client, cfg, relay_ws)`。

`handle_admin_action`：

- `op == 'login_start'`：`mode` 不是 `interactive` 则 `{ok:false, error:'interactive only'}`，否则 `login_start('interactive')`。
- `op == 'login_cancel'`：`login_cancel()`。
- `op == 'login_finish'`：`login_status()`。phase 不是 `done` 则 `{ok:true, pending:true, phase}`。是 `done` 则 consume，长度 `< 200` 返回 `{ok:false, error:'cookie_too_short'}`。否则 `write_douyin_cookie_atomic`，再 `_apply_sidecar_runtime_config()`。

`get_runtime_status` 增加 `login_phase`、`login_mode`、`login_cookie_length`、`login_message`。新增函数 `redact_secrets(value)`：dict/list 递归删除键名 `cookie`、`rawHeaders`、`douyin_cookie`。`sidecar_status` 放进返回值前先 redact。login 字段来自 redact 之后的 status，不要把 consume 的 cookie 放进 runtime status。

- [ ] **Step 4: Run tests**

Run: `cd plugins/douyin-relay && python -m unittest tests.test_cookie_refresh_startup tests.test_runtime_config_apply tests.test_cookie_config_write -v`

Expected: PASS。

- [ ] **Step 5: Commit**

```bash
git add plugins/douyin-relay/dycast_bridge_client.py plugins/douyin-relay/runtime_manager.py plugins/douyin-relay/main.py plugins/douyin-relay/tests/test_cookie_refresh_startup.py
git commit -m "feat: refresh douyin cookie before sidecar connect"
```

---

### Task 6: 管理页按钮（Tk 与 PySide6）

**Files:**
- Modify: `plugins/douyin-relay/admin_ui.py`

**Interfaces:**
- Consumes: ops `login_start`、`login_cancel`、`login_finish`；status 字段 `login_phase`、`login_mode`、`login_cookie_length`、`login_message`
- Produces: Tk 与 PySide6 各一组「登录抖音」「取消登录」

- [ ] **Step 1: 定位两处 Cookie 工具条**

Tk：搜索 `打开抖音直播` 的 `ttk.Button` 行。  
PySide6：搜索同一个按钮文案的 `QPushButton`。两处都加按钮，不要只改 PySide6。

- [ ] **Step 2: 按钮与文案**

「登录抖音」→ `_run_action('sidecar', {'op': 'login_start', 'mode': 'interactive'})`。  
「取消登录」→ `{'op': 'login_cancel'}`，仅 `login_phase=='running'` 且 `login_mode=='interactive'` 时启用。

文案：

- `running` + `silent`：静默续期中
- `running` + `interactive`：请在弹出的浏览器中登录抖音
- `done`：已更新（{login_cookie_length} 字符）
- `need_login`：需要重新登录。{login_message}
- `cancelled`：已取消
- `error`：登录失败。{login_message}
- 其他：未开始

- [ ] **Step 3: done 只刷新输入框**

每个 UI 保存 `_handled_login_updated_at`。status 里若 `login_phase=='done'` 且 `updatedAt` 变化：调用 `login_finish`。返回 `ok` 且非 pending 时 `config.reload()`，把 `config.get_config().douyin_cookie` 写入输入框。不要调用保存配置按钮的处理函数。

- [ ] **Step 4: 语法检查**

Run: `python3 -m py_compile plugins/douyin-relay/admin_ui.py plugins/douyin-relay/main.py plugins/douyin-relay/config.py`

Expected: 退出码 0。

- [ ] **Step 5: Commit**

```bash
git add plugins/douyin-relay/admin_ui.py
git commit -m "feat: add douyin login buttons to plugin admin"
```

---

### Task 7: 文档

**Files:**
- Modify: `plugins/douyin-relay/README.md`

- [ ] **Step 1: 在「如何填写 douyin_cookie」下增加「浏览器登录」小节**

说明首次点「登录抖音」；之后启动会静默续期；失败时再点一次；手动粘贴仍可用；找不到浏览器时设置 `CHROME_PATH`；`cookie_auto_refresh=false` 关闭静默续期。

- [ ] **Step 2: Commit**

```bash
git add plugins/douyin-relay/README.md
git commit -m "docs: describe douyin cookie browser login"
```

---

## 手工冒烟（全部任务完成后）

1. 清空 profile 目录与 `douyin_cookie` 后启动：日志为 need_login，不弹出浏览器。
2. 管理页点「登录抖音」并登录：输入框出现 Cookie，已配置房间会重连。
3. 重启且不打开管理页：先静默续期再连房。
4. 点取消后浏览器关闭，再次登录可以打开新窗口。
5. 手动粘贴并保存后，以手动内容为准。

## Spec coverage

- 交互登录与静默续期：Task 2、3、5、6
- 先续期再连房，失败用旧 cookie：Task 5
- profile 先关闭再改 phase，重复 start 409：Task 2
- start 立即 202；静默 30 秒；交互 300 秒：Task 2、3、5
- `browserContext.cookies()`、白名单、长度 200、登录 URL：Task 1、3
- 仅回环、profile 来自环境变量：Task 3、5
- 原子写 cookie，管理页不双写：Task 4、6
- Tk 与 PySide6：Task 6
- gitignore 与 README：Task 4、7
- 非 sidecar 不跑登录：Task 5 只替换 `relay_backend=='sidecar'` 分支内的 connect
