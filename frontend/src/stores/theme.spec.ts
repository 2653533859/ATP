import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { useThemeStore } from './theme'

function mockSystemDark(matches: boolean) {
  Object.defineProperty(window, 'matchMedia', {
    configurable: true,
    value: vi.fn().mockReturnValue({
      matches,
      media: '(prefers-color-scheme: dark)',
      onchange: null,
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
      addListener: vi.fn(),
      removeListener: vi.fn(),
      dispatchEvent: vi.fn(),
    }),
  })
}

describe('theme store', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    document.documentElement.removeAttribute('data-theme')
  })

  it('initializes from localStorage and applies the DOM theme attribute', () => {
    localStorage.setItem('atp-theme', 'dark')

    const store = useThemeStore()

    expect(store.mode).toBe('dark')
    expect(document.documentElement.getAttribute('data-theme')).toBe('dark')
  })

  it('falls back to the reference light theme when no saved theme exists', () => {
    mockSystemDark(true)

    const store = useThemeStore()

    expect(store.mode).toBe('light')
    expect(document.documentElement.getAttribute('data-theme')).toBe('light')
  })

  it('persists explicit theme changes and toggles between modes', () => {
    const store = useThemeStore()

    store.setMode('dark')
    expect(store.mode).toBe('dark')
    expect(localStorage.getItem('atp-theme')).toBe('dark')
    expect(document.documentElement.getAttribute('data-theme')).toBe('dark')

    store.toggle()
    expect(store.mode).toBe('light')
    expect(localStorage.getItem('atp-theme')).toBe('light')
    expect(document.documentElement.getAttribute('data-theme')).toBe('light')
  })
})
