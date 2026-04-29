import { createRouter, createWebHistory } from 'vue-router'
import MonetizationPage from './pages/MonetizationPage.vue'
import OpsReviewPage from './pages/OpsReviewPage.vue'
import AnchorSummaryPage from './pages/AnchorSummaryPage.vue'
import ExplorePage from './pages/ExplorePage.vue'
import SettingsPage from './pages/SettingsPage.vue'
import UserInsightsPage from './pages/UserInsightsPage.vue'
import UserDetailPage from './pages/UserDetailPage.vue'

export const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', redirect: '/monetization' },
    { path: '/monetization', component: MonetizationPage, meta: { title: '变现分析' } },
    { path: '/ops-review', component: OpsReviewPage, meta: { title: '运营复盘' } },
    { path: '/anchor-summary', component: AnchorSummaryPage, meta: { title: '主播总结' } },
    { path: '/explore', component: ExplorePage, meta: { title: '明细探索' } },
    { path: '/users', component: UserInsightsPage, meta: { title: '用户分析' } },
    { path: '/users/detail', component: UserDetailPage, meta: { title: '用户明细' } },
    { path: '/settings', component: SettingsPage, meta: { title: '设置中心' } },
  ],
})
