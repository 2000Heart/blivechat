import { spawn, type ChildProcess } from 'node:child_process'
import path from 'node:path'
import { chromium, type Browser } from 'playwright-core'
import { resolveBrowserExecutablePath } from './cookie-login-browser.ts'

export const CAST_ORIGIN = 'http://127.0.0.1:5173'

export function castHostUrl(origin = CAST_ORIGIN): string {
  return `${origin.replace(/\/$/, '')}/cast-host.html`
}

export function upstreamHeadersRequest(origin: string, cookie: string): { url: string; body: string } {
  return {
    url: `${origin.replace(/\/$/, '')}/__api/dycast/upstream-headers`,
    body: JSON.stringify({ raw: cookie }),
  }
}

type CastHooks = {
  open: () => void
  message: (payload: unknown) => void
  fail: (status: string, detail?: unknown) => void
  ready: (cast: { close: (code?: number, reason?: string) => void }) => void
}

type CastEvent = { type?: string; payload?: unknown; message?: string; code?: number }

let viteChild: ChildProcess | null = null

export function stopCastVite(): void {
  if (!viteChild) return
  viteChild.kill()
  viteChild = null
}

async function ping(url: string, timeoutMs: number): Promise<boolean> {
  const started = Date.now()
  while (Date.now() - started < timeoutMs) {
    try {
      const res = await fetch(url)
      if (res.status < 500) return true
    } catch {
      // Vite is still starting.
    }
    await new Promise((resolve) => setTimeout(resolve, 200))
  }
  return false
}

export async function ensureCastVite(origin = CAST_ORIGIN): Promise<void> {
  const pageUrl = castHostUrl(origin)
  if (await ping(pageUrl, 400)) return
  if (!viteChild) {
    const viteBin = path.join(process.cwd(), 'node_modules', 'vite', 'bin', 'vite.js')
    viteChild = spawn(process.execPath, [viteBin, '--host', '127.0.0.1', '--port', '5173', '--strictPort'], {
      cwd: process.cwd(),
      stdio: 'ignore',
    })
    viteChild.on('exit', () => {
      viteChild = null
    })
  }
  if (!(await ping(pageUrl, 20000))) throw new Error('vite_unavailable')
}

const CAST_USER_AGENT =
  'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36'

async function launchCastBrowser(): Promise<Browser> {
  const executablePath = resolveBrowserExecutablePath()
  if (executablePath) return chromium.launch({ executablePath, headless: true })
  try {
    return await chromium.launch({ channel: 'chrome', headless: true })
  } catch {
    return chromium.launch({ channel: 'msedge', headless: true })
  }
}

export async function connectBrowserCast(
  room: string,
  cookie: string,
  hooks: CastHooks,
  origin = CAST_ORIGIN,
): Promise<void> {
  try {
    await ensureCastVite(origin)
    const posted = upstreamHeadersRequest(origin, cookie)
    const headersRes = await fetch(posted.url, {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: posted.body,
    })
    if (!headersRes.ok) throw new Error('cookie_post_failed')
    const browser = await launchCastBrowser()
    const page = await browser.newContext({ userAgent: CAST_USER_AGENT }).then((context) => context.newPage())
    await page.exposeBinding('__dyCastEvent', async (_source, evt: CastEvent) => {
      if (evt?.type === 'open') {
        hooks.open()
        return
      }
      if (evt?.type === 'message') {
        hooks.message(evt.payload)
        return
      }
      if (evt?.type === 'error') {
        hooks.fail('error', new Error(evt.message || 'error'))
        return
      }
      if (evt?.type === 'close') {
        hooks.fail('close', typeof evt.code === 'number' ? evt.code : 1006)
      }
    })
    hooks.ready({
      close() {
        void page.evaluate(() => {
          const cast = (window as unknown as { __dyCast?: { close?: (code: number, reason: string) => void } }).__dyCast
          cast?.close?.(1000, 'disconnect')
        }).finally(() => {
          void browser.close()
        })
      },
    })
    const url = `${castHostUrl(origin)}?room=${encodeURIComponent(room)}`
    await page.goto(url, { waitUntil: 'domcontentloaded' })
  } catch (err) {
    const error = err instanceof Error ? err : new Error('browser_missing')
    if (/Executable doesn't exist|browser_missing|未找到浏览器/i.test(error.message)) {
      hooks.fail('error', new Error('browser_missing'))
      return
    }
    hooks.fail('error', error)
  }
}
