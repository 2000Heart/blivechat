<script setup lang="ts">
import { ref, watch } from 'vue'
import { getExploreEvents } from '../services/api'
import { analyticsContext } from '../stores/context'

const eventType = ref('')
const keyword = ref('')
const rows = ref<Array<Record<string, unknown>>>([])
const total = ref(0)
const loading = ref(false)

async function load() {
  loading.value = true
  const data = await getExploreEvents(analyticsContext, {
    event_type: eventType.value,
    keyword: keyword.value,
    limit: '100',
    offset: '0',
  })
  rows.value = data.items
  total.value = data.total
  loading.value = false
}

watch(() => ({ ...analyticsContext }), () => { void load() }, { deep: true })
watch([eventType, keyword], () => { void load() })
void load()
</script>

<template>
  <section class="card">
    <header class="toolbar">
      <select v-model="eventType">
        <option value="">全部事件</option>
        <option value="danmaku">弹幕</option>
        <option value="gift">礼物</option>
        <option value="super_chat">SC</option>
        <option value="member">上舰</option>
      </select>
      <input v-model="keyword" placeholder="作者/礼物关键词" />
    </header>
    <p v-if="loading">加载中...</p>
    <p>共 {{ total }} 条</p>
    <div class="table-wrap">
      <table class="table">
        <thead><tr><th>时间</th><th>类型</th><th>用户</th><th>金额</th><th>礼物</th><th>平台</th></tr></thead>
        <tbody>
          <tr v-for="(row, idx) in rows" :key="idx">
            <td>{{ row.timestamp }}</td>
            <td>{{ row.event_type }}</td>
            <td>{{ row.author_name }}</td>
            <td>{{ row.amount }}</td>
            <td>{{ row.gift_name || '-' }}</td>
            <td>{{ row.source }}</td>
          </tr>
        </tbody>
      </table>
    </div>
  </section>
</template>

<style scoped>
.card { background:#0b1020; border:1px solid #1e293b; border-radius:14px; padding:14px; }
.toolbar { display:flex; gap:10px; margin-bottom:8px; }
input,select { background:#020617; color:#e2e8f0; border:1px solid #334155; border-radius:8px; padding:8px; }
.table-wrap { max-height:520px; overflow:auto; }
.table { width:100%; border-collapse:collapse; }
.table th,.table td { border-bottom:1px solid #1e293b; text-align:left; padding:8px; font-size:13px; }
</style>
