import assert from 'node:assert/strict'
import test from 'node:test'
import { HeadlessRouter } from './headless-router.ts'

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
