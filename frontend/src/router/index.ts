import { createRouter, createWebHistory } from 'vue-router'
import { message } from 'ant-design-vue'
import { useAuthStore } from '@/stores/auth'
import { hasAnyRole, type UserRole } from '@/utils/permissions'

const ADMIN_ONLY: UserRole[] = ['admin']
const ENGINEER_ONLY: UserRole[] = ['admin', 'engineer']

const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: '/login',
      name: 'login',
      component: () => import('@/views/auth/LoginView.vue'),
      meta: { public: true },
    },
    {
      path: '/',
      component: () => import('@/layouts/MainLayout.vue'),
      redirect: '/dashboard',
      children: [
        {
          path: '',
          redirect: '/dashboard',
        },
        {
          path: 'dashboard',
          name: 'dashboard',
          component: () => import('@/views/dashboard/DashboardView.vue'),
        },
        {
          path: 'workbench/todos',
          name: 'workbench-todos',
          component: () => import('@/views/workbench/WorkbenchTodosView.vue'),
          meta: {
            menuTitleKey: 'menu.workbench.todos',
            descriptionKey: 'navigation.placeholder.description.todos',
          },
        },
        {
          path: 'tasks',
          name: 'tasks',
          component: () => import('@/views/workbench/TaskCenterView.vue'),
          meta: {
            menuTitleKey: 'menu.workbench.tasks',
            descriptionKey: 'navigation.placeholder.description.tasks',
          },
        },
        {
          path: '',
          component: () => import('@/layouts/TabbedHubLayout.vue'),
          meta: { hubId: 'api' },
          children: [
            {
              path: 'api-workbench',
              name: 'api-workbench',
              component: () => import('@/views/workbench/ApiWorkbenchView.vue'),
              meta: {
                menuTitleKey: 'menu.capabilities.api',
                descriptionKey: 'navigation.placeholder.description.api',
              },
            },
            {
              path: 'mock-rules',
              name: 'mock-rules',
              component: () => import('@/views/mock/MockRuleList.vue'),
            },
            {
              path: 'system/api-contract-assets',
              name: 'system-api-contract-assets',
              component: () => import('@/views/system/ApiContractAssetsView.vue'),
            },
          ],
        },
        {
          path: 'mobile-special/workbench',
          name: 'mobile-special-workbench',
          component: () => import('@/views/workbench/AppWorkbenchView.vue'),
          meta: {
            menuTitleKey: 'menu.capabilities.app',
            descriptionKey: 'navigation.placeholder.description.app',
          },
        },
        {
          path: '',
          component: () => import('@/layouts/TabbedHubLayout.vue'),
          meta: { hubId: 'ui' },
          children: [
            {
              path: 'ui-workbench',
              name: 'ui-workbench',
              component: () => import('@/views/workbench/UiWorkbenchView.vue'),
              meta: {
                menuTitleKey: 'menu.capabilities.ui',
                descriptionKey: 'navigation.placeholder.description.ui',
              },
            },
            {
              path: 'system/web-assets',
              name: 'system-web-assets',
              component: () => import('@/views/system/WebAssetsView.vue'),
            },
          ],
        },
        {
          path: 'performance-workbench',
          name: 'performance-workbench',
          component: () => import('@/views/workbench/PerformanceWorkbenchView.vue'),
          meta: {
            menuTitleKey: 'menu.capabilities.performance',
            descriptionKey: 'navigation.placeholder.description.performance',
          },
        },
        {
          path: '',
          component: () => import('@/layouts/TabbedHubLayout.vue'),
          meta: { hubId: 'ai-center' },
          children: [
            {
              path: 'ai-workbench',
              name: 'ai-workbench',
              component: () => import('@/views/workbench/AIWorkbenchView.vue'),
              meta: {
                menuTitleKey: 'menu.capabilities.ai',
                descriptionKey: 'navigation.placeholder.description.ai',
              },
            },
            {
              path: 'system/ai-healing-stats',
              name: 'system-ai-healing-stats',
              component: () => import('@/views/system/AIHealingStatsView.vue'),
              meta: { requireAdmin: true, roles: ADMIN_ONLY },
            },
            {
              path: 'system/healing-examples',
              name: 'system-healing-examples',
              component: () => import('@/views/system/HealingExamplesView.vue'),
              meta: { requireAdmin: true, roles: ADMIN_ONLY },
            },
          ],
        },
        {
          path: 'bugs',
          name: 'bugs',
          component: () => import('@/views/defect/DefectListView.vue'),
          meta: {
            menuTitleKey: 'menu.assets.bugs',
            descriptionKey: 'navigation.placeholder.description.bugs',
          },
        },
        {
          path: '',
          component: () => import('@/layouts/TabbedHubLayout.vue'),
          meta: { hubId: 'reports' },
          children: [
            {
              path: 'reports',
              name: 'reports',
              component: () => import('@/views/report/ReportCenterView.vue'),
              meta: {
                menuTitleKey: 'menu.assets.reports',
                descriptionKey: 'navigation.placeholder.description.reports',
              },
            },
            {
              path: 'cloud-sync',
              name: 'cloud-sync',
              component: () => import('@/views/cloud-sync/CloudSyncDashboard.vue'),
            },
          ],
        },
        {
          path: '',
          component: () => import('@/layouts/TabbedHubLayout.vue'),
          meta: { hubId: 'cases' },
          children: [
            {
              path: 'cases',
              name: 'cases',
              component: () => import('@/views/case/CaseList.vue'),
            },
            {
              path: 'projects/:projectId/cases',
              name: 'project-cases',
              component: () => import('@/views/case/CaseList.vue'),
            },
            {
              path: 'case-reviews',
              name: 'case-reviews',
              component: () => import('@/views/case/CaseReviewWorkbench.vue'),
              meta: {
                menuTitleKey: 'menu.assets.reviews',
                descriptionKey: 'navigation.placeholder.description.reviews',
              },
            },
          ],
        },
        {
          path: 'hermes',
          name: 'hermes',
          component: () => import('@/views/intelligence/HermesAssistantView.vue'),
          meta: {
            menuTitleKey: 'menu.intelligence.hermes',
            descriptionKey: 'navigation.placeholder.description.hermes',
          },
        },
        {
          path: 'ai-chat',
          name: 'ai-chat',
          redirect: '/hermes',
        },
        {
          path: '',
          component: () => import('@/layouts/TabbedHubLayout.vue'),
          meta: { hubId: 'requirements-knowledge' },
          children: [
            {
              path: 'requirements',
              name: 'requirements',
              component: () => import('@/views/intelligence/RequirementTraceabilityView.vue'),
              meta: {
                menuTitleKey: 'menu.intelligence.requirements',
                descriptionKey: 'navigation.placeholder.description.requirements',
              },
            },
            {
              path: 'knowledge',
              name: 'knowledge',
              component: () => import('@/views/intelligence/KnowledgeHubView.vue'),
              meta: {
                menuTitleKey: 'menu.intelligence.knowledge',
                descriptionKey: 'navigation.placeholder.description.knowledge',
              },
            },
          ],
        },
        {
          path: '',
          component: () => import('@/layouts/TabbedHubLayout.vue'),
          meta: { hubId: 'remote-ops' },
          children: [
            {
              path: 'system/toolbox',
              name: 'system-toolbox',
              component: () => import('@/views/system/RemoteToolboxView.vue'),
              meta: {
                roles: ENGINEER_ONLY,
                menuTitleKey: 'menu.system_center.toolbox',
                descriptionKey: 'navigation.placeholder.description.toolbox',
              },
            },
            {
              path: 'system/remote-nodes',
              name: 'system-remote-nodes',
              component: () => import('@/views/system/RemoteNodesView.vue'),
              meta: { requireAdmin: true, roles: ADMIN_ONLY, menuTitleKey: 'menu.system_center.remote_nodes' },
            },
          ],
        },
        {
          path: '',
          component: () => import('@/layouts/TabbedHubLayout.vue'),
          meta: { hubId: 'project-settings' },
          children: [
            {
              path: 'system/environments',
              name: 'environments',
              component: () => import('@/views/system/EnvironmentList.vue'),
            },
            {
              path: 'system/global-variables',
              name: 'global-variables',
              component: () => import('@/views/system/GlobalVariableLibrary.vue'),
            },
            {
              path: 'system/notifications',
              name: 'notifications',
              component: () => import('@/views/system/NotificationList.vue'),
              meta: { roles: ENGINEER_ONLY },
            },
          ],
        },
        {
          path: '',
          component: () => import('@/layouts/TabbedHubLayout.vue'),
          meta: { hubId: 'platform-settings' },
          children: [
            {
              path: 'system/config',
              name: 'system-config',
              component: () => import('@/views/system/ConfigurationCenterView.vue'),
              meta: {
                roles: ENGINEER_ONLY,
                menuTitleKey: 'menu.system_center.config',
                descriptionKey: 'navigation.placeholder.description.config',
              },
            },
            {
              path: 'system/storage',
              name: 'system-storage',
              component: () => import('@/views/system/StorageManagementView.vue'),
              meta: { roles: ENGINEER_ONLY },
            },
            {
              path: 'system/startup-config',
              name: 'system-startup-config',
              component: () => import('@/views/system/StartupConfigView.vue'),
              meta: { requireAdmin: true, roles: ADMIN_ONLY },
            },
          ],
        },
        {
          path: 'system/bug-trackers',
          name: 'bug-trackers',
          component: () => import('@/views/system/BugTrackerList.vue'),
          meta: { roles: ENGINEER_ONLY },
        },
        {
          path: 'system/ai-llm-configs',
          name: 'system-ai-llm-configs',
          component: () => import('@/views/system/AILLMConfigList.vue'),
          meta: { roles: ADMIN_ONLY },
        },
        {
          path: '',
          component: () => import('@/layouts/TabbedHubLayout.vue'),
          meta: { hubId: 'governance' },
          children: [
            {
              path: 'system/users',
              name: 'system-users',
              component: () => import('@/views/system/UserManagementView.vue'),
              meta: { requireAdmin: true, roles: ADMIN_ONLY },
            },
            {
              path: 'system/audit-logs',
              name: 'audit-logs',
              component: () => import('@/views/audit/AuditLogList.vue'),
              meta: { requireAdmin: true, roles: ADMIN_ONLY },
            },
            {
              path: 'system/run-retention',
              name: 'system-run-retention',
              component: () => import('@/views/system/RunRetentionView.vue'),
              meta: { requireAdmin: true, roles: ADMIN_ONLY },
            },
            {
              path: 'system/dashboard-alerts',
              name: 'system-dashboard-alerts',
              component: () => import('@/views/system/DashboardAlertRulesView.vue'),
              meta: { requireAdmin: true, roles: ADMIN_ONLY },
            },
            {
              path: 'system/security',
              name: 'system-security',
              component: () => import('@/views/system/SecurityGovernanceView.vue'),
              meta: { requireAdmin: true, roles: ADMIN_ONLY },
            },
          ],
        },
        {
          path: 'projects',
          name: 'projects',
          component: () => import('@/views/project/ProjectList.vue'),
        },
        {
          path: 'projects/:projectId/overview',
          name: 'project-overview',
          component: () => import('@/views/project/ProjectOverviewView.vue'),
        },
        {
          path: 'account',
          name: 'account-settings',
          component: () => import('@/views/account/AccountSettingsView.vue'),
        },
        {
          path: 'cases/:caseId',
          name: 'case-detail',
          component: () => import('@/views/case/CaseDetail.vue'),
        },
        {
          path: 'runs',
          name: 'runs',
          component: () => import('@/views/run/RunList.vue'),
        },
        {
          path: 'runs/:runId',
          name: 'run-detail',
          component: () => import('@/views/run/RunDetail.vue'),
        },
        {
          path: 'devices',
          name: 'devices',
          component: () => import('@/views/device/DeviceList.vue'),
          meta: { roles: ENGINEER_ONLY, menuTitleKey: 'device.title' },
        },
        {
          path: 'apks',
          name: 'apks',
          component: () => import('@/views/apk/ApkList.vue'),
          meta: { menuTitleKey: 'apk.title' },
        },
        {
          path: 'ios-assets',
          name: 'ios-assets',
          component: () => import('@/views/device/IosAssetsView.vue'),
          meta: { menuTitleKey: 'menu.ios_assets' },
        },
        {
          path: '',
          component: () => import('@/layouts/TabbedHubLayout.vue'),
          meta: { hubId: 'plans-suites' },
          children: [
            {
              path: 'suites',
              name: 'suites',
              component: () => import('@/views/suite/SuiteList.vue'),
              meta: {
                menuTitleKey: 'menu.assets.suites',
                descriptionKey: 'navigation.placeholder.description.suites',
              },
            },
            {
              path: 'plans',
              name: 'plans',
              component: () => import('@/views/plan/PlanList.vue'),
            },
          ],
        },
        {
          path: 'mobile-special/tasks',
          name: 'mobile-special-tasks',
          component: () => import('@/views/mobile-special/SpecialTaskListView.vue'),
        },
        {
          path: 'mobile-special/reports',
          name: 'mobile-special-reports',
          component: () => import('@/views/mobile-special/ReportCenterView.vue'),
        },
        {
          path: 'mobile-special/reports/:runId',
          name: 'mobile-special-report-detail',
          component: () => import('@/views/mobile-special/ReportDetailView.vue'),
        },
        {
          path: 'system/datasets',
          name: 'system-datasets',
          component: () => import('@/views/system/DatasetLibrary.vue'),
        },
        {
          path: 'system/performance',
          name: 'system-performance',
          component: () => import('@/views/system/PerformanceCenterView.vue'),
        },
      ],
    },
    { path: '/:pathMatch(.*)*', redirect: '/' },
  ],
})

// 路由守卫：未登录跳转 /login；按路由声明校验角色
router.beforeEach(async (to) => {
  const auth = useAuthStore()
  if (!to.meta.public && !auth.initialized) {
    await auth.restoreSession()
  }
  if (!to.meta.public && !auth.user) {
    return { name: 'login', query: { redirect: to.fullPath } }
  }
  // 已登录但用户信息未加载（如刷新页面）时恢复，避免管理员菜单与权限校验失效
  const allowedRoles = (to.meta.roles ?? (to.meta.requireAdmin ? ADMIN_ONLY : undefined)) as UserRole[] | undefined
  if (!hasAnyRole(auth.user?.role, allowedRoles)) {
    message.error('无权限访问该页面')
    return { name: 'dashboard' }
  }
})

export default router
