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
  assert.equal(session.status(false).cookieLength, cookie.length)
  assert.equal(session.status(true).cookie, '')
  assert.equal(session.consumeCookie(), '')
  assert.equal(session.status(false).cookieLength, cookie.length)
  assert.equal(session.status(false).phase, 'idle')
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
  const passingCookieAt: number[] = []
  const session = new CookieLoginSession({
    launch: async () => ({
      goto: async () => {},
      url: () => 'https://live.douyin.com/1',
      cookies: async () => {
        // cookies() may advance the clock, but not enough to satisfy the 1s gap.
        // The session must wait after the first successful judge.
        now += 1
        passingCookieAt.push(now)
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
  assert.equal(passingCookieAt.length >= 2, true)
  assert.equal(passingCookieAt[1] - passingCookieAt[0] >= 1000, true)
  const st = session.status(false)
  assert.equal('cookie' in st, false)
  const cookie = session.consumeCookie()
  assert.equal(cookie.includes('sessionid=abc'), true)
  assert.equal(session.status(false).cookieLength, cookie.length)
  assert.equal(session.consumeCookie(), '')
  assert.equal(session.status(false).cookieLength, cookie.length)
})

test('silent timeout becomes need_login after close while running', async () => {
  let now = 0
  const silentTimeoutMs = 5_000
  const session = new CookieLoginSession({
    launch: async () => ({
      goto: async () => {},
      url: () => 'https://live.douyin.com/1',
      cookies: async () => shortSessionCookies(),
      close: async () => {
        assert.equal(session.status(false).phase, 'running')
      },
    }),
    now: () => now,
    sleep: async (ms) => {
      now += ms
    },
    interactiveTimeoutMs: 300_000,
    silentTimeoutMs,
  })
  session.start('silent')
  await waitUntilNotRunning(session)
  const st = session.status(false)
  assert.equal(st.phase, 'need_login')
  assert.equal(st.message, 'timeout')
})

test('cancel still sets cancelled when close throws', async () => {
  const session = new CookieLoginSession({
    launch: async () => ({
      goto: async () => {},
      url: () => 'https://live.douyin.com/1',
      cookies: async () => shortSessionCookies(),
      close: async () => {
        throw new Error('close failed')
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
})

test('timeout still sets need_login when close throws', async () => {
  let now = 0
  const session = new CookieLoginSession({
    launch: async () => ({
      goto: async () => {},
      url: () => 'https://live.douyin.com/1',
      cookies: async () => shortSessionCookies(),
      close: async () => {
        throw new Error('close failed')
      },
    }),
    now: () => now,
    sleep: async (ms) => {
      now += ms
    },
    interactiveTimeoutMs: 300_000,
    silentTimeoutMs: 5_000,
  })
  session.start('silent')
  await waitUntilNotRunning(session)
  const st = session.status(false)
  assert.equal(st.phase, 'need_login')
  assert.equal(st.message, 'timeout')
})
