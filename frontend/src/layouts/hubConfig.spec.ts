import { describe, expect, it } from 'vitest'

import { SETTINGS_HUB_GROUPS, getVisibleHubTabs, isHubItemVisible, matchActiveHubTab } from './hubConfig'

const allFeatures = () => true

describe('hub navigation config', () => {
  it('exposes explicit capability tabs for API and UI hubs', () => {
    const apiTabs = getVisibleHubTabs('api', { role: 'tester', localMode: false, supportsFeature: allFeatures })
    expect(apiTabs.map((item) => item.path)).toEqual([
      '/api-workbench',
      '/mock-rules',
      '/system/api-contract-assets',
    ])

    const uiTabs = getVisibleHubTabs('ui', { role: 'viewer', localMode: false, supportsFeature: allFeatures })
    expect(uiTabs.map((item) => item.path)).toEqual(['/ui-workbench', '/system/web-assets'])
  })

  it('filters cloud-sync, AI healing, and remote nodes by role and runtime mode', () => {
    const engineerReports = getVisibleHubTabs('reports', {
      role: 'engineer',
      localMode: false,
      supportsFeature: allFeatures,
    })
    expect(engineerReports.map((item) => item.path)).toEqual(['/reports'])

    const adminReports = getVisibleHubTabs('reports', {
      role: 'admin',
      localMode: false,
      supportsFeature: allFeatures,
    })
    expect(adminReports.map((item) => item.path)).toEqual(['/reports', '/cloud-sync'])

    const localReports = getVisibleHubTabs('reports', {
      role: 'viewer',
      localMode: true,
      supportsFeature: allFeatures,
    })
    expect(localReports.map((item) => item.path)).toEqual(['/reports', '/cloud-sync'])

    const engineerAi = getVisibleHubTabs('ai-center', {
      role: 'engineer',
      localMode: false,
      supportsFeature: allFeatures,
    })
    expect(engineerAi.map((item) => item.path)).toEqual(['/ai-workbench'])

    const adminAi = getVisibleHubTabs('ai-center', {
      role: 'admin',
      localMode: false,
      supportsFeature: allFeatures,
    })
    expect(adminAi.map((item) => item.path)).toEqual([
      '/ai-workbench',
      '/system/ai-healing-stats',
      '/system/healing-examples',
    ])

    const engineerRemote = getVisibleHubTabs('remote-ops', {
      role: 'engineer',
      localMode: false,
      supportsFeature: allFeatures,
    })
    expect(engineerRemote.map((item) => item.path)).toEqual(['/system/toolbox'])

    const localRemote = getVisibleHubTabs('remote-ops', {
      role: 'admin',
      localMode: true,
      supportsFeature: allFeatures,
    })
    expect(localRemote).toEqual([])
  })

  it('filters settings hub navigation items properly for engineers vs admins and localMode', () => {
    const engineerPaths = SETTINGS_HUB_GROUPS.flatMap((group) =>
      group.items.filter((item) => isHubItemVisible(item, {
        role: 'engineer',
        localMode: false,
        supportsFeature: allFeatures,
      })).map((item) => item.path),
    )
    expect(engineerPaths).toEqual([
      '/system/environments',
      '/system/global-variables',
      '/system/notifications',
      '/system/bug-trackers',
      '/system/storage',
      '/system/config',
    ])

    const localAdminSettings = SETTINGS_HUB_GROUPS.flatMap((group) =>
      group.items.filter((item) => isHubItemVisible(item, {
        role: 'admin',
        localMode: true,
        supportsFeature: allFeatures,
      })).map((item) => item.path),
    )
    expect(localAdminSettings).toEqual([
      '/system/environments',
      '/system/global-variables',
      '/system/ai-llm-configs',
      '/system/startup-config',
      '/system/config',
    ])

    const localGovTabs = getVisibleHubTabs('governance', {
      role: 'admin',
      localMode: true,
      supportsFeature: allFeatures,
    })
    expect(localGovTabs.map((item) => item.path)).toEqual(['/system/audit-logs'])
  })

  it('matches active hub tab across deep project case routes', () => {
    const caseTabs = getVisibleHubTabs('cases', { role: 'engineer', localMode: false, supportsFeature: allFeatures })
    expect(matchActiveHubTab(caseTabs, '/projects/12/cases')).toBe('/cases')
    expect(matchActiveHubTab(caseTabs, '/case-reviews')).toBe('/case-reviews')
  })
})
