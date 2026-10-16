import readline from 'node:readline'
import { chromium } from 'playwright-core'
import { setUpstreamOrigin } from '../core/request.ts'
import { resolveBrowserExecutablePath } from './cookie-login-browser.ts'
import type { FakeBrowser, LoginMode } from './cookie-login-session.ts'
import { HeadlessRouter } from './headless-router.ts'

const writeLog = console.error.bind(console)
console.log = writeLog
console.info = writeLog
console.debug = writeLog
console.warn = writeLog

setUpstreamOrigin('https://live.douyin.com')

function envTimeoutMs(name: string, defaultSeconds: number): number {
  const raw = process.env[name]
  if (raw == null || raw.trim() === '') return defaultSeconds * 1000
  const parsed = Number(raw)
  if (!Number.isFinite(parsed)) return defaultSeconds * 1000
  return parsed * 1000
}

async function launch(mode: LoginMode): Promise<FakeBrowser> {
  const profileDir = process.env.DYCAST_LOGIN_PROFILE_DIR || ''
  if (!profileDir) throw new Error('DYCAST_LOGIN_PROFILE_DIR missing')
  const headless = mode === 'silent'
  const executablePath = resolveBrowserExecutablePath()
  const open = async (options: { headless: boolean; executablePath?: string; channel?: 'chrome' | 'msedge' }) => {
    const context = await chromium.launchPersistentContext(profileDir, options)
    const page = context.pages()[0] ?? (await context.newPage())
    return {
      async goto(url: string) {
        await page.goto(url, { waitUntil: 'domcontentloaded' })
      },
      url() {
        return page.url()
      },
      async cookies() {
        const cookies = await context.cookies()
        return cookies.map(({ name, value, domain }) => ({ name, value, domain }))
      },
      async close() {
        await context.close()
      },
    }
  }
  if (executablePath) return open({ headless, executablePath })
  let lastError: unknown
  for (const channel of ['chrome', 'msedge'] as const) {
    try {
      return await open({ headless, channel })
    } catch (err) {
      lastError = err
    }
  }
  throw lastError instanceof Error ? lastError : new Error('未找到浏览器，请设置 CHROME_PATH')
}

const router = new HeadlessRouter({
  write: (line) => {
    process.stdout.write(line)
  },
  launch,
  interactiveTimeoutMs: envTimeoutMs('DYCAST_LOGIN_TIMEOUT_SECONDS', 300),
  silentTimeoutMs: envTimeoutMs('DYCAST_SILENT_TIMEOUT_SECONDS', 30),
})

process.stdout.write(`${JSON.stringify({ type: 'ready' })}\n`)

const rl = readline.createInterface({ input: process.stdin, crlfDelay: Infinity })
rl.on('line', (line) => {
  if (!line.trim()) return
  router.handle(line)
})
