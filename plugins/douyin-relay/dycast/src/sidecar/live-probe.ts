export function extractRoomStatus(html: string): number | null {
  const normalized = html.replace(/\\\\"/g, '"').replace(/\\"/g, '"')
  const match = normalized.match(/"status"\s*:\s*([1-4])/)
  if (!match) {
    return null
  }
  return Number.parseInt(match[1], 10)
}

export function isLivingStatus(status: number | null): boolean {
  return status === 2
}

export function classifyUpstream(input: {
  httpStatus: number
  finalUrl: string
  html: string
}): 'ok' | 'auth' | 'probe_fail' {
  const { httpStatus, finalUrl, html } = input

  if (httpStatus === 401 || httpStatus === 403) {
    return 'auth'
  }
  if (finalUrl.includes('/passport/') || finalUrl.includes('/login')) {
    return 'auth'
  }

  const status = extractRoomStatus(html)
  if (status !== null) {
    return 'ok'
  }

  const lowerHtml = html.toLowerCase()
  if (html.includes('登录') || lowerHtml.includes('login')) {
    return 'auth'
  }

  return 'probe_fail'
}

export type DirectRequestKind = 'live_page' | 'im_fetch' | 'user'

export function directRequestKind(url: string): DirectRequestKind | 'other' {
  let pathname = url
  try {
    pathname = new URL(url, 'https://live.douyin.com').pathname
  } catch {
    return 'other'
  }
  if (pathname.includes('/webcast/im/fetch')) return 'im_fetch'
  if (pathname.includes('/webcast/user')) return 'user'
  if (/^\/[^/]+\/?$/.test(pathname)) return 'live_page'
  return 'other'
}

export function classifyDirectRequest(input: {
  kind: DirectRequestKind
  httpStatus: number
  finalUrl: string
  html: string
  sentCookie: boolean
}): 'ok' | 'auth' | 'probe_fail' {
  if (input.kind === 'user') return 'ok'
  if (input.kind === 'im_fetch') {
    if (input.finalUrl.includes('/passport/') || input.finalUrl.includes('/login')) return 'auth'
    if (!input.sentCookie || (input.httpStatus !== 401 && input.httpStatus !== 403)) return 'ok'
    return classifyUpstream({
      httpStatus: input.httpStatus,
      finalUrl: input.finalUrl,
      html: input.html,
    })
  }
  const httpStatus =
    !input.sentCookie && (input.httpStatus === 401 || input.httpStatus === 403) ? 200 : input.httpStatus
  return classifyUpstream({
    httpStatus,
    finalUrl: input.finalUrl,
    html: input.html,
  })
}

export function danmakuWebSocketUrl(
  pushServer: string | null | undefined,
  browserOrigin: string | null,
): string | null {
  const server = String(pushServer || '').trim()
  if (server) {
    const host = server.replace(/^wss?:\/\//i, '').replace(/\/+$/, '')
    if (host) return `wss://${host}/webcast/im/push/v2/`
  }
  if (browserOrigin) {
    return `${browserOrigin.replace(/^http/, 'ws')}/socket/webcast/im/push/v2/`
  }
  return null
}

function parseCookieHeader(cookieHeader: string): Map<string, string> {
  const jar = new Map<string, string>()
  if (!cookieHeader.trim()) {
    return jar
  }
  for (const part of cookieHeader.split(';')) {
    const trimmed = part.trim()
    if (!trimmed) {
      continue
    }
    const eq = trimmed.indexOf('=')
    if (eq === -1) {
      continue
    }
    jar.set(trimmed.slice(0, eq), trimmed.slice(eq + 1))
  }
  return jar
}

function mergeSetCookies(jar: Map<string, string>, setCookies: string[]): void {
  for (const raw of setCookies) {
    const pair = raw.split(';')[0]?.trim()
    if (!pair) {
      continue
    }
    const eq = pair.indexOf('=')
    if (eq === -1) {
      continue
    }
    jar.set(pair.slice(0, eq), pair.slice(eq + 1))
  }
}

function jarToCookieHeader(jar: Map<string, string>): string {
  return [...jar.entries()].map(([k, v]) => `${k}=${v}`).join('; ')
}

export function mergeCookieHeader(callerCookie: string, setCookieLines: string[]): string {
  const jar = parseCookieHeader(callerCookie)
  mergeSetCookies(jar, setCookieLines)
  return jarToCookieHeader(jar)
}

export type ProbeLivePageResult = {
  ok: boolean
  living: boolean
  roomStatus: number | 'unknown'
  error: string
}

export async function probeLivePage(
  roomNum: string,
  cookieHeader: string,
  fetchImpl: typeof fetch,
): Promise<ProbeLivePageResult> {
  const url = `https://live.douyin.com/${roomNum}`
  const jar = parseCookieHeader(cookieHeader)

  const doFetch = async (): Promise<{ response: Response; sentCookie: boolean }> => {
    const headers = new Headers()
    const cookie = jarToCookieHeader(jar)
    const sentCookie = cookie.length > 0
    if (sentCookie) {
      headers.set('cookie', cookie)
    }
    return { response: await fetchImpl(url, { headers }), sentCookie }
  }

  const classify = (response: Response, html: string, sentCookie: boolean) =>
    classifyDirectRequest({
      kind: 'live_page',
      httpStatus: response.status,
      finalUrl: response.url || url,
      html,
      sentCookie,
    })

  let fetched = await doFetch()
  let response = fetched.response
  let sentCookie = fetched.sentCookie
  let html = await response.text()

  if (classify(response, html, sentCookie) === 'auth') {
    return { ok: false, living: false, roomStatus: 'unknown', error: 'auth' }
  }

  let status = extractRoomStatus(html)
  if (status !== null) {
    return {
      ok: true,
      living: isLivingStatus(status),
      roomStatus: status,
      error: '',
    }
  }

  mergeSetCookies(jar, response.headers.getSetCookie())
  fetched = await doFetch()
  response = fetched.response
  sentCookie = fetched.sentCookie
  html = await response.text()

  if (classify(response, html, sentCookie) === 'auth') {
    return { ok: false, living: false, roomStatus: 'unknown', error: 'auth' }
  }

  status = extractRoomStatus(html)
  if (status !== null) {
    return {
      ok: true,
      living: isLivingStatus(status),
      roomStatus: status,
      error: '',
    }
  }

  return { ok: false, living: false, roomStatus: 'unknown', error: 'probe_fail' }
}
