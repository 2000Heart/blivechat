export const MIN_COOKIE_LENGTH = 200

export type CookieRecord = { name: string; value: string; domain: string }

const SESSION_COOKIE_NAMES = new Set([
  'sessionid',
  'sessionid_ss',
  'sid_tt',
  'uid_tt',
  'uid_tt_ss',
])

export function isLoginUrl(url: string): boolean {
  try {
    const parsed = new URL(url)
    const hostPath = `${parsed.host}${parsed.pathname}`.toLowerCase()
    return (
      hostPath.includes('login') ||
      hostPath.includes('passport') ||
      hostPath.includes('sso')
    )
  } catch {
    return false
  }
}

export function serializeDouyinCookies(cookies: CookieRecord[]): string {
  return cookies
    .filter((c) => c.name && c.domain.includes('douyin.com'))
    .map((c) => `${c.name}=${c.value}`)
    .join('; ')
}

export function judgeDouyinLogin(input: {
  cookies: CookieRecord[]
  url: string
  mode: 'interactive' | 'silent'
}): { ok: boolean; reason: string } {
  if (input.mode === 'silent' && isLoginUrl(input.url)) {
    return { ok: false, reason: 'login_url' }
  }

  const hasSession = input.cookies.some(
    (c) => SESSION_COOKIE_NAMES.has(c.name) && c.domain.includes('douyin.com'),
  )
  if (!hasSession) {
    return { ok: false, reason: 'missing_session_cookie' }
  }

  const serialized = serializeDouyinCookies(input.cookies)
  if (serialized.length < MIN_COOKIE_LENGTH) {
    return { ok: false, reason: 'cookie_too_short' }
  }

  return { ok: true, reason: 'ok' }
}
