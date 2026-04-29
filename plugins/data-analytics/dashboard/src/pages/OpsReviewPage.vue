<script setup lang="ts">
import * as echarts from 'echarts'
import { computed, nextTick, onMounted, ref, watch } from 'vue'
import { analyticsContext } from '../stores/context'
import { getActiveHourOfDay, getKpis, getRevenueTrend } from '../services/api'

const loading = ref(false)
const summary = ref({ totalRevenue: 0, engagerCount: 0, payerCount: 0 })
const trend = ref<Array<{ bucket: string; total: number }>>([])
const activeHours = ref<Array<{ hour: number; danmakuCount: number; giftCount: number; eventCount: number; uniqueUserCount: number }>>([])

const peakHourLabel = computed(() => {
  if (!activeHours.value.length) return '-'
  const peak = [...activeHours.value].sort((a, b) => b.eventCount - a.eventCount)[0]
  return `${peak.hour}:00（事件数 ${peak.eventCount}）`
})

const chartRef = ref<HTMLElement>()
let chart: echarts.ECharts | null = null

function renderChart() {
  if (!chartRef.value) return
  chart = chart || echarts.init(chartRef.value)
  const labels = activeHours.value.map((r) => `${r.hour}:00`)
  chart.setOption({
    tooltip: { trigger: 'axis' },
    legend: { data: ['弹幕', '礼物', '去重用户'], textStyle: { color: '#cbd5e1' } },
    grid: { left: 48, right: 48, bottom: 32, top: 48 },
    xAxis: { type: 'category', data: labels, axisLabel: { color: '#94a3b8' } },
    yAxis: [
      { type: 'value', name: '事件数', axisLabel: { color: '#94a3b8' } },
      { type: 'value', name: '用户数', axisLabel: { color: '#94a3b8' } },
    ],
    series: [
      {
        name: '弹幕',
        type: 'bar',
        stack: 'ev',
        data: activeHours.value.map((r) => r.danmakuCount),
        itemStyle: { color: '#2dd4bf' },
      },
      {
        name: '礼物',
        type: 'bar',
        stack: 'ev',
        data: activeHours.value.map((r) => r.giftCount),
        itemStyle: { color: '#fb7185' },
      },
      {
        name: '去重用户',
        type: 'line',
        yAxisIndex: 1,
        smooth: true,
        data: activeHours.value.map((r) => r.uniqueUserCount),
        lineStyle: { width: 3, color: '#38bdf8' },
      },
    ],
  })
}

async function load() {
  loading.value = true
  try {
    const [k, t, h] = await Promise.all([
      getKpis(analyticsContext),
      getRevenueTrend(analyticsContext),
      getActiveHourOfDay(analyticsContext),
    ])
    summary.value = k
    trend.value = t.map((row) => ({ bucket: row.bucket, total: row.total }))
    activeHours.value = h
    await nextTick()
    renderChart()
  } finally {
    loading.value = false
  }
}

watch(
  () => ({ ...analyticsContext }),
  () => {
    void load()
  },
  { deep: true },
)

onMounted(() => {
  void load()
  window.addEventListener('resize', () => chart?.resize())
})
</script>

<template>
  <section class="stack">
    <article class="card row">
      <div>
        <h3>运营复盘摘要</h3>
        <p>总营收：{{ summary.totalRevenue.toFixed(2) }}</p>
        <p>互动人数（弹幕 UID 去重）：{{ summary.engagerCount }}</p>
        <p>付费人数：{{ summary.payerCount }}</p>
        <p>活跃峰值小时（按事件数）：{{ peakHourLabel }}</p>
        <p v-if="loading">正在更新...</p>
      </div>
      <div class="hint">
        <p><strong>活跃时段口径</strong>：统计弹幕与礼物事件，按服务器本地时区将多日内同一钟点叠加。</p>
        <p>柱状堆叠为事件条数；折线为该小时去重用户数（优先 UID，否则昵称）。</p>
      </div>
    </article>

    <article class="card chart-card">
      <h3>用户活跃时段（0–23 点）</h3>
      <div ref="chartRef" class="chart-box" />
    </article>

    <article class="card">
      <h3>复盘建议</h3>
      <ul>
        <li>优先在峰值小时安排强互动与付费引导。</li>
        <li>在「用户分析」中查看弹幕与送礼排行并下钻明细。</li>
        <li>结合变现页营收趋势对比活动前后变化。</li>
      </ul>
    </article>
  </section>
</template>

<style scoped>
.stack { display: flex; flex-direction: column; gap: 12px; }
.card { background: #0b1020; border: 1px solid #1e293b; border-radius: 14px; padding: 14px; }
.row { display: grid; grid-template-columns: 1fr 1.2fr; gap: 12px; align-items: start; }
.hint { font-size: 13px; color: #94a3b8; line-height: 1.5; }
.chart-card h3 { margin: 0 0 8px; }
.chart-box { height: 360px; }
@media (max-width: 960px) {
  .row { grid-template-columns: 1fr; }
}
</style>
