import { describe, expect, it } from 'vitest'

import { getBreadcrumbKeys, getRouteTitleKey, getSelectedMenuKey } from './navigation'

describe('layout navigation state', () => {
  it('builds a group and page breadcrumb for system pages', () => {
    expect(getBreadcrumbKeys('/system/users', 'menu.system.users')).toEqual([
      'menu.groups.system_center',
      'menu.system.users',
    ])
  })

  it('keeps deep case routes selected under the test-assets group', () => {
    expect(getSelectedMenuKey('/cases/42')).toBe('/cases')
    expect(getSelectedMenuKey('/projects/7/cases')).toBe('/cases')
    expect(getBreadcrumbKeys('/cases/42', 'menu.cases')).toEqual(['menu.groups.test_assets_new', 'menu.cases'])
  })

  it('uses the specific title for mobile task and report detail routes', () => {
    expect(getRouteTitleKey('/mobile-special/tasks/12')).toBe('menu.mobile_special.tasks')
    expect(getRouteTitleKey('/mobile-special/reports/12')).toBe('menu.mobile_special.reports')
  })

  it('does not duplicate a group when the route title is the group title', () => {
    expect(getBreadcrumbKeys('/unknown', 'menu.groups.workbench')).toEqual(['menu.groups.workbench'])
  })
})
