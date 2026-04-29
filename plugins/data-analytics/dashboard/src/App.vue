<script setup lang="ts">
import { RouterLink, RouterView } from 'vue-router'
import GlobalContextBar from './components/GlobalContextBar.vue'
</script>

<template>
  <div class="page">
    <header class="hero">
      <div>
        <p class="eyebrow">Data Analytics Dashboard v2</p>
        <h1>直播数据多维看板系统</h1>
        <p class="desc">多页面业务看板：变现分析、运营复盘、主播总结、用户分析、明细探索、设置中心。</p>
      </div>
    </header>

    <GlobalContextBar />

    <nav class="tabs">
      <RouterLink class="tab" to="/monetization">变现分析</RouterLink>
      <RouterLink class="tab" to="/ops-review">运营复盘</RouterLink>
      <RouterLink class="tab" to="/anchor-summary">主播总结</RouterLink>
      <RouterLink class="tab" to="/users">用户分析</RouterLink>
      <RouterLink class="tab" to="/explore">明细探索</RouterLink>
      <RouterLink class="tab" to="/settings">设置中心</RouterLink>
    </nav>

    <RouterView />
  </div>
</template>

<style scoped>
.page { max-width: 1480px; margin:0 auto; padding:24px; }
.hero { margin-bottom:12px; }
.eyebrow { margin:0; color:#5eead4; letter-spacing:.12em; text-transform:uppercase; font-size:12px; font-weight:700; }
h1 { margin:6px 0 6px; font-size:32px; line-height:1.2; }
.desc { margin:0; color:#94a3b8; }
.tabs { display:flex; gap:8px; margin:14px 0; flex-wrap:wrap; }
.tab { border:1px solid #334155; border-radius:999px; padding:8px 14px; color:#cbd5e1; text-decoration:none; background:#0f172a; }
.tab.router-link-active { background:linear-gradient(120deg,#14b8a6,#0ea5e9); color:#042f2e; font-weight:700; border-color:transparent; }
</style>
