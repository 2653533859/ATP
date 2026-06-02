import { defineStore } from 'pinia'
import { ref } from 'vue'

export type ThemeMode = 'light' | 'dark'

const STORAGE_KEY = 'atp-theme'

function resolveInitial(): ThemeMode {
  const saved = localStorage.getItem(STORAGE_KEY)
  if (saved === 'light' || saved === 'dark') return saved
  // 无历史选择时跟随系统
  if (window.matchMedia?.('(prefers-color-scheme: dark)').matches) return 'dark'
  return 'light'
}

function applyToDom(mode: ThemeMode) {
  document.documentElement.setAttribute('data-theme', mode)
}

export const useThemeStore = defineStore('theme', () => {
  const mode = ref<ThemeMode>(resolveInitial())
  applyToDom(mode.value)

  function setMode(next: ThemeMode) {
    mode.value = next
    localStorage.setItem(STORAGE_KEY, next)
    applyToDom(next)
  }

  function toggle() {
    setMode(mode.value === 'dark' ? 'light' : 'dark')
  }

  return { mode, setMode, toggle }
})
