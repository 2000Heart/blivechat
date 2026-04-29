import { reactive } from 'vue'
import type { AnalyticsContext, Segment } from '../models'

function nowTs() {
  return Math.floor(Date.now() / 1000)
}

const defaultContext: AnalyticsContext = {
  roomId: '',
  source: 'all',
  fromTs: String(nowTs() - 7 * 24 * 3600),
  toTs: String(nowTs()),
  viewMode: 'all',
  granularity: 'day',
  audienceAxis: 'contribution',
}

export const analyticsContext = reactive<AnalyticsContext>({ ...defaultContext })

export const compareSegments = reactive<Segment[]>([])

export function resetContext() {
  Object.assign(analyticsContext, defaultContext)
}

export function saveSegment(name: string) {
  compareSegments.push({
    id: `${Date.now()}-${Math.random().toString(16).slice(2, 8)}`,
    name,
    context: { ...analyticsContext },
  })
}

export function removeSegment(id: string) {
  const idx = compareSegments.findIndex((s) => s.id === id)
  if (idx >= 0) compareSegments.splice(idx, 1)
}
