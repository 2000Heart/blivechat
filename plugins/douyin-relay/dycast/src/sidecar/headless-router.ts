import fs from 'node:fs'
import path from 'node:path'
import { createRequire } from 'node:module'
import {
  CookieLoginSession,
  type FakeBrowser,
  type LoginMode,
} from './cookie-login-session.ts'
import { probeLivePage, type ProbeLivePageResult } from './live-probe.ts'
import { loadMssdkFrontier } from './mssdk-runtime.ts'

type ConnectOptions = { maxReconnectCount?: number; strictIm?: boolean }

type ConnectHooks = {
  fail: (status: string, detail?: unknown) => void
  open: () => void
  message: (payload: unknown) => void
  ready: (cast: ClosableCast) => void
}

type ProbeFn = (roomNum: string, rawHeaders: string) => Promise<ProbeLivePageResult>

type ConnectCastFn = (
  room: string,
  options: ConnectOptions,
  hooks: ConnectHooks,
  cookie: string,
) => Promise<void>

type Command = {
  id?: string
  cmd?: string
  mode?: LoginMode
  roomNum?: string
  rawHeaders?: string
}

type Inflight = {
  id: string
  kind: 'probe' | 'connect'
  generation: number
  cancelled: boolean
  terminal: boolean
  sawError: boolean
  sawClose: boolean
  sawOpen: boolean
  sawMessage: boolean
  pendingError: unknown
  pendingCode: number | null
  failTimer?: ReturnType<typeof setTimeout>
}

type ClosableCast = {
  close: (code?: number, reason?: string) => void
}

let castRuntimeReady = false

function isAuthError(error: unknown): boolean {
  if (!error || typeof error !== 'object') return false
  const status = (error as { status?: number }).status
  if (status === 401 || status === 403) return true
  if (!(error instanceof Error)) return false
  return error.message === 'auth' || error.name === 'UpstreamAuthError'
}

function ensureCastRuntime(): void {
  if (castRuntimeReady) return
  const g = globalThis as {
    WebSocket?: unknown
    __dy_frontierSign?: (payload: Record<string, unknown>) => Record<string, unknown>
    byted_acrawler?: { frontierSign?: (payload: Record<string, unknown>) => Record<string, unknown> }
    window?: { byted_acrawler?: unknown }
  }
  try {
    const nodeRequire = createRequire(import.meta.url)
    const wsMod = nodeRequire('ws') as { WebSocket?: unknown }
    g.WebSocket = wsMod.WebSocket || wsMod
  } catch {
    // DyCast surfaces a missing WebSocket when connect runs.
  }

  const mssdkPath = path.join(process.cwd(), 'public', 'mssdk.js')
  if (!fs.existsSync(mssdkPath)) {
    castRuntimeReady = true
    return
  }
  try {
    const loaded = loadMssdkFrontier(mssdkPath)
    g.__dy_frontierSign = (payload) => loaded.frontierSign(payload)
    g.byted_acrawler = { frontierSign: loaded.frontierSign }
  } catch {
    // frontierSign 缺失时不抛错，getSignature 走原回退。
  }
  castRuntimeReady = true
}

type HeadlessRouterOptions = {
  write: (line: string) => void
  launch: (mode: LoginMode) => Promise<FakeBrowser>
  interactiveTimeoutMs?: number
  silentTimeoutMs?: number
  probe?: ProbeFn
  connectCast?: ConnectCastFn
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
  private readonly probeFn: ProbeFn
  private readonly connectCastFn: ConnectCastFn | undefined
  private inflight: Inflight | null = null
  private generation = 0
  private pendingCookie = ''
  private activeCast: ClosableCast | null = null

  private loginId = ''

  constructor(opts: HeadlessRouterOptions) {
    this.write = opts.write
    this.session = new CookieLoginSession({
      launch: opts.launch,
      interactiveTimeoutMs: opts.interactiveTimeoutMs ?? 300_000,
      silentTimeoutMs: opts.silentTimeoutMs ?? 30_000,
      onPhase: (st) => {
        if (st.phase === 'running' || st.phase === 'idle') return
        this.writeLine({
          type: 'login',
          id: this.loginId,
          phase: st.phase,
          mode: st.mode,
          cookieLength: st.cookieLength,
          message: st.message,
        })
      },
    })
    this.probeFn = opts.probe ?? ((roomNum, rawHeaders) => probeLivePage(roomNum, rawHeaders, globalThis.fetch))
    this.connectCastFn = opts.connectCast
  }

  seedDoneCookie(cookie: string): void {
    this.session.seedDoneState(cookie)
  }

  handle(line: string): void {
    let parsed: Command
    try {
      parsed = JSON.parse(line) as Command
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
      case 'probe_live':
        this.handleProbe(id, parsed.roomNum, parsed.rawHeaders)
        return
      case 'connect':
        this.handleConnect(id, parsed.roomNum, parsed.rawHeaders)
        return
      case 'disconnect':
        this.handleDisconnect(id)
        return
      default:
        this.emitResult(id, { ok: false, error: 'bad_args' })
    }
  }

  private handleProbe(id: string, roomNum: string | undefined, rawHeaders: string | undefined): void {
    if (!roomNum) {
      this.emitResult(id, { ok: false, error: 'bad_args' })
      return
    }
    if (this.inflight) {
      this.emitResult(id, { ok: false, error: 'busy' })
      return
    }
    this.emitResult(id, { ok: true, error: '' })
    const generation = ++this.generation
    this.inflight = this.makeInflight(id, 'probe', generation)
    void Promise.resolve(this.probeFn(roomNum, rawHeaders ?? '')).then(
      (result) => {
        if (!this.owns(generation)) return
        this.inflight = null
        this.writeLine({
          type: 'probe',
          id,
          ok: result.ok,
          living: result.living,
          roomStatus: result.roomStatus,
          error: result.error,
        })
      },
      () => {
        if (!this.owns(generation)) return
        this.inflight = null
        this.writeLine({
          type: 'probe',
          id,
          ok: false,
          living: false,
          roomStatus: 'unknown',
          error: 'probe_fail',
        })
      },
    )
  }

  private handleConnect(id: string, roomNum: string | undefined, rawHeaders: string | undefined): void {
    if (!roomNum) {
      this.emitResult(id, { ok: false, error: 'bad_args' })
      return
    }
    if (this.inflight) {
      this.emitResult(id, { ok: false, error: 'busy' })
      return
    }
    this.emitResult(id, { ok: true, error: '' })
    const generation = ++this.generation
    this.inflight = this.makeInflight(id, 'connect', generation)
    this.pendingCookie = rawHeaders ?? ''
    const options: ConnectOptions = { maxReconnectCount: 0, strictIm: true }
    const hooks: ConnectHooks = {
      fail: (status: string, detail?: unknown) => {
        if (status === 'close') {
          this.noteConnectFailure(generation, {
            signal: 'close',
            ...(typeof detail === 'number' ? { code: detail } : {}),
          })
          return
        }
        this.noteConnectFailure(generation, {
          signal: 'error',
          ...(detail !== undefined ? { error: detail } : {}),
        })
      },
      open: () => {
        const slot = this.inflight
        if (!slot || slot.generation !== generation || slot.cancelled || slot.terminal) return
        slot.sawOpen = true
        this.writeLine({ type: 'status', state: 'connected', id })
      },
      message: (payload: unknown) => {
        const slot = this.inflight
        if (!slot || slot.generation !== generation || slot.cancelled || slot.terminal) return
        slot.sawMessage = true
        this.writeLine({ type: 'messages', payload })
      },
      ready: (cast: ClosableCast) => {
        if (!this.owns(generation)) return
        this.activeCast = cast
      },
    }
    const run = this.connectCastFn
      ? this.connectCastFn(roomNum, options, hooks, this.pendingCookie)
      : this.defaultConnectCast(roomNum, options, generation, hooks)
    void Promise.resolve(run).catch((err: unknown) => {
      this.noteConnectFailure(generation, { error: err })
    })
  }

  private async defaultConnectCast(
    room: string,
    options: ConnectOptions,
    generation: number,
    hooks: ConnectHooks,
  ): Promise<void> {
    const [{ DyCast }, requestMod] = await Promise.all([
      import('../core/dycast.ts'),
      import('../core/request.ts'),
    ])
    if (!this.owns(generation)) return
    requestMod.clearUpstreamJar()
    ;(globalThis as { __dy_cookie?: string }).__dy_cookie = this.pendingCookie
    ensureCastRuntime()
    const cast = new DyCast(room, {
      maxReconnectCount: options.maxReconnectCount ?? 0,
      strictIm: options.strictIm === true,
    })
    hooks.ready(cast)
    cast.on('open', () => {
      hooks.open()
    })
    cast.on('message', ((payload: unknown) => {
      hooks.message(payload)
    }) as (...args: never[]) => void)
    cast.on('error', ((err: unknown) => {
      this.noteConnectFailure(generation, { error: err })
    }) as (...args: never[]) => void)
    cast.on('close', ((code: number) => {
      this.noteConnectFailure(generation, { code })
    }) as (...args: never[]) => void)
    await cast.connect()
    if (!this.owns(generation)) cast.close(1000, 'disconnect')
  }

  private handleDisconnect(id: string): void {
    const slot = this.inflight
    if (slot?.failTimer) clearTimeout(slot.failTimer)
    if (slot) {
      slot.cancelled = true
      slot.terminal = true
    }
    this.inflight = null
    const cast = this.activeCast
    this.activeCast = null
    if (cast) cast.close(1000, 'disconnect')
    void import('../core/request.ts')
      .then((requestMod) => requestMod.clearUpstreamJar())
      .catch(() => undefined)
    this.emitResult(id, { ok: true, error: '' })
    this.writeLine({ type: 'status', state: 'disconnected', id })
  }

  private makeInflight(id: string, kind: Inflight['kind'], generation: number): Inflight {
    return {
      id,
      kind,
      generation,
      cancelled: false,
      terminal: false,
      sawError: false,
      sawClose: false,
      sawOpen: false,
      sawMessage: false,
      pendingError: null,
      pendingCode: null,
    }
  }

  private owns(generation: number): boolean {
    return !!this.inflight && this.inflight.generation === generation && !this.inflight.cancelled && !this.inflight.terminal
  }

  private noteConnectFailure(
    generation: number,
    update: { error?: unknown; code?: number; signal?: 'error' | 'close' },
  ): void {
    const slot = this.inflight
    if (!slot || slot.generation !== generation || slot.cancelled || slot.terminal) return
    if (update.error !== undefined) {
      slot.pendingError = update.error
      slot.sawError = true
    }
    if (update.signal === 'error') slot.sawError = true
    if (update.signal === 'close') slot.sawClose = true
    if (update.code !== undefined) {
      slot.pendingCode = update.code
      slot.sawClose = true
    }
    if (slot.failTimer) return
    slot.failTimer = setTimeout(() => {
      this.flushConnect(generation)
    }, 0)
  }

  private flushConnect(generation: number): void {
    const slot = this.inflight
    if (!slot || slot.generation !== generation || slot.cancelled || slot.terminal) return
    if (!slot.sawError && !slot.sawClose && slot.pendingError == null && slot.pendingCode == null) return
    slot.terminal = true
    if (slot.failTimer) clearTimeout(slot.failTimer)
    const { id, pendingError, pendingCode, sawOpen, sawMessage } = slot
    this.inflight = null
    this.activeCast = null
    this.writeTerminalStatus(id, pendingCode, pendingError, sawOpen, sawMessage)
  }

  private writeTerminalStatus(
    id: string,
    code: number | null,
    error: unknown,
    sawOpen: boolean,
    sawMessage: boolean,
  ): void {
    const message = error instanceof Error ? error.message : ''
    if (isAuthError(error)) {
      this.writeLine({ type: 'status', state: 'auth_failed', id })
      return
    }
    if (message === 'empty_signature' || message.includes('Unexpected server response')) {
      this.writeLine({ type: 'status', state: 'connect_failed', error: message, id })
      return
    }
    if (message === 'im_fetch_failed') {
      this.writeLine({ type: 'status', state: 'closed', error: 'im_fetch_failed', id })
      return
    }
    if (code === 4001 || code === 1000) {
      this.writeLine({ type: 'status', state: 'live_end', code, id })
      return
    }
    if (!sawOpen || !sawMessage) {
      this.writeLine({ type: 'status', state: 'connect_failed', error: message, id })
      return
    }
    if (code != null) {
      this.writeLine({ type: 'status', state: 'closed', code, id })
      return
    }
    this.writeLine({ type: 'status', state: 'closed', id })
  }

  private handleLoginStart(id: string, mode: LoginMode | undefined): void {
    if (mode !== 'interactive' && mode !== 'silent') {
      this.emitResult(id, { ok: false, error: 'bad_args' })
      return
    }
    const previousLoginId = this.loginId
    this.loginId = id
    const res = this.session.start(mode)
    if (res.status === 409) {
      this.loginId = previousLoginId
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

  private writeLine(payload: Record<string, unknown>): void {
    this.write(JSON.stringify(payload) + '\n')
  }
}
