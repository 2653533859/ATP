import { createApp } from 'vue'
import { createPinia } from 'pinia'
// Ant Design 组件经 unplugin-vue-components 按需注册（见 vite.config.ts）；
// 这里只保留全局 reset 样式。message/Modal 等命令式 API 在使用处显式 import。
import 'ant-design-vue/dist/reset.css'
import './styles/theme.css'
import './styles/page-shell.css'
// 注意：不要在这里 import '@/utils/chartTheme'——它引用全套 echarts 模块，
// 同步引入会把 echarts chunk 拉进登录首屏。主题/组件注册在图表视图
// import useChartTheme 时（模块求值）自动完成。

import App from './App.vue'
import router from './router'
import { i18n } from './locales'

const app = createApp(App)

app.use(createPinia())
app.use(router)
app.use(i18n)

app.mount('#app')
