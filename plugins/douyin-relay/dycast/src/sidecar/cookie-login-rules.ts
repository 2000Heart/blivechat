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

function domainRank(domain: string): number {
  return domain
    .trim()
    .toLowerCase()
    .replace(/^\./, '')
    .split('.')
    .filter(Boolean).length
}

export function serializeDouyinCookies(cookies: CookieRecord[]): string {
  const chosen = new Map<string, { value: string; rank: number; index: number }>()
  cookies.forEach((cookie, index) => {
    if (!cookie.name || !cookie.domain.includes('douyin.com')) return
    const rank = domainRank(cookie.domain)
    const prev = chosen.get(cookie.name)
    if (!prev || rank > prev.rank || (rank === prev.rank && index >= prev.index)) {
      chosen.set(cookie.name, { value: cookie.value, rank, index })
    }
  })
  return [...chosen.entries()].map(([name, item]) => `${name}=${item.value}`).join('; ')
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
