import { beforeEach, describe, expect, it } from 'vitest'

import enUS from '@/locales/en-US'
import zhCN from '@/locales/zh-CN'
import {
  QUICK_SEARCH_ITEMS,
  QUICK_SEARCH_RECENT_KEY,
  filterQuickSearchItems,
  getVisibleQuickSearchItems,
  readRecentQuickSearchPaths,
  recordRecentQuickSearchPath,
} from './quickSearch'

function translateFrom(tree: Record<string, unknown>, key: string): string {
  const parts = key.split('.')
  let cur: unknown = tree
  for (const part of parts) {
    if (!cur || typeof cur !== 'object') return key
    cur = (cur as Record<string, unknown>)[part]
  }
  return typeof cur === 'string' ? cur : key
}

const zhT = (key: string) => translateFrom(zhCN as unknown as Record<string, unknown>, key)
const enT = (key: string) => translateFrom(enUS as unknown as Record<string, unknown>, key)

describe('quick search index', () => {
  beforeEach(() => {
    window.localStorage.removeItem(QUICK_SEARCH_RECENT_KEY)
  })

  it('indexes all 40 feature entries with unique paths', () => {
    expect(QUICK_SEARCH_ITEMS).toHaveLength(40)
    expect(new Set(QUICK_SEARCH_ITEMS.map((item) => item.path)).size).toBe(40)
  })

  it('finds hidden/consolidated subpages directly by Chinese and English aliases', () => {
    const adminCtx = { role: 'admin', localMode: false, supportsFeature: () => true }

    expect(filterQuickSearchItems('Mock', zhT, adminCtx).map((i) => i.path)).toContain('/mock-rules')
    expect(filterQuickSearchItems('挡板', zhT, adminCtx).map((i) => i.path)).toContain('/mock-rules')
    expect(filterQuickSearchItems('POM', zhT, adminCtx).map((i) => i.path)).toContain('/system/web-assets')
    expect(filterQuickSearchItems('审计', zhT, adminCtx).map((i) => i.path)).toContain('/system/audit-logs')
    expect(filterQuickSearchItems('模型', zhT, adminCtx).map((i) => i.path)).toContain('/system/ai-llm-configs')
    expect(filterQuickSearchItems('节点', zhT, adminCtx).map((i) => i.path)).toContain('/system/remote-nodes')
    expect(filterQuickSearchItems('openapi', enT, adminCtx).map((i) => i.path)).toContain('/system/api-contract-assets')

    const bugTrackers = QUICK_SEARCH_ITEMS.find((i) => i.path === '/system/bug-trackers')
    expect(bugTrackers?.groupKey).toBe('menu.groups.test_assets_new')
    expect(bugTrackers?.parentKey).toBeUndefined()

    const llmConfig = QUICK_SEARCH_ITEMS.find((i) => i.path === '/system/ai-llm-configs')
    expect(llmConfig?.groupKey).toBe('menu.groups.system_center')
    expect(llmConfig?.parentKey).toBeUndefined()
  })

  it('respects user roles and local mode when listing visible items', () => {
    const viewerPaths = getVisibleQuickSearchItems({
      role: 'viewer',
      localMode: false,
      supportsFeature: () => true,
    }).map((item) => item.path)
    expect(viewerPaths).not.toContain('/system/users')
    expect(viewerPaths).not.toContain('/system/ai-llm-configs')
    expect(viewerPaths).not.toContain('/system/toolbox')

    const engineerPaths = getVisibleQuickSearchItems({
      role: 'engineer',
      localMode: false,
      supportsFeature: () => true,
    }).map((item) => item.path)
    expect(engineerPaths).toContain('/system/config')
    expect(engineerPaths).toContain('/system/toolbox')
    expect(engineerPaths).not.toContain('/system/users')
    expect(engineerPaths).not.toContain('/system/remote-nodes')

    const localAdminPaths = getVisibleQuickSearchItems({
      role: 'admin',
      localMode: true,
      supportsFeature: () => true,
    }).map((item) => item.path)
    expect(localAdminPaths).not.toContain('/system/toolbox')
    expect(localAdminPaths).not.toContain('/tasks')
    expect(localAdminPaths).not.toContain('/system/users')
    expect(localAdminPaths).not.toContain('/system/run-retention')
    expect(localAdminPaths).not.toContain('/system/dashboard-alerts')
    expect(localAdminPaths).not.toContain('/system/notifications')
    expect(localAdminPaths).not.toContain('/system/bug-trackers')
    expect(localAdminPaths).not.toContain('/system/storage')
    expect(localAdminPaths).toContain('/system/audit-logs')
    expect(localAdminPaths).toContain('/cloud-sync')

    const withoutHermes = getVisibleQuickSearchItems({
      role: 'admin',
      localMode: true,
      supportsFeature: (feature) => feature !== 'hermes',
    }).map((item) => item.path)
    expect(withoutHermes).not.toContain('/hermes')
  })

  it('records recent visited paths up to 5 valid items', () => {
    recordRecentQuickSearchPath('/unknown-route')
    expect(readRecentQuickSearchPaths()).toEqual([])

    for (const path of ['/dashboard', '/mock-rules', '/system/users', '/system/web-assets', '/cases', '/plans']) {
      recordRecentQuickSearchPath(path)
    }
    expect(readRecentQuickSearchPaths()).toEqual([
      '/plans',
      '/cases',
      '/system/web-assets',
      '/system/users',
      '/mock-rules',
    ])
  })
})
