import assert from 'node:assert/strict'
import { spawn } from 'node:child_process'
import fs from 'node:fs'
import path from 'node:path'
import test from 'node:test'
import { fileURLToPath } from 'node:url'
import { HeadlessRouter } from './headless-router.ts'
import { replacePageCookie } from '../../vite.douyin-proxy-cookie.ts'

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

test('login cookie replaces the same names already on the page', () => {
  assert.equal(
    replacePageCookie('sessionid=old; __ac_nonce=abc', 'sessionid=new; ttwid=fresh'),
    'sessionid=new; __ac_nonce=abc; ttwid=fresh',
  )
})

test('login done emits a login event without the cookie body', async () => {
  const lines: string[] = []
  const router = new HeadlessRouter({
    write: (line) => lines.push(line),
    launch: async () => ({
      goto: async () => {},
      url: () => 'https://live.douyin.com/1',
      cookies: async () => [
        { name: 'sessionid', value: 'abc', domain: '.douyin.com' },
        { name: 'ttwid', value: 'x'.repeat(220), domain: 'live.douyin.com' },
      ],
      close: async () => {},
    }),
  })
  router.handle(JSON.stringify({ id: 'login-1', cmd: 'login_start', mode: 'silent' }))
  for (let i = 0; i < 50 && !lines.some((line) => line.includes('"type":"login"')); i++) {
    await new Promise((resolve) => setImmediate(resolve))
  }
  const login = lines.map((line) => JSON.parse(line)).find((row) => row.type === 'login')
  assert.equal(login.phase, 'done')
  assert.equal(login.id, 'login-1')
  assert.ok(login.cookieLength >= 200)
  assert.equal(login.cookie, undefined)
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

test('auth failure stays auth_failed when close code is 4002', async () => {
  const lines: string[] = []
  const router = new HeadlessRouter({
    write: (line) => lines.push(line),
    launch: async () => { throw new Error('unused') },
    connectCast: async (_room, _opts, hooks) => {
      const err = new Error('auth')
      err.name = 'UpstreamAuthError'
      hooks.fail('close', 4002)
      hooks.fail('error', err)
    },
  })
  router.handle(JSON.stringify({ id: 'c', cmd: 'connect', roomNum: '1', rawHeaders: 'sessionid=s' }))
  await new Promise((r) => setTimeout(r, 0))
  const statuses = lines.map((line) => JSON.parse(line)).filter((row) => row.type === 'status')
  assert.equal(statuses.length, 1)
  assert.equal(statuses[0].state, 'auth_failed')
  assert.equal(statuses[0].code, undefined)
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

test('CLog.debug stays off stdout when headless redirects console first', async () => {
  const sidecarDir = path.dirname(fileURLToPath(import.meta.url))
  const dycastDir = path.resolve(sidecarDir, '../..')
  const headlessSrc = fs.readFileSync(path.join(sidecarDir, 'headless.ts'), 'utf8')
  const redirectAt = headlessSrc.indexOf('redirectHeadlessConsole()')
  const mainImportAt = headlessSrc.search(/import\(\s*['"]\.\/headless-main\.ts['"]\s*\)/)
  assert.ok(redirectAt >= 0)
  assert.ok(mainImportAt > redirectAt)
  assert.doesNotMatch(headlessSrc, /from\s+['"][^'"]*(?:request|logUtil|dycast)[^'"]*['"]/)

  const child = spawn(process.execPath, [
    path.join(dycastDir, 'node_modules/tsx/dist/cli.mjs'),
    '--tsconfig', 'tsconfig.sidecar.json',
    path.join(sidecarDir, 'headless-stdout-probe.ts'),
  ], { cwd: dycastDir })
  let stdout = ''
  let stderr = ''
  child.stdout.setEncoding('utf8')
  child.stderr.setEncoding('utf8')
  child.stdout.on('data', (chunk) => { stdout += chunk })
  child.stderr.on('data', (chunk) => { stderr += chunk })
  const code = await new Promise<number>((resolve, reject) => {
    child.on('error', reject)
    child.on('exit', (status) => resolve(status ?? 1))
  })
  assert.equal(code, 0, stderr)
  assert.equal(stdout, 'STDOUT_OK\n')
  assert.equal(stdout.includes('CLOG_DEBUG_MARKER'), false)
  assert.equal(stderr.includes('CLOG_DEBUG_MARKER'), true)
  assert.equal(stderr.includes('console.error replaced'), false)
})

test('empty signature and handshake rejection do not look like a drop', async () => {
  const lines: string[] = []
  const router = new HeadlessRouter({
    write: (line) => lines.push(line),
    launch: async () => { throw new Error('unused') },
    connectCast: async (_room, _opts, hooks) => {
      hooks.fail('error', new Error('empty_signature'))
    },
  })
  router.handle(JSON.stringify({ id: 's', cmd: 'connect', roomNum: '1', rawHeaders: 'a=b' }))
  await new Promise((resolve) => setTimeout(resolve, 0))
  const signatureStatus = JSON.parse(lines.filter((line) => line.includes('empty_signature'))[0])
  assert.equal(signatureStatus.state, 'connect_failed')

  const lines2: string[] = []
  const router2 = new HeadlessRouter({
    write: (line) => lines2.push(line),
    launch: async () => { throw new Error('unused') },
    connectCast: async (_room, _opts, hooks) => {
      hooks.fail('error', new Error('Unexpected server response: 200'))
      hooks.fail('close', 1006)
    },
  })
  router2.handle(JSON.stringify({ id: 'h', cmd: 'connect', roomNum: '1', rawHeaders: 'a=b' }))
  await new Promise((resolve) => setTimeout(resolve, 0))
  const statuses = lines2.map((line) => JSON.parse(line)).filter((row) => row.type === 'status')
  assert.equal(statuses.length, 1)
  assert.equal(statuses[0].state, 'connect_failed')
})

test('close before open is connect_failed and a received message stays a drop', async () => {
  const lines: string[] = []
  const router = new HeadlessRouter({
    write: (line) => lines.push(line),
    launch: async () => { throw new Error('unused') },
    connectCast: async (_room, _opts, hooks) => {
      hooks.fail('close', 1006)
    },
  })
  router.handle(JSON.stringify({ id: 'e', cmd: 'connect', roomNum: '1', rawHeaders: 'a=b' }))
  await new Promise((resolve) => setTimeout(resolve, 0))
  const early = lines.map((line) => JSON.parse(line)).filter((row) => row.type === 'status')
  assert.equal(early.length, 1)
  assert.equal(early[0].state, 'connect_failed')

  const lines2: string[] = []
  const router2 = new HeadlessRouter({
    write: (line) => lines2.push(line),
    launch: async () => { throw new Error('unused') },
    connectCast: async (_room, _opts, hooks) => {
      hooks.open()
      hooks.message([{ kind: 'text' }])
      hooks.fail('close', 1006)
    },
  })
  router2.handle(JSON.stringify({ id: 'm', cmd: 'connect', roomNum: '1', rawHeaders: 'a=b' }))
  await new Promise((resolve) => setTimeout(resolve, 0))
  const later = lines2.map((line) => JSON.parse(line)).filter((row) => row.type === 'status')
  assert.equal(later.map((row) => row.state).join(','), 'connected,closed')
})
