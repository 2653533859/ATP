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
      colorPrimary: dark ? '#3b82f6' : '#2563eb',
      borderRadius: 6,
      controlHeight: 32,
      fontSize: 13,
      fontFamily:
        "-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'PingFang SC', sans-serif",
      colorSuccess: dark ? '#10b981' : '#059669',
      colorWarning: dark ? '#f59e0b' : '#d97706',
      colorError: dark ? '#ef4444' : '#dc2626',
      colorInfo: dark ? '#38bdf8' : '#0284c7',
      wireframe: false,
    },
  }
})
</script>
