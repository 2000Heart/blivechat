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
