import fs from 'node:fs'
import path from 'node:path'
import { chromium, type BrowserContext, type LaunchPersistentContextOptions } from 'playwright-core'
import { CookieLoginSession, type FakeBrowser, type LoginMode } from './cookie-login-session.ts'

const LOOPBACK_ADDRESSES = new Set(['127.0.0.1', '::1', '::ffff:127.0.0.1'])

export function isLoopbackAddress(remoteAddress: string | undefined): boolean {
  return remoteAddress !== undefined && LOOPBACK_ADDRESSES.has(remoteAddress)
}

export function resolveBrowserExecutablePath(candidates?: string[]): string | null {
  const envPath = (process.env.CHROME_PATH || '').trim()
  if (envPath && fs.existsSync(envPath)) return envPath
  for (const candidate of candidates ?? platformBrowserCandidates()) {
    if (candidate && fs.existsSync(candidate)) return candidate
  }
  return null
}

function platformBrowserCandidates(): string[] {
  if (process.platform === 'darwin') {
    return [
      '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
      '/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge',
    ]
  }
  if (process.platform === 'win32') {
    const localAppData = process.env.LOCALAPPDATA || ''
    const programFiles = process.env.PROGRAMFILES || ''
    return [
      path.join(localAppData, 'Google/Chrome/Application/chrome.exe'),
      path.join(programFiles, 'Google/Chrome/Application/chrome.exe'),
      path.join(localAppData, 'Microsoft/Edge/Application/msedge.exe'),
      path.join(programFiles, 'Microsoft/Edge/Application/msedge.exe'),
    ]
  }
  return ['/usr/bin/google-chrome', '/usr/bin/chromium', '/usr/bin/chromium-browser']
}

async function wrapPersistentContext(context: BrowserContext): Promise<FakeBrowser> {
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

async function launchWithOptions(
  profileDir: string,
  options: LaunchPersistentContextOptions,
): Promise<FakeBrowser> {
  const context = await chromium.launchPersistentContext(profileDir, options)
  return wrapPersistentContext(context)
}

async function launchPersistentDouyin(mode: LoginMode): Promise<FakeBrowser> {
  const profileDir = process.env.DYCAST_LOGIN_PROFILE_DIR || ''
  if (!profileDir) {
    throw new Error('DYCAST_LOGIN_PROFILE_DIR missing')
  }
  const headless = mode === 'silent'
  const executablePath = resolveBrowserExecutablePath()
  if (executablePath) {
    return launchWithOptions(profileDir, { headless, executablePath })
  }

  for (const channel of ['chrome', 'msedge'] as const) {
    try {
      return await launchWithOptions(profileDir, { headless, channel })
    } catch {
      // try next channel or platform path
    }
  }

  for (const candidate of platformBrowserCandidates()) {
    if (!fs.existsSync(candidate)) continue
    try {
      return await launchWithOptions(profileDir, { headless, executablePath: candidate })
    } catch {
      // try next existing path
    }
  }

  throw new Error('未找到浏览器，请设置 CHROME_PATH')
}

function envTimeoutMs(name: string, defaultSeconds: number): number {
  const raw = process.env[name]
  if (raw == null || raw.trim() === '') return defaultSeconds * 1000
  const parsed = Number(raw)
  if (!Number.isFinite(parsed)) return defaultSeconds * 1000
  return parsed * 1000
}

export function createCookieLoginSessionFromEnv(): CookieLoginSession {
  return new CookieLoginSession({
    launch: launchPersistentDouyin,
    interactiveTimeoutMs: envTimeoutMs('DYCAST_LOGIN_TIMEOUT_SECONDS', 300),
    silentTimeoutMs: envTimeoutMs('DYCAST_SILENT_TIMEOUT_SECONDS', 30),
  })
}
