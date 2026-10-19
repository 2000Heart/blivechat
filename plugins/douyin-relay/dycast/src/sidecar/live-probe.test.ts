import assert from 'node:assert/strict'
import test from 'node:test'
import {
  classifyDirectRequest,
  classifyUpstream,
  danmakuWebSocketUrl,
  directRequestKind,
  extractRoomStatus,
  isLivingStatus,
  mergeCookieHeader,
  probeLivePage,
} from './live-probe.ts'

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

test('probe 401 or 403 without a sent cookie is not auth', async () => {
  const seen: Array<string | null> = []
  const fetchImpl = async (_input: unknown, init?: { headers?: Headers }) => {
    seen.push(init?.headers?.get('cookie') ?? null)
    return new Response('<html></html>', { status: seen.length === 1 ? 401 : 403 })
  }
  const result = await probeLivePage('1', '', fetchImpl as typeof fetch)
  assert.equal(seen.every((cookie) => cookie == null), true)
  assert.equal(result.ok, false)
  assert.equal(result.living, false)
  assert.equal(result.roomStatus, 'unknown')
  assert.equal(result.error, 'probe_fail')
})

test('probe 401 with the cookie it sent is auth', async () => {
  const fetchImpl = async (_input: unknown, init?: { headers?: Headers }) => {
    assert.match(init?.headers?.get('cookie') || '', /sessionid=s/)
    return new Response('', { status: 401 })
  }
  const result = await probeLivePage('8', 'sessionid=s', fetchImpl as typeof fetch)
  assert.equal(result.error, 'auth')
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

test('live page login uses the same three signals, and only with a cookie for 401', () => {
  assert.equal(directRequestKind('https://live.douyin.com/123'), 'live_page')
  assert.equal(directRequestKind('https://live.douyin.com/webcast/im/fetch/?room_id=1'), 'im_fetch')
  assert.equal(directRequestKind('https://live.douyin.com/webcast/user/'), 'user')
  assert.equal(directRequestKind('https://live.douyin.com/webcast/user/me/'), 'user')

  assert.equal(classifyDirectRequest({
    kind: 'live_page', httpStatus: 401, finalUrl: 'https://live.douyin.com/1', html: '', sentCookie: true,
  }), 'auth')
  assert.equal(classifyDirectRequest({
    kind: 'live_page', httpStatus: 403, finalUrl: 'https://live.douyin.com/1', html: '', sentCookie: true,
  }), 'auth')
  assert.equal(classifyDirectRequest({
    kind: 'live_page', httpStatus: 401, finalUrl: 'https://live.douyin.com/1', html: '', sentCookie: false,
  }), 'probe_fail')
  assert.equal(classifyDirectRequest({
    kind: 'live_page', httpStatus: 200, finalUrl: 'https://www.douyin.com/passport/web/login', html: '<html></html>', sentCookie: false,
  }), 'auth')
  assert.equal(classifyDirectRequest({
    kind: 'live_page', httpStatus: 200, finalUrl: 'https://live.douyin.com/1', html: '<html>请登录</html>', sentCookie: true,
  }), 'auth')
  assert.equal(classifyDirectRequest({
    kind: 'live_page', httpStatus: 200, finalUrl: 'https://live.douyin.com/1', html: '{"status":2} 登录', sentCookie: true,
  }), 'ok')

  assert.equal(classifyDirectRequest({
    kind: 'im_fetch', httpStatus: 403, finalUrl: 'https://live.douyin.com/webcast/im/fetch/', html: '', sentCookie: true,
  }), 'auth')
  assert.equal(classifyDirectRequest({
    kind: 'im_fetch', httpStatus: 401, finalUrl: 'https://live.douyin.com/webcast/im/fetch/', html: '登录', sentCookie: false,
  }), 'ok')
  assert.equal(classifyDirectRequest({
    kind: 'im_fetch', httpStatus: 200, finalUrl: 'https://www.douyin.com/passport/web/login', html: '', sentCookie: true,
  }), 'auth')
  assert.equal(classifyDirectRequest({
    kind: 'im_fetch', httpStatus: 200, finalUrl: 'https://live.douyin.com/login', html: '', sentCookie: false,
  }), 'auth')
  assert.equal(classifyDirectRequest({
    kind: 'im_fetch', httpStatus: 200, finalUrl: 'https://live.douyin.com/webcast/im/fetch/', html: '', sentCookie: true,
  }), 'ok')

  assert.equal(classifyDirectRequest({
    kind: 'user', httpStatus: 401, finalUrl: 'https://live.douyin.com/webcast/user/', html: '', sentCookie: true,
  }), 'ok')
  assert.equal(classifyDirectRequest({
    kind: 'user', httpStatus: 403, finalUrl: 'https://www.douyin.com/passport/web/login', html: '登录', sentCookie: true,
  }), 'ok')
})

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
  assert.equal(
    danmakuWebSocketUrl('webcast100-ws-web-lq.douyin.com', 'http://127.0.0.1:5173'),
    'ws://127.0.0.1:5173/socket/webcast/im/push/v2/',
  )
})

test('handshake cookie merges caller cookie with set-cookie', () => {
  const header = mergeCookieHeader('sessionid=s', ['__ac_nonce=abc; Path=/'])
  assert.match(header, /sessionid=s/)
  assert.match(header, /__ac_nonce=abc/)
  assert.equal(header.includes('Path='), false)
})
