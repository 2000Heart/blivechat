<script setup lang="ts">
import * as echarts from 'echarts'
import { nextTick, onMounted, ref, watch } from 'vue'
import { getKpis, getRevenueTrend, getUserSegments } from '../services/api'
import { analyticsContext } from '../stores/context'

const loading = ref(false)
const error = ref('')
const kpis = ref({
  totalRevenue: 0,
  giftRevenue: 0,
  scRevenue: 0,
  memberRevenue: 0,
  payerCount: 0,
  engagerCount: 0,
  arppu: 0,
})
const trend = ref<Array<{ bucket: string; gift: number; super_chat: number; member: number; total: number }>>([])
const userSeg = ref<Array<{ segment: string; count: number }>>([])

const trendRef = ref<HTMLElement>()
const segmentRef = ref<HTMLElement>()
let trendChart: echarts.ECharts | null = null
let segmentChart: echarts.ECharts | null = null

async function load() {
  loading.value = true
  error.value = ''
  try {
    const [k, t, s] = await Promise.all([
      getKpis(analyticsContext),
      getRevenueTrend(analyticsContext),
      getUserSegments(analyticsContext),
    ])
    kpis.value = k
    trend.value = t
    userSeg.value = s
    await nextTick()
    renderCharts()
  } catch (e) {
    error.value = `加载失败: ${String(e)}`
  } finally {
    loading.value = false
  }
}

function renderCharts() {
  if (trendRef.value) {
    trendChart = trendChart || echarts.init(trendRef.value)
    trendChart.setOption({
      tooltip: { trigger: 'axis' },
      legend: { textStyle: { color: '#cbd5e1' } },
      xAxis: { type: 'category', data: trend.value.map((x) => x.bucket), axisLabel: { color: '#94a3b8' } },
      yAxis: { type: 'value', axisLabel: { color: '#94a3b8' } },
      series: [
        { name: '总营收', type: 'line', smooth: true, data: trend.value.map((x) => x.total) },
        { name: '礼物', type: 'bar', stack: 'r', data: trend.value.map((x) => x.gift) },
        { name: 'SC', type: 'bar', stack: 'r', data: trend.value.map((x) => x.super_chat) },
        { name: '上舰', type: 'bar', stack: 'r', data: trend.value.map((x) => x.member) },
      ],
    })
  }
  if (segmentRef.value) {
    segmentChart = segmentChart || echarts.init(segmentRef.value)
    segmentChart.setOption({
      tooltip: { trigger: 'item' },
      series: [
        {
          type: 'pie',
          radius: ['38%', '72%'],
          data: userSeg.value.map((x) => ({ name: x.segment, value: x.count })),
        },
      ],
    })
  }
}

watch(
  () => ({ ...analyticsContext }),
  () => { void load() },
  { deep: true },
)

onMounted(() => {
  void load()
  window.addEventListener('resize', () => {
    trendChart?.resize()
    segmentChart?.resize()
  })
})
</script>

<template>
  <section class="grid">
    <p v-if="error" class="error">{{ error }}</p>
    <p v-if="loading" class="loading">加载中...</p>
    <article class="card kpi"><h3>总营收</h3><p>{{ kpis.totalRevenue.toFixed(2) }}</p></article>
    <article class="card kpi"><h3>礼物营收</h3><p>{{ kpis.giftRevenue.toFixed(2) }}</p></article>
    <article class="card kpi"><h3>SC营收</h3><p>{{ kpis.scRevenue.toFixed(2) }}</p></article>
    <article class="card kpi"><h3>上舰营收</h3><p>{{ kpis.memberRevenue.toFixed(2) }}</p></article>
    <article class="card kpi"><h3>付费人数</h3><p>{{ kpis.payerCount }}</p></article>
    <article class="card kpi"><h3>ARPPU</h3><p>{{ kpis.arppu.toFixed(2) }}</p></article>
    <article class="card chart">
      <h3>营收趋势与构成</h3>
      <div ref="trendRef" class="chart-box" />
    </article>
    <article class="card chart">
      <h3>人群贡献分层</h3>
      <div ref="segmentRef" class="chart-box" />
    </article>
  </section>
</template>

<style scoped>
.grid { display:grid; grid-template-columns: repeat(6,minmax(0,1fr)); gap:12px; }
.card { background:#0b1020; border:1px solid #1e293b; border-radius:14px; padding:14px; }
.kpi { grid-column: span 2; }
.kpi p { font-size:28px; margin:4px 0 0; color:#ccfbf1; font-weight:800; }
.chart { grid-column: span 3; }
.chart-box { height:320px; }
.error { color:#fca5a5; grid-column:1 / -1; }
.loading { color:#7dd3fc; grid-column:1 / -1; }
@media (max-width: 1100px) { .kpi, .chart { grid-column: span 6; } }
</style>
