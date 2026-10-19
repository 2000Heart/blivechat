import assert from 'node:assert/strict'
import path from 'node:path'
import test from 'node:test'
import { fileURLToPath } from 'node:url'
import { getSignature } from '../core/signature.js'
import { loadMssdkFrontier } from './mssdk-runtime.ts'

test('mssdk frontierSign returns a 16 char X-Bogus', () => {
  const mssdkPath = path.join(path.dirname(fileURLToPath(import.meta.url)), '../../public/mssdk.js')
  const { frontierSign } = loadMssdkFrontier(mssdkPath)
  ;(globalThis as { __dy_frontierSign?: typeof frontierSign }).__dy_frontierSign = frontierSign
  const direct = frontierSign({ 'X-MS-STUB': 'abc' })
  assert.equal(Object.keys(direct).includes('X-Bogus'), true)
  assert.equal(String(direct['X-Bogus'] || '').length, 16)
  const sign = getSignature('7000000000000000000', '7000000000000000001')
  assert.equal(sign.length, 16)
})
