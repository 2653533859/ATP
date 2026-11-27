export type NavigationGroup = 'workbench' | 'test-capabilities' | 'test-assets' | 'intelligence-center' | 'system-center'

export const routeMenuGroups: Record<string, NavigationGroup> = {
  '/dashboard': 'workbench',
  '/workbench': 'workbench',
  '/projects': 'workbench',
  '/tasks': 'workbench',
  '/runs': 'workbench',
  '/api-workbench': 'test-capabilities',
  '/mock-rules': 'test-capabilities',
  '/system/api-contract-assets': 'test-capabilities',
  '/mobile-special': 'test-capabilities',
  '/devices': 'test-capabilities',
  '/apks': 'test-capabilities',
  '/ios-assets': 'test-capabilities',
  '/ui-workbench': 'test-capabilities',
  '/system/web-assets': 'test-capabilities',
  '/performance-workbench': 'test-capabilities',
  '/system/performance': 'test-capabilities',
  '/cases': 'test-assets',
  '/plans': 'test-assets',
  '/suites': 'test-assets',
  '/case-reviews': 'test-assets',
  '/system/datasets': 'test-assets',
  '/bugs': 'test-assets',
  '/system/bug-trackers': 'test-assets',
  '/reports': 'test-assets',
  '/cloud-sync': 'test-assets',
  '/hermes': 'intelligence-center',
  '/ai-chat': 'intelligence-center',
  '/ai-workbench': 'intelligence-center',
  '/system/ai-healing-stats': 'intelligence-center',
  '/system/healing-examples': 'intelligence-center',
  '/requirements': 'intelligence-center',
  '/knowledge': 'intelligence-center',
  '/system': 'system-center',
}

export const navigationGroupTitleKeys: Record<NavigationGroup, string> = {
  workbench: 'menu.groups.workbench',
  'test-capabilities': 'menu.groups.test_capabilities',
  'test-assets': 'menu.groups.test_assets_new',
  'intelligence-center': 'menu.groups.intelligence_center',
  'system-center': 'menu.groups.system_center',
}

export const systemRouteTitles: Record<string, string> = {
  '/system/environments': 'menu.system.environments',
  '/system/startup-config': 'menu.system.startup_config',
  '/system/global-variables': 'menu.system.global_variables',
  '/system/datasets': 'menu.system.datasets',
  '/system/web-assets': 'menu.system.web_assets',
  '/system/api-contract-assets': 'menu.system.api_contract_assets',
  '/system/ai-llm-configs': 'menu.system.ai_llm_configs',
  '/system/healing-examples': 'menu.system.ai_healing_examples',
  '/system/ai-healing-stats': 'menu.system.ai_healing_stats',
  '/system/performance': 'menu.system.performance',
  '/system/storage': 'menu.system.storage',
  '/system/run-retention': 'menu.system.run_retention',
  '/system/dashboard-alerts': 'menu.system.dashboard_alerts',
  '/system/security': 'menu.system.security_governance',
  '/system/notifications': 'menu.system.notifications',
  '/system/bug-trackers': 'menu.system.bug_trackers',
  '/system/users': 'menu.system.users',
  '/system/audit-logs': 'menu.system.audit_logs',
  '/system/remote-nodes': 'menu.system_center.remote_nodes',
  '/system/toolbox': 'menu.system_center.toolbox',
  '/system/config': 'menu.system_center.config',
}

const mobileRouteTitles: Record<string, string> = {
  '/mobile-special/tasks': 'menu.mobile_special.tasks',
  '/mobile-special/reports': 'menu.mobile_special.reports',
}

const SUBPAGE_HUB_PARENTS: Array<[string, string]> = [
  ['/mock-rules', 'menu.capabilities.api'],
  ['/system/api-contract-assets', 'menu.capabilities.api'],
  ['/system/web-assets', 'menu.capabilities.ui'],
  ['/case-reviews', 'menu.assets.cases'],
  ['/plans', 'menu.assets.plans_and_suites'],
  ['/suites', 'menu.assets.plans_and_suites'],
  ['/cloud-sync', 'menu.assets.reports'],
  ['/ai-workbench', 'menu.intelligence.ai_hub'],
  ['/system/ai-healing-stats', 'menu.intelligence.ai_hub'],
  ['/system/healing-examples', 'menu.intelligence.ai_hub'],
  ['/requirements', 'menu.intelligence.requirements_knowledge'],
  ['/knowledge', 'menu.intelligence.requirements_knowledge'],
  ['/system/users', 'menu.system_center.governance'],
  ['/system/audit-logs', 'menu.system_center.governance'],
  ['/system/run-retention', 'menu.system_center.governance'],
  ['/system/dashboard-alerts', 'menu.system_center.governance'],
  ['/system/security', 'menu.system_center.governance'],
  ['/system/toolbox', 'menu.system_center.remote_ops'],
  ['/system/remote-nodes', 'menu.system_center.remote_ops'],
  ['/system/environments', 'hub.settings.group_project'],
  ['/system/global-variables', 'hub.settings.group_project'],
  ['/system/notifications', 'hub.settings.group_project'],
  ['/system/config', 'hub.settings.group_platform'],
  ['/system/storage', 'hub.settings.group_platform'],
  ['/system/startup-config', 'hub.settings.group_platform'],
]

export function findRouteEntry<T>(entries: Record<string, T>, path: string): T | undefined {
  return Object.entries(entries).find(([prefix]) => path.startsWith(prefix))?.[1]
}

export function getMenuOpenKeys(path: string, _localMode = false): string[] {
  if (path.startsWith('/projects/') && path.endsWith('/cases')) return ['test-assets']
  const group = findRouteEntry(routeMenuGroups, path)
  return group ? [group] : []
}

export function resolveAccordionOpenKeys(
  currentOpenKeys: readonly string[],
  nextOpenKeys: readonly string[],
): string[] {
  const latestOpened = nextOpenKeys.find((key) => !currentOpenKeys.includes(key))
  if (latestOpened) return [latestOpened]
  return nextOpenKeys.length ? [nextOpenKeys[nextOpenKeys.length - 1]] : []
}

const ROUTE_TO_MENU_KEY: Array<[string, string]> = [
  ['/api-workbench', '/api-workbench'],
  ['/mock-rules', '/api-workbench'],
  ['/system/api-contract-assets', '/api-workbench'],
  ['/mobile-special/', '/mobile-special/workbench'],
  ['/devices', '/mobile-special/workbench'],
  ['/apks', '/mobile-special/workbench'],
  ['/ios-assets', '/mobile-special/workbench'],
  ['/ui-workbench', '/ui-workbench'],
  ['/system/web-assets', '/ui-workbench'],
  ['/performance-workbench', '/performance-workbench'],
  ['/system/performance', '/performance-workbench'],
  ['/cases', '/cases'],
  ['/case-reviews', '/cases'],
  ['/plans', '/plans'],
  ['/suites', '/plans'],
  ['/system/datasets', '/system/datasets'],
  ['/bugs', '/bugs'],
  ['/system/bug-trackers', '/system/bug-trackers'],
  ['/reports', '/reports'],
  ['/cloud-sync', '/reports'],
  ['/hermes', '/hermes'],
  ['/ai-chat', '/hermes'],
  ['/ai-workbench', '/ai-workbench'],
  ['/system/ai-healing-stats', '/ai-workbench'],
  ['/system/healing-examples', '/ai-workbench'],
  ['/requirements', '/requirements'],
  ['/knowledge', '/requirements'],
  ['/system/ai-llm-configs', '/system/ai-llm-configs'],
  ['/system/environments', '/system/environments'],
  ['/system/global-variables', '/system/environments'],
  ['/system/notifications', '/system/environments'],
  ['/system/users', '/system/users'],
  ['/system/audit-logs', '/system/users'],
  ['/system/run-retention', '/system/users'],
  ['/system/dashboard-alerts', '/system/users'],
  ['/system/security', '/system/users'],
  ['/system/toolbox', '/system/toolbox'],
  ['/system/remote-nodes', '/system/toolbox'],
  ['/system/config', '/system/config'],
  ['/system/storage', '/system/config'],
  ['/system/startup-config', '/system/config'],
  ['/system/', '/system/config'],
]

export function getSelectedMenuKey(path: string, _localMode = false): string {
  if (path.startsWith('/projects/') && path.endsWith('/cases')) return '/cases'
  if (path.startsWith('/projects/')) return '/projects'
  if (path === '/runs' || path.startsWith('/runs/')) return '/tasks'

  const matched = ROUTE_TO_MENU_KEY.find(([prefix]) =>
    prefix.endsWith('/') ? path.startsWith(prefix) : path === prefix || path.startsWith(`${prefix}/`),
  )
  return matched ? matched[1] : path
}

export function getRouteTitleKey(path: string, menuTitleKey?: unknown): string {
  if (typeof menuTitleKey === 'string' && menuTitleKey) return menuTitleKey
  const mobileTitle = findRouteEntry(mobileRouteTitles, path)
  if (mobileTitle) return mobileTitle
  if (path.startsWith('/dashboard')) return 'menu.dashboard'
  if (path.startsWith('/projects')) return 'menu.projects'
  if (path.startsWith('/account')) return 'account.title'
  if (path.startsWith('/cases')) return 'menu.cases'
  if (path.startsWith('/runs')) return 'menu.runs'
  if (path.startsWith('/cloud-sync')) return 'menu.workbench.cloud_sync'
  if (path.startsWith('/suites')) return 'menu.assets.suites'
  if (path.startsWith('/plans')) return 'menu.assets.plans'
  if (path.startsWith('/hermes')) return 'menu.intelligence.hermes'
  if (path.startsWith('/ai-chat')) return 'menu.intelligence.ai_chat'
  if (path.startsWith('/requirements')) return 'menu.intelligence.requirements'
  if (path.startsWith('/knowledge')) return 'menu.intelligence.knowledge'
  if (path.startsWith('/ios-assets')) return 'menu.ios_assets'
  if (path.startsWith('/mock')) return 'menu.mock_rules'
  if (path.startsWith('/mobile-special')) return 'menu.mobile_special.title'
  if (path.startsWith('/system')) return findRouteEntry(systemRouteTitles, path) ?? 'menu.system.title'
  return 'layout.sider_title_full'
}

export function getBreadcrumbKeys(path: string, routeTitleKey: string): string[] {
  const group =
    path.startsWith('/projects/') && path.endsWith('/cases')
      ? 'test-assets'
      : findRouteEntry(routeMenuGroups, path)
  if (!group) return [routeTitleKey]

  const keys: string[] = [navigationGroupTitleKeys[group]]
  const hubParent = SUBPAGE_HUB_PARENTS.find(([prefix]) => path === prefix || path.startsWith(`${prefix}/`))?.[1]
  if (hubParent && !keys.includes(hubParent)) {
    keys.push(hubParent)
  }
  if (!keys.includes(routeTitleKey)) {
    keys.push(routeTitleKey)
  }
  return keys
}
