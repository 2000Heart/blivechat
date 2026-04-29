import { createApp } from 'vue'
import App from './App.vue'
import './style.css'
import { router } from './router'
import { initAuthToken } from './services/api'

initAuthToken()
createApp(App).use(router).mount('#app')
