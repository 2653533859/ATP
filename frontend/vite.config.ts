import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import Components from 'unplugin-vue-components/vite'
import { AntDesignVueResolver } from 'unplugin-vue-components/resolvers'
import { dirname, resolve } from 'path'
import { fileURLToPath } from 'url'

const __dirname = dirname(fileURLToPath(import.meta.url))

export default defineConfig({
  plugins: [
    vue(),
    // Ant Design 按需解析：模板中的 a-* 标签按使用注册，取代 main.ts 全局 app.use(Antd)。
    // importStyle:false —— antd v4 用 cssinjs，无需按组件引样式；reset.css 仍在 main.ts 全局引入。
    // dts 生成 src/components.d.ts（已提交），让 vue-tsc 对 a-* 组件做真实 props 类型检查。
    Components({
      resolvers: [AntDesignVueResolver({ importStyle: false })],
      dts: 'src/components.d.ts',
    }),
  ],
  resolve: {
    alias: {
      '@': resolve(__dirname, 'src'),
    },
  },
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
      },
      '/ws': {
        target: 'ws://127.0.0.1:8000',
        ws: true,
      },
    },
  },
  build: {
    rollupOptions: {
      output: {
        manualChunks(id) {
          if (!id.includes('node_modules')) return undefined
          if (id.includes('vue-router') || id.includes('/pinia/')) return 'vue-vendor'
          if (/[\\/]node_modules[\\/]vue[\\/]/.test(id)) return 'vue-vendor'
          if (id.includes('@ant-design/icons')) return 'ant-design-icons'
          // Q13-04: 不给 ant-design-vue 建单体 chunk——按需注册（unplugin-vue-components）
          // 后，让组件随各路由 chunk 分裂。/login 首屏传输因此从 510 降到 336 kB（-34%），
          // 代价是 antd 共享运行时在少数路由 chunk 里重复，dist JS 总量 +~35 kB。
          // 证据与决策见 docs/frontend-bundle-decision.md。
          if (id.includes('vue-i18n') || id.includes('@intlify')) return 'i18n'
          if (id.includes('vue-echarts')) return 'echarts'
          if (id.includes('echarts')) return 'echarts'
          if (id.includes('vuedraggable') || id.includes('sortablejs')) return 'vuedraggable'
          if (id.includes('monaco-editor') || id.includes('@monaco-editor')) return 'monaco'
          if (id.includes('dayjs') || id.includes('axios')) return 'common-vendor'
          return undefined
        },
      },
    },
    // Q13-04: 单体 antd chunk 移除后最大 chunk 是 echarts(~563kB)；阈值收到 600 以更早发现回归
    chunkSizeWarningLimit: 600,
  },
})
