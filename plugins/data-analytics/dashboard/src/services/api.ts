import type { AnalyticsContext, KpiPayload } from '../models'

/** 与 blivechat Admin UI 打开方式一致：首屏常在 `/?token=`；Vue Router 切页后 query 会丢失，故持久化 token。 */
const TOKEN_STORAGE_KEY = 'data-analytics-admin-token'
let memoryToken = ''

function persistToken(token: string) {
  if (!token) return
  try {
    sessionStorage.setItem(TOKEN_STORAGE_KEY, token)
  } catch {
    memoryToken = token
  }
}

/** 启动时调用一次，便于无 URL token 但已有 session 的场景 */
export function initAuthToken() {
  const fromUrl = new URLSearchParams(window.location.search).get('token')
  if (fromUrl) persistToken(fromUrl)
}

function getToken() {
  const fromUrl = new URLSearchParams(window.location.search).get('token')
  if (fromUrl) {
    persistToken(fromUrl)
    return fromUrl
  }
  try {
    const stored = sessionStorage.getItem(TOKEN_STORAGE_KEY)
    if (stored) return stored
  } catch {
    /* private mode 等 */
  }
  return memoryToken
}

function toQuery(ctx: AnalyticsContext, extra: Record<string, string> = {}) {
  const q = new URLSearchParams()
  const token = getToken()
  if (token) q.set('token', token)
  if (ctx.roomId) q.set('room_id', ctx.roomId)
  if (ctx.fromTs) q.set('from_ts', ctx.fromTs)
  if (ctx.toTs) q.set('to_ts', ctx.toTs)
  q.set('source', ctx.source)
  q.set('view_mode', ctx.viewMode)
  q.set('granularity', ctx.granularity)
  for (const [k, v] of Object.entries(extra)) {
    if (v !== '') q.set(k, v)
  }
  return q.toString()
}

async function request<T>(path: string, ctx: AnalyticsContext, extra: Record<string, string> = {}) {
  const token = getToken()
  const res = await fetch(`${path}?${toQuery(ctx, extra)}`, {
    headers: token ? { Authorization: `Bearer ${token}` } : undefined,
  })
  if (!res.ok) throw new Error(`HTTP ${res.status}`)
  const body = await res.json()
  return body.data as T
}

export function getRooms() {
  return fetch(`/api/v1/meta/rooms?token=${getToken()}`)
    .then((r) => r.json())
    .then((b) => b.data as Array<{ room_id: number }>)
}

export function getKpis(ctx: AnalyticsContext) {
  return request<KpiPayload>('/api/v2/kpis', ctx)
}

export function getRevenueTrend(ctx: AnalyticsContext) {
  return request<Array<{ bucket: string; gift: number; super_chat: number; member: number; total: number }>>('/api/v2/trend/revenue', ctx)
}

export function getUserSegments(ctx: AnalyticsContext) {
  return request<Array<{ segment: string; count: number }>>('/api/v2/segments/users', ctx)
}

export function getExploreEvents(ctx: AnalyticsContext, params: Record<string, string>) {
  return request<{ total: number; items: Array<Record<string, unknown>>; limit: number; offset: number }>('/api/v2/explore/events', ctx, params)
}

export type ActiveHourRow = {
  hour: number
  danmakuCount: number
  giftCount: number
  eventCount: number
  uniqueUserCount: number
}

export function getActiveHourOfDay(ctx: AnalyticsContext) {
  return request<ActiveHourRow[]>('/api/v2/series/active-hour-of-day', ctx)
}

export type DanmakuRankingRow = { uid: string; authorName: string; danmakuCount: number }
export type GiftRankingRow = { uid: string; authorName: string; giftCount: number; giftAmount: number }

export function getDanmakuRanking(ctx: AnalyticsContext, limit = 50) {
  return request<DanmakuRankingRow[]>('/api/v2/rankings/danmaku-authors', ctx, { limit: String(limit) })
}

export function getGiftRanking(ctx: AnalyticsContext, sort: 'count' | 'amount', limit = 50) {
  return request<GiftRankingRow[]>('/api/v2/rankings/gift-authors', ctx, { limit: String(limit), sort })
}

export function getUserDanmaku(
  ctx: AnalyticsContext,
  params: { uid?: string; authorName?: string; limit?: number; offset?: number },
) {
  const extra: Record<string, string> = {
    limit: String(params.limit ?? 50),
    offset: String(params.offset ?? 0),
  }
  if (params.uid) extra.uid = params.uid
  if (params.authorName) extra.author_name = params.authorName
  return request<{ total: number; items: Array<Record<string, unknown>>; limit: number; offset: number }>(
    '/api/v2/users/danmaku',
    ctx,
    extra,
  )
}

export function getUserGifts(
  ctx: AnalyticsContext,
  params: { uid?: string; authorName?: string; limit?: number; offset?: number },
) {
  const extra: Record<string, string> = {
    limit: String(params.limit ?? 50),
    offset: String(params.offset ?? 0),
  }
  if (params.uid) extra.uid = params.uid
  if (params.authorName) extra.author_name = params.authorName
  return request<{ total: number; items: Array<Record<string, unknown>>; limit: number; offset: number }>(
    '/api/v2/users/gifts',
    ctx,
    extra,
  )
}
