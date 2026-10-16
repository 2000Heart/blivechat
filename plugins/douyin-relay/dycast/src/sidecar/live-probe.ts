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
