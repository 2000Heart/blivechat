import assert from 'node:assert/strict'
import test from 'node:test'
import {
  absorbUpstreamSetCookie,
  clearUpstreamJar,
  setUpstreamOrigin,
  upstreamCookieHeader,
} from '../core/request.ts'

test('caller cookie wins over a stale set-cookie of the same name', () => {
  setUpstreamOrigin('https://live.douyin.com')
  clearUpstreamJar()
  ;(globalThis as { __dy_cookie?: string }).__dy_cookie = 'sessionid=new; ttwid=fresh'
  absorbUpstreamSetCookie('ttwid=stale; Path=/')
  absorbUpstreamSetCookie('__ac_nonce=abc; Path=/')
  const header = upstreamCookieHeader()
  assert.match(header, /sessionid=new/)
  assert.match(header, /ttwid=fresh/)
  assert.match(header, /__ac_nonce=abc/)
  assert.equal(header.includes('ttwid=stale'), false)
  clearUpstreamJar()
  const cleared = upstreamCookieHeader()
  assert.match(cleared, /sessionid=new/)
  assert.equal(cleared.includes('__ac_nonce'), false)
})
