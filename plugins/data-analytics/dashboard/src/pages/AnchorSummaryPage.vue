<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { analyticsContext } from '../stores/context'
import { getKpis, getRevenueTrend } from '../services/api'

const kpis = ref({ totalRevenue: 0, giftRevenue: 0, scRevenue: 0, memberRevenue: 0, payerCount: 0, engagerCount: 0, arppu: 0 })
const trend = ref<Array<{ bucket: string; total: number }>>([])

const suggestion = computed(() => {
  if (!trend.value.length) return '数据不足，建议延长统计周期。'
  const peak = [...trend.value].sort((a, b) => b.total - a.total)[0]
  return `建议重点复用 ${peak.bucket} 附近的互动节奏，并围绕高付费人群增强引导。`
})

async function load() {
  const [k, t] = await Promise.all([getKpis(analyticsContext), getRevenueTrend(analyticsContext)])
  kpis.value = k
  trend.value = t
}

watch(() => ({ ...analyticsContext }), () => { void load() }, { deep: true })
void load()
</script>

<template>
  <section class="grid">
    <article class="card">
      <h3>主播总结</h3>
      <p>总营收：{{ kpis.totalRevenue.toFixed(2) }}</p>
      <p>ARPPU：{{ kpis.arppu.toFixed(2) }}</p>
      <p>付费人数：{{ kpis.payerCount }}</p>
      <p>互动人数：{{ kpis.engagerCount }}</p>
    </article>
    <article class="card">
      <h3>行动建议</h3>
      <p>{{ suggestion }}</p>
    </article>
  </section>
</template>

<style scoped>
.grid { display:grid; grid-template-columns: 1fr 1fr; gap:12px; }
.card { background:#0b1020; border:1px solid #1e293b; border-radius:14px; padding:14px; }
@media (max-width: 960px) { .grid { grid-template-columns: 1fr; } }
</style>
