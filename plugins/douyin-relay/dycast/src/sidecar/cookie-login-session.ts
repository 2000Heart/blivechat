import {
  judgeDouyinLogin,
  serializeDouyinCookies,
  type CookieRecord,
} from './cookie-login-rules.ts'

export type LoginPhase = 'idle' | 'running' | 'done' | 'need_login' | 'error' | 'cancelled'

export type FakeBrowser = {
  goto(url: string): Promise<void>
  url(): string
  cookies(): Promise<CookieRecord[]>
  close(): Promise<void>
}

export type LoginMode = 'interactive' | 'silent'

type SessionOptions = {
  launch: (mode: LoginMode) => Promise<FakeBrowser>
  now?: () => number
  sleep?: (ms: number) => Promise<void>
  interactiveTimeoutMs: number
  silentTimeoutMs: number
}

type StatusBody = {
  phase: LoginPhase
  mode: string | null
  cookieLength: number
  message: string
  updatedAt: number
  cookie?: string
}

export class CookieLoginSession {
  private readonly launch: SessionOptions['launch']
  private readonly now: () => number
  private readonly sleep: (ms: number) => Promise<void>
  private readonly interactiveTimeoutMs: number
  private readonly silentTimeoutMs: number

  private phase: LoginPhase = 'idle'
  private mode: LoginMode | null = null
  private message = ''
  private cookie = ''
  private startedAt = 0
  private updatedAt = 0
  private aborted = false

  constructor(opts: SessionOptions) {
    this.launch = opts.launch
    this.now = opts.now ?? Date.now
    this.sleep = opts.sleep ?? ((ms) => new Promise((r) => setTimeout(r, ms)))
    this.interactiveTimeoutMs = opts.interactiveTimeoutMs
    this.silentTimeoutMs = opts.silentTimeoutMs
  }

  start(mode: LoginMode): { status: number; body: { phase: LoginPhase; mode: string | null; message: string } } {
    if (this.phase === 'running') {
      return {
        status: 409,
        body: { phase: this.phase, mode: this.mode, message: 'login already running' },
      }
    }
    this.phase = 'running'
    this.mode = mode
    this.cookie = ''
    this.message = ''
    this.aborted = false
    this.startedAt = this.now()
    this.updatedAt = this.startedAt
    void this.run(mode)
    return {
      status: 202,
      body: { phase: this.phase, mode: this.mode, message: this.message },
    }
  }

  status(includeCookie: boolean): StatusBody {
    const body: StatusBody = {
      phase: this.phase,
      mode: this.mode,
      cookieLength: this.cookie.length,
      message: this.message,
      updatedAt: this.updatedAt,
    }
    if (includeCookie) body.cookie = this.cookie
    return body
  }

  consumeCookie(): string {
    const value = this.cookie
    this.cookie = ''
    return value
  }

  cancel(): void {
    if (this.phase === 'running') this.aborted = true
  }

  private async run(mode: LoginMode): Promise<void> {
    let browser: FakeBrowser | undefined
    try {
      browser = await this.launch(mode)
      await browser.goto('https://live.douyin.com/')
      await this.poll(browser, mode)
    } catch (err) {
      if (this.phase !== 'running') return
      if (browser) {
        try {
          await browser.close()
        } catch {
          // ignore close errors after a launch/goto failure
        }
      }
      this.message = err instanceof Error ? err.message : String(err)
      this.phase = 'error'
      this.updatedAt = this.now()
    }
  }

  private async poll(browser: FakeBrowser, mode: LoginMode): Promise<void> {
    const timeoutMs = mode === 'interactive' ? this.interactiveTimeoutMs : this.silentTimeoutMs
    while (true) {
      if (await this.stopIfNeeded(browser, timeoutMs)) return

      const cookies = await browser.cookies()
      const judged = judgeDouyinLogin({ cookies, url: browser.url(), mode })

      if (!judged.ok) {
        if (
          mode === 'silent' &&
          (judged.reason === 'login_url' || judged.reason === 'missing_session_cookie')
        ) {
          await browser.close()
          this.message = judged.reason
          this.phase = 'need_login'
          this.updatedAt = this.now()
          return
        }
        await this.sleep(1000)
        continue
      }

      if (mode === 'silent') {
        await this.succeed(browser, cookies)
        return
      }

      const judgedAt = this.now()
      while (this.now() - judgedAt < 1000) {
        if (await this.stopIfNeeded(browser, timeoutMs)) return
        const delta = this.now() - judgedAt
        if (delta >= 1000) break
        await this.sleep(Math.min(200, 1000 - delta))
      }

      const cookies2 = await browser.cookies()
      const judged2 = judgeDouyinLogin({ cookies: cookies2, url: browser.url(), mode })
      if (judged2.ok) {
        await this.succeed(browser, cookies2)
        return
      }
    }
  }

  private async stopIfNeeded(browser: FakeBrowser, timeoutMs: number): Promise<boolean> {
    if (this.aborted) {
      await browser.close()
      this.phase = 'cancelled'
      this.updatedAt = this.now()
      return true
    }
    if (this.now() - this.startedAt >= timeoutMs) {
      await browser.close()
      this.message = 'timeout'
      this.phase = 'need_login'
      this.updatedAt = this.now()
      return true
    }
    return false
  }

  private async succeed(browser: FakeBrowser, cookies: CookieRecord[]): Promise<void> {
    const serialized = serializeDouyinCookies(cookies)
    await browser.close()
    this.cookie = serialized
    this.phase = 'done'
    this.updatedAt = this.now()
  }
}
