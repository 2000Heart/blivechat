import assert from 'node:assert/strict'
import test from 'node:test'
import { getImInfo, setUpstreamOrigin } from './request.ts'

test('empty im body keeps the decoded cursor empty', async () => {
  setUpstreamOrigin('https://live.douyin.com')
  const original = globalThis.fetch
  globalThis.fetch = async (input: RequestInfo | URL) => {
    const url = String(input)
    if (url.includes('/webcast/im/fetch')) {
      return new Response(new Uint8Array(), { status: 200, headers: { 'content-type': 'application/json' } })
    }
    return new Response('not-im', { status: 500 })
  }
  try {
    const info = await getImInfo('7000000000000000001', '7000000000000000002', true)
    assert.equal(info.pushServer, undefined)
    assert.equal(info.cursor, undefined)
    assert.equal(info.internalExt, undefined)
  } finally {
    globalThis.fetch = original
  }
})
