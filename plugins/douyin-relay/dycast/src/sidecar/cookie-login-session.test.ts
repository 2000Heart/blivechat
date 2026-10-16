import assert from 'node:assert/strict'
import test from 'node:test'
import { CookieLoginSession } from './cookie-login-session.ts'
import type { CookieRecord } from './cookie-login-rules.ts'

function readyCookies(): CookieRecord[] {
  return [
    { name: 'sessionid', value: 'abc', domain: '.douyin.com' },
    { name: 'ttwid', value: 'x'.repeat(220), domain: 'live.douyin.com' },
  ]
}

function shortSessionCookies(): CookieRecord[] {
  return [{ name: 'sessionid', value: 'abc', domain: '.douyin.com' }]
}

async function waitUntilNotRunning(session: CookieLoginSession) {
  for (let i = 0; i < 500; i++) {
    if (session.status(false).phase !== 'running') return
    await new Promise((r) => setImmediate(r))
  }
  throw new Error(`still running: ${session.status(false).phase}`)
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

test('success path closes while running then consumeCookie is one-shot', async () => {
  const session = new CookieLoginSession({
    launch: async () => ({
      goto: async () => {},
      url: () => 'https://live.douyin.com/1',
      cookies: async () => readyCookies(),
      close: async () => {
        assert.equal(session.status(false).phase, 'running')
      },
    }),
    interactiveTimeoutMs: 300_000,
    silentTimeoutMs: 30_000,
  })
  session.start('silent')
  await waitUntilNotRunning(session)
  const st = session.status(false)
  assert.equal(st.phase, 'done')
  assert.equal('cookie' in st, false)
  const cookie = session.consumeCookie()
  assert.equal(cookie.includes('sessionid=abc'), true)
  assert.equal(session.consumeCookie(), '')
  assert.equal(session.status(false).phase, 'done')
})

test('cancel sets cancelled and closes the browser', async () => {
  let closed = false
  const session = new CookieLoginSession({
    launch: async () => ({
      goto: async () => {},
      url: () => 'https://live.douyin.com/1',
      cookies: async () => shortSessionCookies(),
      close: async () => {
        closed = true
      },
    }),
    sleep: async () => {},
    interactiveTimeoutMs: 300_000,
    silentTimeoutMs: 30_000,
  })
  session.start('silent')
  session.cancel()
  await waitUntilNotRunning(session)
  assert.equal(session.status(false).phase, 'cancelled')
  assert.equal(closed, true)
})

test('silent login url becomes need_login', async () => {
  const session = new CookieLoginSession({
    launch: async () => ({
      goto: async () => {},
      url: () => 'https://www.douyin.com/passport/web/login',
      cookies: async () => readyCookies(),
      close: async () => {},
    }),
    interactiveTimeoutMs: 300_000,
    silentTimeoutMs: 30_000,
  })
  session.start('silent')
  await waitUntilNotRunning(session)
  assert.equal(session.status(false).phase, 'need_login')
})

test('interactive success waits 1s via injected clock', async () => {
  let now = 0
  let cookieCalls = 0
  const session = new CookieLoginSession({
    launch: async () => ({
      goto: async () => {},
      url: () => 'https://live.douyin.com/1',
      cookies: async () => {
        cookieCalls += 1
        return readyCookies()
      },
      close: async () => {
        assert.equal(session.status(false).phase, 'running')
      },
    }),
    now: () => now,
    sleep: async (ms) => {
      now += ms
    },
    interactiveTimeoutMs: 300_000,
    silentTimeoutMs: 30_000,
  })
  session.start('interactive')
  await waitUntilNotRunning(session)
  assert.equal(session.status(false).phase, 'done')
  assert.equal(cookieCalls >= 2, true)
  const st = session.status(false)
  assert.equal('cookie' in st, false)
  assert.equal(session.consumeCookie().includes('sessionid=abc'), true)
  assert.equal(session.consumeCookie(), '')
})
