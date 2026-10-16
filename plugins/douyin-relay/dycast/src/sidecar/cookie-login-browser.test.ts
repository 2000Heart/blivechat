import assert from 'node:assert/strict'
import fs from 'node:fs'
import os from 'node:os'
import path from 'node:path'
import test from 'node:test'
import {
  createCookieLoginSessionFromEnv,
  isLoopbackAddress,
  resolveBrowserExecutablePath,
} from './cookie-login-browser.ts'

test('loopback addresses', () => {
  assert.equal(isLoopbackAddress('127.0.0.1'), true)
  assert.equal(isLoopbackAddress('::1'), true)
  assert.equal(isLoopbackAddress('::ffff:127.0.0.1'), true)
  assert.equal(isLoopbackAddress('192.168.1.8'), false)
  assert.equal(isLoopbackAddress(undefined), false)
})

function withEnv(name: string, value: string | undefined, fn: () => void) {
  const prev = process.env[name]
  if (value === undefined) delete process.env[name]
  else process.env[name] = value
  try {
    fn()
  } finally {
    if (prev === undefined) delete process.env[name]
    else process.env[name] = prev
  }
}

test('resolveBrowserExecutablePath uses existing CHROME_PATH only', () => {
  withEnv('CHROME_PATH', undefined, () => {
    assert.equal(resolveBrowserExecutablePath(), null)
  })
  withEnv('CHROME_PATH', path.join(os.tmpdir(), 'dycast-no-such-chrome'), () => {
    assert.equal(resolveBrowserExecutablePath(), null)
  })
  const tmp = path.join(os.tmpdir(), `dycast-chrome-path-${process.pid}`)
  fs.writeFileSync(tmp, '')
  try {
    withEnv('CHROME_PATH', tmp, () => {
      assert.equal(resolveBrowserExecutablePath(), tmp)
    })
  } finally {
    fs.unlinkSync(tmp)
  }
})

test('missing DYCAST_LOGIN_PROFILE_DIR becomes error without launching', async () => {
  const prev = process.env.DYCAST_LOGIN_PROFILE_DIR
  delete process.env.DYCAST_LOGIN_PROFILE_DIR
  try {
    const session = createCookieLoginSessionFromEnv()
    session.start('silent')
    for (let i = 0; i < 500; i++) {
      if (session.status(false).phase !== 'running') break
      await new Promise((r) => setImmediate(r))
    }
    const st = session.status(false)
    assert.equal(st.phase, 'error')
    assert.equal(st.message, 'DYCAST_LOGIN_PROFILE_DIR missing')
  } finally {
    if (prev === undefined) delete process.env.DYCAST_LOGIN_PROFILE_DIR
    else process.env.DYCAST_LOGIN_PROFILE_DIR = prev
  }
})
