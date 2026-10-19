import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'
import test from 'node:test'
import { fileURLToPath } from 'node:url'
import { castHostUrl, upstreamHeadersRequest } from './browser-cast.ts'

test('cast page posts the cookie and does not set an upstream origin', () => {
  const posted = upstreamHeadersRequest('http://127.0.0.1:5173', 'sessionid=abc')
  assert.equal(posted.url, 'http://127.0.0.1:5173/__api/dycast/upstream-headers')
  assert.equal(JSON.parse(posted.body).raw, 'sessionid=abc')
  assert.equal(castHostUrl(), 'http://127.0.0.1:5173/cast-host.html')
  const html = fs.readFileSync(path.join(path.dirname(fileURLToPath(import.meta.url)), '../../cast-host.html'), 'utf8')
  assert.match(html, /<script src="\/mssdk.js"><\/script>/)
  assert.equal(html.includes('setUpstreamOrigin'), false)
})
