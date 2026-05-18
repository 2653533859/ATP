import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import { resolve } from 'path'

export default defineConfig({
  plugins: [vue()],
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
