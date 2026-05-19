import { createI18n } from 'vue-i18n'

import zhCN from './zh-CN'
import enUS from './en-US'

export type SupportedLocale = 'zh-CN' | 'en-US'

const STORAGE_KEY = 'atp.lang'
const DEFAULT_LOCALE: SupportedLocale = 'zh-CN'

function detectInitialLocale(): SupportedLocale {
  if (typeof window === 'undefined') return DEFAULT_LOCALE
  // 1. URL ?lang=en|zh 优先
  const params = new URLSearchParams(window.location.search)
  const fromQuery = params.get('lang')
  if (fromQuery === 'en') return 'en-US'
  if (fromQuery === 'zh') return 'zh-CN'
  // 2. localStorage 记忆
  const stored = window.localStorage.getItem(STORAGE_KEY)
  if (stored === 'en-US' || stored === 'zh-CN') return stored
  // 3. 浏览器 navigator.language
  const nav = window.navigator?.language ?? ''
  if (nav.toLowerCase().startsWith('en')) return 'en-US'
  return DEFAULT_LOCALE
}

export const i18n = createI18n({
  legacy: false,
  globalInjection: true,
  locale: detectInitialLocale(),
  fallbackLocale: DEFAULT_LOCALE,
  messages: {
    'zh-CN': zhCN,
    'en-US': enUS,
  },
})

export function setLocale(locale: SupportedLocale) {
  i18n.global.locale.value = locale
  if (typeof window !== 'undefined') {
    window.localStorage.setItem(STORAGE_KEY, locale)
  }
}

export function getLocale(): SupportedLocale {
  return i18n.global.locale.value as SupportedLocale
}
