<script setup lang="ts">
import { computed } from 'vue'
import { analyticsContext, compareSegments, removeSegment, resetContext, saveSegment } from '../stores/context'

const fromLocal = computed({
  get: () => toLocalInput(analyticsContext.fromTs),
  set: (v: string) => { analyticsContext.fromTs = toTs(v) },
})

const toLocal = computed({
  get: () => toLocalInput(analyticsContext.toTs),
  set: (v: string) => { analyticsContext.toTs = toTs(v) },
})

function toLocalInput(ts: string) {
  const n = Number(ts)
  if (!Number.isFinite(n) || n <= 0) return ''
  const d = new Date(n * 1000)
  const y = d.getFullYear()
  const m = String(d.getMonth() + 1).padStart(2, '0')
  const day = String(d.getDate()).padStart(2, '0')
  const hh = String(d.getHours()).padStart(2, '0')
  const mm = String(d.getMinutes()).padStart(2, '0')
  return `${y}-${m}-${day}T${hh}:${mm}`
}

function toTs(v: string) {
  if (!v) return ''
  return String(Math.floor(new Date(v).getTime() / 1000))
}

function addSegment() {
  const index = compareSegments.length + 1
  saveSegment(`Segment ${index}`)
}
</script>

<template>
  <section class="ctx-bar">
    <label>房间<input v-model="analyticsContext.roomId" placeholder="全部" /></label>
    <label>平台
      <select v-model="analyticsContext.source">
        <option value="all">全部</option>
        <option value="bilibili">B站</option>
        <option value="douyin">抖音</option>
      </select>
    </label>
    <label>视角
      <select v-model="analyticsContext.viewMode">
        <option value="all">全局</option>
        <option value="session">场次</option>
        <option value="time">时间</option>
      </select>
    </label>
    <label>粒度
      <select v-model="analyticsContext.granularity">
        <option value="day">日</option>
        <option value="week">周</option>
        <option value="month">月</option>
      </select>
    </label>
    <label>开始<input type="datetime-local" v-model="fromLocal" /></label>
    <label>结束<input type="datetime-local" v-model="toLocal" /></label>
    <label>人群主轴
      <select v-model="analyticsContext.audienceAxis">
        <option value="contribution">贡献</option>
        <option value="activity">活跃</option>
        <option value="identity">身份</option>
      </select>
    </label>
    <div class="ctx-actions">
      <button class="btn ghost" @click="resetContext">重置</button>
      <button class="btn" @click="addSegment">加入对比组</button>
    </div>
    <div class="segment-list" v-if="compareSegments.length">
      <span v-for="seg in compareSegments" :key="seg.id" class="segment-chip">
        {{ seg.name }}
        <button @click="removeSegment(seg.id)">x</button>
      </span>
    </div>
  </section>
</template>

<style scoped>
.ctx-bar { display:grid; grid-template-columns: repeat(4,minmax(0,1fr)); gap:10px; padding:12px; border:1px solid #334155; border-radius:14px; background:#0f172a; margin-bottom:14px; }
label { display:flex; flex-direction:column; font-size:12px; color:#cbd5e1; gap:6px; }
input,select { background:#020617; color:#e2e8f0; border:1px solid #334155; border-radius:8px; padding:8px; }
.ctx-actions { display:flex; gap:8px; align-items:flex-end; }
.btn { border:0; border-radius:8px; padding:8px 10px; background:linear-gradient(120deg,#14b8a6,#0ea5e9); color:#042f2e; font-weight:700; cursor:pointer; }
.btn.ghost { background:#1e293b; color:#dbeafe; }
.segment-list { grid-column:1 / -1; display:flex; gap:8px; flex-wrap:wrap; }
.segment-chip { display:inline-flex; align-items:center; gap:6px; padding:4px 8px; border-radius:999px; background:#1e293b; color:#cbd5e1; }
.segment-chip button { border:0; background:transparent; color:#94a3b8; cursor:pointer; }
@media (max-width: 1024px) { .ctx-bar { grid-template-columns:1fr 1fr; } }
</style>
