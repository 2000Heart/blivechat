<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useRoute, onBeforeRouteUpdate } from 'vue-router'
import { analyticsContext } from '../stores/context'
import { getUserDanmaku, getUserGifts } from '../services/api'

const route = useRoute()
const tab = ref<'danmaku' | 'gift'>('danmaku')
const pageSize = 30
const offsetDm = ref(0)
const offsetGift = ref(0)
const dmTotal = ref(0)
const giftTotal = ref(0)
const dmItems = ref<Array<Record<string, unknown>>>([])
const giftItems = ref<Array<Record<string, unknown>>>([])
const loading = ref(false)

const uid = computed(() => (route.query.uid as string) || '')
const authorName = computed(() => (route.query.author_name as string) || '')

/** 仅 URL 带 uid、未带昵称时，从首条记录补全展示用昵称 */
const resolvedDisplayName = ref('')

/** 主标题仅展示用户名；有 UID 时放在第二行副标题 */
const displayName = computed(() => (authorName.value || resolvedDisplayName.value).trim())

const mainTitle = computed(() => {
  if (displayName.value) return `用户 ${displayName.value}`
  if (uid.value.trim()) return '用户'
  return '用户明细'
})

const uidSubtitle = computed(() => {
  const id = uid.value.trim()
  if (!id) return ''
  return `UID：${id}`
})

function pickDisplayNameFromRows(items: Array<Record<string, unknown>>) {
  if (authorName.value) {
    resolvedDisplayName.value = ''
    return
  }
  if (!uid.value || !items.length) {
    resolvedDisplayName.value = ''
    return
  }
  const n = items[0].author_name
  resolvedDisplayName.value = typeof n === 'string' && n.trim() ? n.trim() : ''
}

/** 未切换 Tab 前也要显示礼物总数：并行拉取两条接口的 total（limit=1 即可） */
async function refreshBothTotals() {
  if (!uid.value && !authorName.value) return
  const params = {
    uid: uid.value || undefined,
    authorName: authorName.value || undefined,
    limit: 1,
    offset: 0,
  }
  const [d, g] = await Promise.all([
    getUserDanmaku(analyticsContext, params),
    getUserGifts(analyticsContext, params),
  ])
  dmTotal.value = d.total
  giftTotal.value = g.total
  pickDisplayNameFromRows(d.items.length ? d.items : g.items)
}

async function loadDanmaku() {
  if (!uid.value && !authorName.value) return
  loading.value = true
  try {
    const data = await getUserDanmaku(analyticsContext, {
      uid: uid.value || undefined,
      authorName: authorName.value || undefined,
      limit: pageSize,
      offset: offsetDm.value,
    })
    dmTotal.value = data.total
    dmItems.value = data.items
    pickDisplayNameFromRows(data.items)
  } finally {
    loading.value = false
  }
}

async function loadGifts() {
  if (!uid.value && !authorName.value) return
  loading.value = true
  try {
    const data = await getUserGifts(analyticsContext, {
      uid: uid.value || undefined,
      authorName: authorName.value || undefined,
      limit: pageSize,
      offset: offsetGift.value,
    })
    giftTotal.value = data.total
    giftItems.value = data.items
    pickDisplayNameFromRows(data.items)
  } finally {
    loading.value = false
  }
}

async function loadActive() {
  if (tab.value === 'danmaku') await loadDanmaku()
  else await loadGifts()
}

watch(
  () => ({ ...analyticsContext, uid: uid.value, authorName: authorName.value }),
  () => {
    resolvedDisplayName.value = ''
    offsetDm.value = 0
    offsetGift.value = 0
    void (async () => {
      await refreshBothTotals()
      await loadActive()
    })()
  },
  { deep: true },
)

watch(tab, () => {
  void loadActive()
})

watch(offsetDm, () => {
  if (tab.value === 'danmaku') void loadDanmaku()
})

watch(offsetGift, () => {
  if (tab.value === 'gift') void loadGifts()
})

void (async () => {
  await refreshBothTotals()
  await loadActive()
})()

onBeforeRouteUpdate(() => {
  resolvedDisplayName.value = ''
  offsetDm.value = 0
  offsetGift.value = 0
  void (async () => {
    await refreshBothTotals()
    await loadActive()
  })()
})

function fmtTs(ts: unknown) {
  const n = Number(ts)
  if (!Number.isFinite(n)) return String(ts ?? '')
  return new Date(n * 1000).toLocaleString()
}
</script>

<template>
  <section class="wrap">
    <header class="head">
      <h2>{{ mainTitle }}</h2>
      <p v-if="uidSubtitle" class="uid-sub">{{ uidSubtitle }}</p>
      <p v-if="!uid && !authorName" class="err">缺少 uid 或 author_name 参数。</p>
      <p v-else class="muted">筛选与顶部全局上下文一致；时区与数据写入一致。</p>
    </header>

    <div class="tabs">
      <button :class="{ on: tab === 'danmaku' }" @click="tab = 'danmaku'">弹幕（{{ dmTotal }}）</button>
      <button :class="{ on: tab === 'gift' }" @click="tab = 'gift'">礼物（{{ giftTotal }}）</button>
    </div>
    <p v-if="loading" class="muted">加载中...</p>

    <div v-show="tab === 'danmaku'" class="panel">
      <table class="table">
        <thead><tr><th>时间</th><th>房间</th><th>平台</th><th>内容</th></tr></thead>
        <tbody>
          <tr v-for="(row, i) in dmItems" :key="`dm-${i}`">
            <td>{{ fmtTs(row.timestamp) }}</td>
            <td>{{ row.room_id }}</td>
            <td>{{ row.source }}</td>
            <td class="content">{{ row.content }}</td>
          </tr>
        </tbody>
      </table>
      <div class="pager">
        <button :disabled="offsetDm <= 0" @click="offsetDm = Math.max(0, offsetDm - pageSize)">上一页</button>
        <button :disabled="offsetDm + pageSize >= dmTotal" @click="offsetDm = offsetDm + pageSize">下一页</button>
      </div>
    </div>

    <div v-show="tab === 'gift'" class="panel">
      <table class="table">
        <thead><tr><th>时间</th><th>礼物</th><th>次数</th><th>金额</th><th>平台</th></tr></thead>
        <tbody>
          <tr v-for="(row, i) in giftItems" :key="`g-${i}`">
            <td>{{ fmtTs(row.timestamp) }}</td>
            <td>{{ row.gift_name }}</td>
            <td>{{ row.quantity }}</td>
            <td>{{ Number(row.amount).toFixed(2) }}</td>
            <td>{{ row.source }}</td>
          </tr>
        </tbody>
      </table>
      <div class="pager">
        <button :disabled="offsetGift <= 0" @click="offsetGift = Math.max(0, offsetGift - pageSize)">上一页</button>
        <button :disabled="offsetGift + pageSize >= giftTotal" @click="offsetGift = offsetGift + pageSize">下一页</button>
      </div>
    </div>
  </section>
</template>

<style scoped>
.wrap { display: flex; flex-direction: column; gap: 12px; }
.head h2 { margin: 0 0 4px; }
.uid-sub { margin: 0 0 8px; font-size: 14px; color: #94a3b8; letter-spacing: 0.02em; }
.muted { color: #94a3b8; font-size: 13px; }
.err { color: #fca5a5; }
.tabs { display: flex; gap: 8px; }
.tabs button { border: 1px solid #334155; background: #0f172a; color: #cbd5e1; border-radius: 8px; padding: 8px 12px; cursor: pointer; }
.tabs button.on { background: linear-gradient(120deg, #14b8a6, #0ea5e9); color: #042f2e; font-weight: 700; border-color: transparent; }
.panel { background: #0b1020; border: 1px solid #1e293b; border-radius: 12px; padding: 10px; }
.table { width: 100%; border-collapse: collapse; font-size: 13px; }
.table th, .table td { border-bottom: 1px solid #1e293b; text-align: left; padding: 8px; vertical-align: top; }
.content { max-width: 520px; word-break: break-word; }
.pager { display: flex; gap: 8px; margin-top: 10px; }
.pager button { border: 1px solid #334155; background: #1e293b; color: #e2e8f0; border-radius: 8px; padding: 6px 12px; cursor: pointer; }
.pager button:disabled { opacity: 0.4; cursor: not-allowed; }
</style>
