import { describe, expect, it } from 'vitest'

import { getBreadcrumbKeys, getMenuOpenKeys, getRouteTitleKey, getSelectedMenuKey } from './navigation'

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

  it('routes legacy run details through the task center navigation entry', () => {
    expect(getSelectedMenuKey('/runs')).toBe('/tasks')
    expect(getSelectedMenuKey('/runs/42')).toBe('/tasks')
    expect(getBreadcrumbKeys('/runs/42', 'menu.runs')).toEqual([
      'menu.groups.workbench',
      'menu.runs',
    ])
  })

  it('keeps test suite deep links selected as test suites instead of test plans', () => {
    expect(getSelectedMenuKey('/suites')).toBe('/suites')
    expect(getSelectedMenuKey('/suites/42')).toBe('/suites')
    expect(getBreadcrumbKeys('/suites/42', 'menu.assets.suites')).toEqual([
      'menu.groups.test_assets_new',
      'menu.assets.suites',
    ])
  })

  it('uses the specific title for mobile task and report detail routes', () => {
    expect(getRouteTitleKey('/mobile-special/tasks/12')).toBe('menu.mobile_special.tasks')
    expect(getRouteTitleKey('/mobile-special/reports/12')).toBe('menu.mobile_special.reports')
    expect(getSelectedMenuKey('/mobile-special/reports/12')).toBe('/mobile-special/workbench')
  })

  it('selects dedicated sidebar entries for asset and system pages directly', () => {
    expect(getSelectedMenuKey('/system/web-assets')).toBe('/system/web-assets')
    expect(getSelectedMenuKey('/system/api-contract-assets')).toBe('/system/api-contract-assets')
    expect(getSelectedMenuKey('/system/datasets')).toBe('/system/datasets')
    expect(getSelectedMenuKey('/system/users')).toBe('/system/users')
    expect(getSelectedMenuKey('/system/ai-llm-configs')).toBe('/system/ai-llm-configs')
    expect(getMenuOpenKeys('/system/web-assets')).toEqual(['test-assets'])
    expect(getMenuOpenKeys('/system/ai-llm-configs')).toEqual(['system-center'])
  })

  it('keeps AI healing pages under the intelligence center group', () => {
    expect(getSelectedMenuKey('/system/healing-examples')).toBe('/system/healing-examples')
    expect(getSelectedMenuKey('/system/ai-healing-stats')).toBe('/system/ai-healing-stats')
    expect(getMenuOpenKeys('/system/healing-examples')).toEqual(['intelligence-center'])
  })

  it('keeps intelligence center routes open and resolves their breadcrumbs', () => {
    expect(getMenuOpenKeys('/knowledge')).toEqual(['intelligence-center'])
    expect(getMenuOpenKeys('/hermes')).toEqual(['intelligence-center'])
    expect(getMenuOpenKeys('/ai-chat')).toEqual(['intelligence-center'])
    expect(getMenuOpenKeys('/requirements')).toEqual(['intelligence-center'])
    expect(getSelectedMenuKey('/knowledge')).toBe('/knowledge')
    expect(getSelectedMenuKey('/ai-chat')).toBe('/hermes')
    expect(getRouteTitleKey('/knowledge')).toBe('menu.intelligence.knowledge')
    expect(getRouteTitleKey('/ai-chat')).toBe('menu.intelligence.ai_chat')
    expect(getBreadcrumbKeys('/knowledge', 'menu.intelligence.knowledge')).toEqual([
      'menu.groups.intelligence_center',
      'menu.intelligence.knowledge',
    ])
    expect(getBreadcrumbKeys('/ai-chat', 'menu.intelligence.ai_chat')).toEqual([
      'menu.groups.intelligence_center',
      'menu.intelligence.ai_chat',
    ])
  })

  it('does not duplicate a group when the route title is the group title', () => {
    expect(getBreadcrumbKeys('/unknown', 'menu.groups.workbench')).toEqual(['menu.groups.workbench'])
  })
})
