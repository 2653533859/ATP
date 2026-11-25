import { describe, expect, it } from 'vitest'
import { createI18n } from 'vue-i18n'

import enUS from './en-US'
import zhCN from './zh-CN'

function collectLeafKeys(obj: Record<string, unknown>, prefix = ''): string[] {
  const keys: string[] = []
  for (const [k, v] of Object.entries(obj)) {
    const next = prefix ? `${prefix}.${k}` : k
    if (v && typeof v === 'object' && !Array.isArray(v)) {
      keys.push(...collectLeafKeys(v as Record<string, unknown>, next))
    } else if (typeof v === 'string') {
      keys.push(next)
    }
  }
  return keys
}

describe('locale message compilation', () => {
  it('compiles every zh-CN and en-US message without vue-i18n SyntaxError', () => {
    const i18n = createI18n({
      legacy: false,
      locale: 'zh-CN',
      fallbackLocale: 'zh-CN',
      missingWarn: false,
      fallbackWarn: false,
      messages: { 'zh-CN': zhCN, 'en-US': enUS },
    })

    const failures: string[] = []
    for (const [locale, tree] of [
      ['zh-CN', zhCN],
      ['en-US', enUS],
    ] as const) {
      const keys = collectLeafKeys(tree as unknown as Record<string, unknown>)
      for (const key of keys) {
        try {
          const out = i18n.global.t(key, {}, { locale })
          if (typeof out !== 'string') {
            failures.push(`${locale}:${key} -> non-string`)
          }
        } catch (err) {
          failures.push(`${locale}:${key} -> ${err instanceof Error ? err.message : String(err)}`)
        }
      }
    }

    expect(failures).toEqual([])
  })
})
