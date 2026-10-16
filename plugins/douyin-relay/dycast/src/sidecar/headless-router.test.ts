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
