import { describe, expect, it } from 'vitest'

import router from './index'

describe('product navigation routes', () => {
  it('exposes every N0 roadmap entry with a title and description', () => {
    const expectedRoutes = [
      'workbench-todos',
      'tasks',
      'api-workbench',
      'mobile-special-workbench',
      'ui-workbench',
      'performance-workbench',
      'ai-workbench',
      'bugs',
      'reports',
      'case-reviews',
      'hermes',
      'requirements',
      'knowledge',
      'system-toolbox',
      'system-config',
    ]

    for (const routeName of expectedRoutes) {
      const route = router.getRoutes().find((item) => item.name === routeName)
      expect(route, `route ${routeName} should exist`).toBeDefined()
      expect(route?.meta.menuTitleKey).toBeTruthy()
      expect(route?.meta.descriptionKey).toBeTruthy()
    }
  })

  it('keeps the existing task and report routes available', () => {
    expect(router.hasRoute('mobile-special-tasks')).toBe(true)
    expect(router.hasRoute('mobile-special-reports')).toBe(true)
    expect(router.hasRoute('system-performance')).toBe(true)
    expect(router.hasRoute('system-api-contract-assets')).toBe(true)
  })
})
