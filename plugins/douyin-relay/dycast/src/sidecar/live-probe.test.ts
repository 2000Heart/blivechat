import assert from 'node:assert/strict'
import test from 'node:test'
import {
  classifyUpstream,
  extractRoomStatus,
  isLivingStatus,
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
