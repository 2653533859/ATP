import { hasAnyRole, type UserRole } from '@/utils/permissions'

export interface VisibilityRule {
  roles?: readonly UserRole[]
  feature?: string
  serverOnly?: boolean
  localOrAdmin?: boolean
}

export interface HubTabItem extends VisibilityRule {
  path: string
  labelKey: string
  matchPrefixes?: readonly string[]
}

export type HubId =
  | 'api'
  | 'ui'
  | 'cases'
  | 'plans-suites'
  | 'reports'
  | 'ai-center'
  | 'requirements-knowledge'
  | 'governance'
  | 'remote-ops'

export interface HubDefinition {
  titleKey: string
  tabs: HubTabItem[]
}

export interface HubVisibilityContext {
  role?: string | null
  localMode: boolean
  supportsFeature: (feature: string) => boolean
}

export interface SettingsHubGroup {
  titleKey: string
  items: HubTabItem[]
}

export const TABBED_HUBS: Record<HubId, HubDefinition> = {
  api: {
    titleKey: 'menu.capabilities.api',
    tabs: [
      { path: '/api-workbench', labelKey: 'hub.api.workbench' },
      { path: '/mock-rules', labelKey: 'menu.mock_rules' },
      { path: '/system/api-contract-assets', labelKey: 'menu.system.api_contract_assets' },
    ],
  },
  ui: {
    titleKey: 'menu.capabilities.ui',
    tabs: [
      { path: '/ui-workbench', labelKey: 'hub.ui.workbench' },
      { path: '/system/web-assets', labelKey: 'menu.system.web_assets' },
    ],
  },
  cases: {
    titleKey: 'menu.assets.cases',
    tabs: [
      {
        path: '/cases',
        labelKey: 'hub.cases.library',
        matchPrefixes: ['/cases', '/projects/'],
      },
      { path: '/case-reviews', labelKey: 'menu.assets.reviews' },
    ],
  },
  'plans-suites': {
    titleKey: 'menu.assets.plans_and_suites',
    tabs: [
      { path: '/plans', labelKey: 'menu.assets.plans', feature: 'plans' },
      { path: '/suites', labelKey: 'menu.assets.suites', feature: 'suites' },
    ],
  },
  reports: {
    titleKey: 'menu.assets.reports',
    tabs: [
      { path: '/reports', labelKey: 'hub.reports.quality' },
      { path: '/cloud-sync', labelKey: 'hub.reports.cloud_sync', localOrAdmin: true },
    ],
  },
  'ai-center': {
    titleKey: 'menu.intelligence.ai_hub',
    tabs: [
      { path: '/ai-workbench', labelKey: 'menu.capabilities.ai', feature: 'ai_generation' },
      { path: '/system/ai-healing-stats', labelKey: 'menu.system.ai_healing_stats', roles: ['admin'] },
      { path: '/system/healing-examples', labelKey: 'menu.system.ai_healing_examples', roles: ['admin'] },
    ],
  },
  'requirements-knowledge': {
    titleKey: 'menu.intelligence.requirements_knowledge',
    tabs: [
      { path: '/requirements', labelKey: 'menu.intelligence.requirements' },
      { path: '/knowledge', labelKey: 'menu.intelligence.knowledge' },
    ],
  },
  governance: {
    titleKey: 'menu.system_center.governance',
    tabs: [
      { path: '/system/users', labelKey: 'menu.system.users', roles: ['admin'], serverOnly: true },
      { path: '/system/audit-logs', labelKey: 'menu.system.audit_logs', roles: ['admin'] },
      { path: '/system/run-retention', labelKey: 'menu.system.run_retention', roles: ['admin'], serverOnly: true },
      { path: '/system/dashboard-alerts', labelKey: 'menu.system.dashboard_alerts', roles: ['admin'], serverOnly: true },
    ],
  },
  'remote-ops': {
    titleKey: 'menu.system_center.remote_ops',
    tabs: [
      {
        path: '/system/toolbox',
        labelKey: 'menu.system_center.toolbox',
        roles: ['admin', 'engineer'],
        serverOnly: true,
      },
      {
        path: '/system/remote-nodes',
        labelKey: 'menu.system_center.remote_nodes',
        roles: ['admin'],
        serverOnly: true,
      },
    ],
  },
}

export const SETTINGS_HUB_GROUPS: SettingsHubGroup[] = [
  {
    titleKey: 'hub.settings.group_project',
    items: [
      { path: '/system/environments', labelKey: 'menu.system.environments' },
      { path: '/system/global-variables', labelKey: 'menu.system.global_variables' },
      { path: '/system/notifications', labelKey: 'menu.system.notifications', roles: ['admin', 'engineer'], serverOnly: true },
      { path: '/system/bug-trackers', labelKey: 'menu.system.bug_trackers', roles: ['admin', 'engineer'], serverOnly: true },
    ],
  },
  {
    titleKey: 'hub.settings.group_platform',
    items: [
      { path: '/system/ai-llm-configs', labelKey: 'menu.system.ai_llm_configs', roles: ['admin'] },
      { path: '/system/storage', labelKey: 'menu.system.storage', roles: ['admin', 'engineer'], serverOnly: true },
      { path: '/system/startup-config', labelKey: 'menu.system.startup_config', roles: ['admin'] },
      { path: '/system/config', labelKey: 'hub.settings.revisions', roles: ['admin', 'engineer'] },
    ],
  },
]

export function isNavItemVisible(item: VisibilityRule, ctx: HubVisibilityContext): boolean {
  if (item.serverOnly && ctx.localMode) return false
  if (item.localOrAdmin && !ctx.localMode && !hasAnyRole(ctx.role, ['admin'])) return false
  if (item.feature && !ctx.supportsFeature(item.feature)) return false
  if (item.roles && !hasAnyRole(ctx.role, item.roles)) return false
  return true
}

export const isHubItemVisible = isNavItemVisible

export function getVisibleHubTabs(hubId: HubId, ctx: HubVisibilityContext): HubTabItem[] {
  const hub = TABBED_HUBS[hubId]
  if (!hub) return []
  return hub.tabs.filter((item) => isHubItemVisible(item, ctx))
}

export function matchActiveHubTab(tabs: readonly HubTabItem[], path: string): string {
  const exact = tabs.find((item) => path === item.path)
  if (exact) return exact.path
  const prefixed = tabs.find((item) => {
    if (item.matchPrefixes?.some((prefix) => path.startsWith(prefix))) return true
    return path.startsWith(`${item.path}/`)
  })
  return prefixed?.path ?? tabs[0]?.path ?? ''
}
