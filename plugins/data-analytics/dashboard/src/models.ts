export type SourceType = 'all' | 'bilibili' | 'douyin'
export type ViewMode = 'all' | 'session' | 'time'
export type Granularity = 'day' | 'week' | 'month'
export type AudienceAxis = 'contribution' | 'activity' | 'identity'

export type AnalyticsContext = {
  roomId: string
  source: SourceType
  fromTs: string
  toTs: string
  viewMode: ViewMode
  granularity: Granularity
  audienceAxis: AudienceAxis
}

export type Segment = {
  id: string
  name: string
  context: AnalyticsContext
}

export type KpiPayload = {
  totalRevenue: number
  giftRevenue: number
  scRevenue: number
  memberRevenue: number
  payerCount: number
  engagerCount: number
  arppu: number
}
