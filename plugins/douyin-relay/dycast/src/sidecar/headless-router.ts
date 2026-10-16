import {
  CookieLoginSession,
  type FakeBrowser,
  type LoginMode,
} from './cookie-login-session.ts'

type HeadlessRouterOptions = {
  write: (line: string) => void
  launch: (mode: LoginMode) => Promise<FakeBrowser>
  interactiveTimeoutMs?: number
  silentTimeoutMs?: number
}

type ResultPayload = {
  ok: boolean
  error?: string
  phase?: string
  mode?: string | null
  cookieLength?: number
  message?: string
  cookie?: string
}

export class HeadlessRouter {
  private readonly write: (line: string) => void
  private readonly session: CookieLoginSession

  constructor(opts: HeadlessRouterOptions) {
    this.write = opts.write
    this.session = new CookieLoginSession({
      launch: opts.launch,
      interactiveTimeoutMs: opts.interactiveTimeoutMs ?? 300_000,
      silentTimeoutMs: opts.silentTimeoutMs ?? 30_000,
    })
  }

  seedDoneCookie(cookie: string): void {
    this.session.seedDoneState(cookie)
  }

  handle(line: string): void {
    let parsed: { id?: string; cmd?: string; mode?: LoginMode }
    try {
      parsed = JSON.parse(line) as { id?: string; cmd?: string; mode?: LoginMode }
    } catch {
      this.emitResult('', { ok: false, error: 'bad_args' })
      return
    }

    const id = parsed.id
    const cmd = parsed.cmd
    if (!id || !cmd) {
      this.emitResult(id || '', { ok: false, error: 'bad_args' })
      return
    }

    switch (cmd) {
      case 'login_start':
        this.handleLoginStart(id, parsed.mode)
        return
      case 'login_consume':
        this.handleLoginConsume(id)
        return
      case 'login_status':
        this.handleLoginStatus(id)
        return
      case 'login_cancel':
        this.handleLoginCancel(id)
        return
      default:
        this.emitResult(id, { ok: false, error: 'bad_args' })
    }
  }

  private handleLoginStart(id: string, mode: LoginMode | undefined): void {
    if (mode !== 'interactive' && mode !== 'silent') {
      this.emitResult(id, { ok: false, error: 'bad_args' })
      return
    }
    const res = this.session.start(mode)
    if (res.status === 409) {
      this.emitResult(id, {
        ok: false,
        error: 'busy',
        phase: res.body.phase,
        mode: res.body.mode,
        message: res.body.message,
      })
      return
    }
    this.emitResult(id, {
      ok: true,
      phase: 'running',
      mode: res.body.mode,
      message: res.body.message,
    })
  }

  private handleLoginConsume(id: string): void {
    const st = this.session.status(false)
    if (st.phase !== 'done') {
      this.emitResult(id, {
        ok: false,
        error: 'not_ready',
        phase: st.phase,
        mode: st.mode,
        cookieLength: st.cookieLength,
        message: st.message,
      })
      return
    }
    const cookie = this.session.consumeCookie()
    const after = this.session.status(false)
    this.emitResult(id, {
      ok: true,
      phase: 'idle',
      mode: after.mode,
      cookieLength: cookie.length,
      message: after.message,
      cookie,
    })
  }

  private handleLoginStatus(id: string): void {
    const st = this.session.status(false)
    this.emitResult(id, {
      ok: true,
      phase: st.phase,
      mode: st.mode,
      cookieLength: st.cookieLength,
      message: st.message,
    })
  }

  private handleLoginCancel(id: string): void {
    this.session.cancel()
    const st = this.session.status(false)
    this.emitResult(id, {
      ok: true,
      phase: st.phase,
      mode: st.mode,
      cookieLength: st.cookieLength,
      message: st.message,
    })
  }

  private emitResult(id: string, payload: ResultPayload): void {
    this.write(JSON.stringify({ type: 'result', id, ...payload }) + '\n')
  }
}
