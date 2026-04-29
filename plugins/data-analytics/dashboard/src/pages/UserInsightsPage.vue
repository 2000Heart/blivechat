<script setup lang="ts">
import { useRouter } from 'vue-router'
import { ref, watch } from 'vue'
import { analyticsContext } from '../stores/context'
import { getDanmakuRanking, getGiftRanking, type DanmakuRankingRow, type GiftRankingRow } from '../services/api'

const router = useRouter()
const tab = ref<'danmaku' | 'gift'>('danmaku')
const giftSort = ref<'count' | 'amount'>('count')
const dmRows = ref<DanmakuRankingRow[]>([])
const giftRows = ref<GiftRankingRow[]>([])
const loading = ref(false)

function openUser(row: { uid: string; authorName: string }) {
  const q: Record<string, string> = {}
  if (row.uid) q.uid = row.uid
  if (row.authorName) q.author_name = row.authorName
  if (!q.uid && !q.author_name) return
  void router.push({ path: '/users/detail', query: q })
}

async function load() {
  loading.value = true
  try {
    const [d, g] = await Promise.all([
      getDanmakuRanking(analyticsContext, 50),
      getGiftRanking(analyticsContext, giftSort.value, 50),
    ])
    dmRows.value = d
    giftRows.value = g
  } finally {
    loading.value = false
  }
}

watch(
  () => ({ ...analyticsContext, giftSort: giftSort.value }),
  () => {
    void load()
  },
  { deep: true },
)

void load()
</script>

<template>
  <section class="wrap">
    <div class="tabs">
      <button :class="{ on: tab === 'danmaku' }" @click="tab = 'danmaku'">弹幕数排行</button>
      <button :class="{ on: tab === 'gift' }" @click="tab = 'gift'">送礼排行</button>
      <span v-if="tab === 'gift'" class="sort">
        <label>排序</label>
        <select v-model="giftSort">
          <option value="count">次数</option>
          <option value="amount">金额</option>
        </select>
      </span>
    </div>
    <p v-if="loading" class="muted">加载中...</p>

    <table v-show="tab === 'danmaku'" class="table">
      <thead>
        <tr><th>#</th><th>用户</th><th>UID</th><th>弹幕数</th></tr>
      </thead>
      <tbody>
        <tr v-for="(row, i) in dmRows" :key="`${row.uid}-${row.authorName}-${i}`" class="click" @click="openUser(row)">
          <td>{{ i + 1 }}</td>
          <td>{{ row.authorName || '-' }}</td>
          <td>{{ row.uid || '-' }}</td>
          <td>{{ row.danmakuCount }}</td>
        </tr>
      </tbody>
    </table>

    <table v-show="tab === 'gift'" class="table">
      <thead>
        <tr><th>#</th><th>用户</th><th>UID</th><th>次数</th><th>金额</th></tr>
      </thead>
      <tbody>
        <tr v-for="(row, i) in giftRows" :key="`g-${row.uid}-${row.authorName}-${i}`" class="click" @click="openUser(row)">
          <td>{{ i + 1 }}</td>
          <td>{{ row.authorName || '-' }}</td>
          <td>{{ row.uid || '-' }}</td>
          <td>{{ row.giftCount }}</td>
          <td>{{ row.giftAmount.toFixed(2) }}</td>
        </tr>
      </tbody>
    </table>
    <p class="muted">点击行查看该用户在当前筛选时间内的弹幕与礼物明细。</p>
  </section>
</template>

<style scoped>
.wrap { display: flex; flex-direction: column; gap: 10px; }
.tabs { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }
.tabs button { border: 1px solid #334155; background: #0f172a; color: #cbd5e1; border-radius: 8px; padding: 8px 12px; cursor: pointer; }
.tabs button.on { background: linear-gradient(120deg, #14b8a6, #0ea5e9); color: #042f2e; font-weight: 700; border-color: transparent; }
.sort { display: flex; align-items: center; gap: 8px; color: #94a3b8; }
.sort select { background: #020617; color: #e2e8f0; border: 1px solid #334155; border-radius: 8px; padding: 6px 8px; }
.table { width: 100%; border-collapse: collapse; font-size: 14px; }
.table th, .table td { border-bottom: 1px solid #1e293b; text-align: left; padding: 10px 8px; }
.table th { color: #94a3b8; }
.click { cursor: pointer; }
.click:hover { background: rgba(30, 41, 59, 0.6); }
.muted { color: #94a3b8; font-size: 13px; }
</style>
