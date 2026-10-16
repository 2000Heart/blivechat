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
