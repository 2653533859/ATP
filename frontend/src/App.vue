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
      colorPrimary: dark ? '#818cf8' : '#4f46e5',
      borderRadius: 10,
      controlHeight: 36,
      fontSize: 14,
      fontFamily:
        "'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', 'PingFang SC', 'Hiragino Sans GB', 'Microsoft YaHei', sans-serif",
      colorSuccess: dark ? '#22c55e' : '#16a34a',
      colorWarning: dark ? '#f59e0b' : '#d97706',
      colorError: dark ? '#f87171' : '#dc2626',
      colorInfo: dark ? '#22d3ee' : '#0891b2',
      wireframe: false,
    },
  }
})
</script>
