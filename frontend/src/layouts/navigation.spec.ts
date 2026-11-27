import { describe, expect, it } from 'vitest'

import {
  getBreadcrumbKeys,
  getMenuOpenKeys,
  getRouteTitleKey,
  getSelectedMenuKey,
  resolveAccordionOpenKeys,
} from './navigation'

describe('layout navigation state', () => {
  it('builds a three-level breadcrumb for subpages consolidated under a hub', () => {
    expect(getBreadcrumbKeys('/system/users', 'menu.system.users')).toEqual([
      'menu.groups.system_center',
      'menu.system_center.governance',
      'menu.system.users',
    ])
    expect(getBreadcrumbKeys('/system/environments', 'menu.system.environments')).toEqual([
      'menu.groups.system_center',
      'hub.settings.group_project',
      'menu.system.environments',
    ])
    expect(getBreadcrumbKeys('/system/storage', 'menu.system.storage')).toEqual([
      'menu.groups.system_center',
      'hub.settings.group_platform',
      'menu.system.storage',
    ])
    expect(getBreadcrumbKeys('/mock-rules', 'menu.mock_rules')).toEqual([
      'menu.groups.test_capabilities',
      'menu.capabilities.api',
      'menu.mock_rules',
    ])
    expect(getBreadcrumbKeys('/system/bug-trackers', 'menu.system.bug_trackers')).toEqual([
      'menu.groups.test_assets_new',
      'menu.system.bug_trackers',
    ])
    expect(getBreadcrumbKeys('/system/ai-llm-configs', 'menu.system.ai_llm_configs')).toEqual([
      'menu.groups.system_center',
      'menu.system.ai_llm_configs',
    ])
  })

  it('keeps deep case routes selected under the test-assets group', () => {
    expect(getSelectedMenuKey('/cases/42')).toBe('/cases')
    expect(getSelectedMenuKey('/projects/7/cases')).toBe('/cases')
    expect(getSelectedMenuKey('/case-reviews')).toBe('/cases')
    expect(getMenuOpenKeys('/projects/7/cases')).toEqual(['test-assets'])
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

  it('maps test suites and plans to the shared plans-and-suites entry with accurate breadcrumbs', () => {
    expect(getSelectedMenuKey('/plans')).toBe('/plans')
    expect(getSelectedMenuKey('/suites')).toBe('/plans')
    expect(getSelectedMenuKey('/suites/42')).toBe('/plans')
    expect(getBreadcrumbKeys('/suites/42', 'menu.assets.suites')).toEqual([
      'menu.groups.test_assets_new',
      'menu.assets.plans_and_suites',
      'menu.assets.suites',
    ])
  })

  it('uses the specific title for mobile task and report detail routes', () => {
    expect(getRouteTitleKey('/mobile-special/tasks/12')).toBe('menu.mobile_special.tasks')
    expect(getRouteTitleKey('/mobile-special/reports/12')).toBe('menu.mobile_special.reports')
    expect(getSelectedMenuKey('/mobile-special/reports/12')).toBe('/mobile-special/workbench')
  })

  it('maps consolidated capability, report, and system routes to their parent sidebar entry', () => {
    expect(getSelectedMenuKey('/system/web-assets')).toBe('/ui-workbench')
    expect(getSelectedMenuKey('/system/api-contract-assets')).toBe('/api-workbench')
    expect(getSelectedMenuKey('/mock-rules')).toBe('/api-workbench')
    expect(getSelectedMenuKey('/cloud-sync')).toBe('/reports')
    expect(getSelectedMenuKey('/system/datasets')).toBe('/system/datasets')
    expect(getSelectedMenuKey('/system/users')).toBe('/system/users')
    expect(getSelectedMenuKey('/system/audit-logs')).toBe('/system/users')
    expect(getSelectedMenuKey('/system/security')).toBe('/system/users')
    expect(getBreadcrumbKeys('/system/security', 'menu.system.security_governance')).toEqual([
      'menu.groups.system_center',
      'menu.system_center.governance',
      'menu.system.security_governance',
    ])
    expect(getSelectedMenuKey('/system/toolbox')).toBe('/system/toolbox')
    expect(getSelectedMenuKey('/system/remote-nodes')).toBe('/system/toolbox')
    expect(getSelectedMenuKey('/system/ai-llm-configs')).toBe('/system/ai-llm-configs')
    expect(getSelectedMenuKey('/system/bug-trackers')).toBe('/system/bug-trackers')
    expect(getSelectedMenuKey('/system/environments')).toBe('/system/environments')
    expect(getSelectedMenuKey('/system/global-variables')).toBe('/system/environments')
    expect(getSelectedMenuKey('/system/notifications')).toBe('/system/environments')
    expect(getSelectedMenuKey('/system/config')).toBe('/system/config')
    expect(getSelectedMenuKey('/system/storage')).toBe('/system/config')
    expect(getSelectedMenuKey('/system/startup-config')).toBe('/system/config')

    expect(getMenuOpenKeys('/system/web-assets')).toEqual(['test-capabilities'])
    expect(getMenuOpenKeys('/system/api-contract-assets')).toEqual(['test-capabilities'])
    expect(getMenuOpenKeys('/cloud-sync')).toEqual(['test-assets'])
    expect(getMenuOpenKeys('/system/bug-trackers')).toEqual(['test-assets'])
    expect(getMenuOpenKeys('/system/ai-llm-configs')).toEqual(['system-center'])
  })

  it('keeps AI workbench, healing, and knowledge routes under the intelligence center group', () => {
    expect(getSelectedMenuKey('/ai-workbench')).toBe('/ai-workbench')
    expect(getSelectedMenuKey('/system/healing-examples')).toBe('/ai-workbench')
    expect(getSelectedMenuKey('/system/ai-healing-stats')).toBe('/ai-workbench')
    expect(getSelectedMenuKey('/requirements')).toBe('/requirements')
    expect(getSelectedMenuKey('/knowledge')).toBe('/requirements')
    expect(getMenuOpenKeys('/ai-workbench')).toEqual(['intelligence-center'])
    expect(getMenuOpenKeys('/system/healing-examples')).toEqual(['intelligence-center'])
    expect(getMenuOpenKeys('/knowledge')).toEqual(['intelligence-center'])
    expect(getMenuOpenKeys('/hermes')).toEqual(['intelligence-center'])
    expect(getMenuOpenKeys('/ai-chat')).toEqual(['intelligence-center'])
    expect(getSelectedMenuKey('/ai-chat')).toBe('/hermes')
    expect(getRouteTitleKey('/knowledge')).toBe('menu.intelligence.knowledge')
    expect(getRouteTitleKey('/ai-chat')).toBe('menu.intelligence.ai_chat')
    expect(getBreadcrumbKeys('/knowledge', 'menu.intelligence.knowledge')).toEqual([
      'menu.groups.intelligence_center',
      'menu.intelligence.requirements_knowledge',
      'menu.intelligence.knowledge',
    ])
  })

  it('keeps only the most recently opened sidebar group in accordion mode', () => {
    expect(resolveAccordionOpenKeys(['workbench'], ['workbench', 'test-capabilities'])).toEqual(['test-capabilities'])
    expect(resolveAccordionOpenKeys(['workbench'], [])).toEqual([])
    expect(resolveAccordionOpenKeys([], ['system-center'])).toEqual(['system-center'])
  })

  it('does not duplicate a group when the route title is the group title', () => {
    expect(getBreadcrumbKeys('/unknown', 'menu.groups.workbench')).toEqual(['menu.groups.workbench'])
  })
})
