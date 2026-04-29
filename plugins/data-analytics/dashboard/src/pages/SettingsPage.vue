<script setup lang="ts">
import { analyticsContext } from '../stores/context'
</script>

<template>
  <section class="grid">
    <article class="card">
      <h3>口径设置</h3>
      <p>默认总营收口径：礼物 + SC + 上舰。</p>
      <p>当前分层主轴：{{ analyticsContext.audienceAxis }}</p>
    </article>
    <article class="card">
      <h3>默认视图</h3>
      <p>默认分析视角：{{ analyticsContext.viewMode }}</p>
      <p>默认时间粒度：{{ analyticsContext.granularity }}</p>
    </article>
  </section>
</template>

<style scoped>
.grid { display:grid; grid-template-columns: 1fr 1fr; gap:12px; }
.card { background:#0b1020; border:1px solid #1e293b; border-radius:14px; padding:14px; }
@media (max-width: 960px) { .grid { grid-template-columns: 1fr; } }
</style>
