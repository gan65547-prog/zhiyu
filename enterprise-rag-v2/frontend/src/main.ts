import { createApp } from 'vue'
import { createPinia } from 'pinia'
import ElementPlus from 'element-plus'
import { ElNotification } from 'element-plus'
import 'element-plus/dist/index.css'
import * as ElementPlusIconsVue from '@element-plus/icons-vue'
import App from './App.vue'
import router from './router'
import './styles/main.scss'

const app = createApp(App)

for (const [key, component] of Object.entries(ElementPlusIconsVue)) {
  app.component(key, component)
}

app.use(createPinia())
app.use(router)
app.use(ElementPlus)

app.config.errorHandler = (error, instance, info) => {
  console.error('[GlobalErrorHandler]', { error, info, instance })
  ElNotification({
    title: '页面发生异常',
    message: '已捕获前端运行错误，请刷新页面后重试；如果持续出现，请联系管理员。',
    type: 'error',
    duration: 5000,
  })
}

window.addEventListener('unhandledrejection', (event) => {
  console.error('[UnhandledRejection]', event.reason)
  ElNotification({
    title: '请求处理失败',
    message: '检测到未处理的异步错误，请稍后重试。',
    type: 'error',
    duration: 5000,
  })
})

app.mount('#app')
