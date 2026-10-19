import fs from 'node:fs'
import vm from 'node:vm'
import { createRequire } from 'node:module'

const LIVE_ORIGIN = 'https://live.douyin.com'

export function loadMssdkFrontier(mssdkPath: string): {
  frontierSign: (payload: Record<string, unknown>) => Record<string, unknown>
} {
  const code = fs.readFileSync(mssdkPath, 'utf8')
  const nodeRequire = createRequire(mssdkPath)
  const sandbox = {
    location: {
      origin: LIVE_ORIGIN,
      protocol: 'https:',
      host: 'live.douyin.com',
      hostname: 'live.douyin.com',
      port: '',
      href: `${LIVE_ORIGIN}/`,
    },
    navigator: {
      userAgent: 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36',
      appVersion: '5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36',
      appCodeName: 'Mozilla',
    },
    document: {
      cookie: '',
      referrer: '',
      visibilityState: 'visible',
      hidden: false,
      addEventListener() {},
      removeEventListener() {},
      createEvent: () => ({ initEvent() {} }),
    },
    setTimeout,
    clearTimeout,
    setInterval,
    clearInterval,
    require: nodeRequire,
  } as Record<string, unknown>
  sandbox.window = sandbox
  sandbox.self = sandbox
  sandbox.globalThis = sandbox
  vm.runInNewContext(code, sandbox, { filename: 'mssdk.js' })
  const crawler = sandbox.byted_acrawler as { frontierSign?: (payload: Record<string, unknown>) => Record<string, unknown> } | undefined
  if (!crawler || typeof crawler.frontierSign !== 'function') {
    throw new Error('frontierSign missing')
  }
  return { frontierSign: (payload) => crawler.frontierSign!(payload) }
}
