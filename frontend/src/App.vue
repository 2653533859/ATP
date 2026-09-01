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
      colorPrimary: dark ? '#897eff' : '#1677ff',
      borderRadius: 10,
      controlHeight: 36,
      fontSize: 14,
      fontFamily:
        "'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', 'PingFang SC', 'Hiragino Sans GB', 'Microsoft YaHei', sans-serif",
      colorSuccess: dark ? '#4ae191' : '#52c41a',
      colorWarning: dark ? '#ffd05e' : '#faad14',
      colorError: dark ? '#ff395c' : '#ff4d4f',
      colorInfo: dark ? '#40ebe3' : '#1677ff',
      wireframe: false,
    },
  }
})
</script>
