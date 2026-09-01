export type NavigationGroup = 'workbench' | 'test-capabilities' | 'test-assets' | 'intelligence-center' | 'system-center'

export const routeMenuGroups: Record<string, NavigationGroup> = {
  '/dashboard': 'workbench',
  '/workbench': 'workbench',
  '/projects': 'workbench',
  '/tasks': 'workbench',
  '/runs': 'workbench',
  '/api-workbench': 'test-capabilities',
  '/mobile-special': 'test-capabilities',
  '/ui-workbench': 'test-capabilities',
  '/performance-workbench': 'test-capabilities',
  '/ai-workbench': 'test-capabilities',
  '/cases': 'test-assets',
  '/plans': 'test-assets',
  '/bugs': 'test-assets',
  '/reports': 'test-assets',
  '/case-reviews': 'test-assets',
  '/suites': 'test-assets',
  '/system/datasets': 'test-capabilities',
  '/system/web-assets': 'test-capabilities',
  '/system/api-contract-assets': 'test-capabilities',
  '/system/performance': 'test-capabilities',
  '/system/ai-healing-stats': 'test-capabilities',
  '/system/healing-examples': 'test-capabilities',
  '/system': 'system-center',
  '/devices': 'test-capabilities',
  '/apks': 'test-capabilities',
  '/ios-assets': 'test-capabilities',
  '/mock-rules': 'test-capabilities',
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
  '/system/notifications': 'menu.system.notifications',
  '/system/bug-trackers': 'menu.system.bug_trackers',
  '/system/users': 'menu.system.users',
  '/system/audit-logs': 'menu.system.audit_logs',
}

const mobileRouteTitles: Record<string, string> = {
  '/mobile-special/tasks': 'menu.mobile_special.tasks',
  '/mobile-special/reports': 'menu.mobile_special.reports',
}

export function findRouteEntry<T>(entries: Record<string, T>, path: string): T | undefined {
  return Object.entries(entries).find(([prefix]) => path.startsWith(prefix))?.[1]
}

export function getMenuOpenKeys(path: string): string[] {
  const group = findRouteEntry(routeMenuGroups, path)
  return group ? [group] : []
}

export function getSelectedMenuKey(path: string): string {
  if (path.startsWith('/projects/') && path.endsWith('/cases')) return '/cases'
  if (path.startsWith('/projects/')) return '/projects'
  if (path.startsWith('/cases/')) return '/cases'
  if (path === '/runs' || path.startsWith('/runs/')) return '/tasks'
  if (path.startsWith('/mobile-special/')) return '/mobile-special/workbench'
  if (path.startsWith('/devices') || path.startsWith('/apks') || path.startsWith('/ios-assets')) return '/mobile-special/workbench'
  if (path.startsWith('/system/performance')) return '/performance-workbench'
  if (path.startsWith('/system/web-assets')) return '/ui-workbench'
  if (path.startsWith('/system/api-contract-assets')) return '/api-workbench'
  if (path.startsWith('/system/datasets') || path.startsWith('/mock-rules')) return '/ai-workbench'
  // 自愈统计和自愈示例是 AI 能力页而非配置域，入口在 AI 工作台；若不在这里拦下，
  // 会被下面的 '/system/' 兜底高亮成配置中心。
  if (path.startsWith('/system/ai-healing-stats') || path.startsWith('/system/healing-examples')) return '/ai-workbench'
  if (path.startsWith('/suites')) return '/suites'
  if (path.startsWith('/system/toolbox')) return '/system/toolbox'
  if (path.startsWith('/system/config') || path.startsWith('/system/')) return '/system/config'
  return path
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
  if (path.startsWith('/suites')) return 'menu.suites'
  if (path.startsWith('/plans')) return 'menu.plans'
  if (path.startsWith('/devices')) return 'menu.devices'
  if (path.startsWith('/apks')) return 'menu.apks'
  if (path.startsWith('/ios-assets')) return 'menu.ios_assets'
  if (path.startsWith('/mock')) return 'menu.mock_rules'
  if (path.startsWith('/mobile-special')) return 'menu.mobile_special.title'
  if (path.startsWith('/system')) return findRouteEntry(systemRouteTitles, path) ?? 'menu.system.title'
  return 'layout.sider_title_full'
}

export function getBreadcrumbKeys(path: string, routeTitleKey: string): string[] {
  const group = findRouteEntry(routeMenuGroups, path)
  if (!group) return [routeTitleKey]
  const groupTitleKey = navigationGroupTitleKeys[group]
  return groupTitleKey === routeTitleKey ? [routeTitleKey] : [groupTitleKey, routeTitleKey]
}
