import { describe, expect, it } from 'vitest'

import { getVisibleHubTabs, matchActiveHubTab } from './hubConfig'

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

  it('filters project-settings and platform-settings tabs by role and localMode', () => {
    const engineerProjectTabs = getVisibleHubTabs('project-settings', {
      role: 'engineer',
      localMode: false,
      supportsFeature: allFeatures,
    })
    expect(engineerProjectTabs.map((item) => item.path)).toEqual([
      '/system/environments',
      '/system/global-variables',
      '/system/notifications',
    ])

    const localAdminProjectTabs = getVisibleHubTabs('project-settings', {
      role: 'admin',
      localMode: true,
      supportsFeature: allFeatures,
    })
    expect(localAdminProjectTabs.map((item) => item.path)).toEqual([
      '/system/environments',
      '/system/global-variables',
    ])

    const engineerPlatformTabs = getVisibleHubTabs('platform-settings', {
      role: 'engineer',
      localMode: false,
      supportsFeature: allFeatures,
    })
    expect(engineerPlatformTabs.map((item) => item.path)).toEqual([
      '/system/config',
      '/system/storage',
    ])

    const adminPlatformTabs = getVisibleHubTabs('platform-settings', {
      role: 'admin',
      localMode: false,
      supportsFeature: allFeatures,
    })
    expect(adminPlatformTabs.map((item) => item.path)).toEqual([
      '/system/config',
      '/system/storage',
      '/system/startup-config',
    ])

    const localAdminPlatformTabs = getVisibleHubTabs('platform-settings', {
      role: 'admin',
      localMode: true,
      supportsFeature: allFeatures,
    })
    expect(localAdminPlatformTabs.map((item) => item.path)).toEqual([
      '/system/config',
      '/system/startup-config',
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
