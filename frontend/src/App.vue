<template>
  <a-config-provider :theme="themeConfig">
    <RouterView />
  </a-config-provider>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { theme as antdTheme } from 'ant-design-vue'
import { useThemeStore } from '@/stores/theme'

const themeStore = useThemeStore()

const themeConfig = computed(() => {
  const dark = themeStore.mode === 'dark'
  return {
    algorithm: dark ? antdTheme.darkAlgorithm : antdTheme.defaultAlgorithm,
    token: {
      colorPrimary: dark ? '#6366f1' : '#5850ec',
      borderRadius: 12,
      controlHeight: 34,
      fontSize: 13,
      fontFamily:
        "'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'PingFang SC', sans-serif",
      colorSuccess: '#10b981',
      colorWarning: '#f59e0b',
      colorError: '#f43f5e',
      colorInfo: '#06b6d4',
      wireframe: false,
    },
  }
})
</script>
