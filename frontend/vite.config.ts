import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import Components from 'unplugin-vue-components/vite'
import { AntDesignVueResolver } from 'unplugin-vue-components/resolvers'
import { resolve } from 'path'

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
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
      '/ws': {
        target: 'ws://localhost:8000',
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
          if (id.includes('ant-design-vue')) return 'ant-design'
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
    chunkSizeWarningLimit: 1500,
  },
})
