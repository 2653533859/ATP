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
            existingLinks: [
              { path: '/cases', labelKey: 'menu.cases' },
              { path: '/runs', labelKey: 'menu.runs' },
              { path: '/plans', labelKey: 'menu.plans' },
            ],
          },
        },
        {
          path: 'tasks',
          name: 'tasks',
          component: () => import('@/views/workbench/TaskCenterView.vue'),
          meta: {
            menuTitleKey: 'menu.workbench.tasks',
            descriptionKey: 'navigation.placeholder.description.tasks',
            existingLinks: [{ path: '/runs', labelKey: 'menu.runs' }],
          },
        },
        {
          path: 'api-workbench',
          name: 'api-workbench',
          component: () => import('@/views/workbench/ApiWorkbenchView.vue'),
          meta: {
            menuTitleKey: 'menu.capabilities.api',
            descriptionKey: 'navigation.placeholder.description.api',
            existingLinks: [
              { path: '/cases', labelKey: 'menu.cases' },
              { path: '/system/api-contract-assets', labelKey: 'menu.system.api_contract_assets' },
              { path: '/mock-rules', labelKey: 'menu.mock_rules' },
            ],
          },
        },
        {
          path: 'mobile-special/workbench',
          name: 'mobile-special-workbench',
          component: () => import('@/views/workbench/AppWorkbenchView.vue'),
          meta: {
            roles: ENGINEER_ONLY,
            menuTitleKey: 'menu.capabilities.app',
            descriptionKey: 'navigation.placeholder.description.app',
            existingLinks: [
              { path: '/devices', labelKey: 'menu.devices' },
              { path: '/apks', labelKey: 'menu.apks' },
              { path: '/mobile-special/tasks', labelKey: 'menu.mobile_special.tasks' },
            ],
          },
        },
        {
          path: 'ui-workbench',
          name: 'ui-workbench',
          component: () => import('@/views/workbench/UiWorkbenchView.vue'),
          meta: {
            menuTitleKey: 'menu.capabilities.ui',
            descriptionKey: 'navigation.placeholder.description.ui',
            existingLinks: [
              { path: '/system/web-assets', labelKey: 'menu.system.web_assets' },
              { path: '/cases', labelKey: 'menu.cases' },
            ],
          },
        },
        {
          path: 'performance-workbench',
          name: 'performance-workbench',
          component: () => import('@/views/workbench/PerformanceWorkbenchView.vue'),
          meta: {
            menuTitleKey: 'menu.capabilities.performance',
            descriptionKey: 'navigation.placeholder.description.performance',
            existingLinks: [
              { path: '/system/performance', labelKey: 'menu.system.performance' },
              { path: '/runs', labelKey: 'menu.runs' },
            ],
          },
        },
        {
          path: 'ai-workbench',
          name: 'ai-workbench',
          component: () => import('@/views/workbench/AIWorkbenchView.vue'),
          meta: {
            menuTitleKey: 'menu.capabilities.ai',
            descriptionKey: 'navigation.placeholder.description.ai',
            existingLinks: [
              { path: '/cases', labelKey: 'menu.cases' },
              { path: '/mock-rules', labelKey: 'menu.mock_rules' },
            ],
          },
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
          path: 'reports',
          name: 'reports',
          component: () => import('@/views/report/ReportCenterView.vue'),
          meta: {
            menuTitleKey: 'menu.assets.reports',
            descriptionKey: 'navigation.placeholder.description.reports',
            existingLinks: [
              { path: '/runs', labelKey: 'menu.runs' },
              { path: '/mobile-special/reports', labelKey: 'menu.mobile_special.reports' },
            ],
          },
        },
        {
          path: 'case-reviews',
          name: 'case-reviews',
          component: () => import('@/views/case/CaseReviewWorkbench.vue'),
          meta: {
            menuTitleKey: 'menu.assets.reviews',
            descriptionKey: 'navigation.placeholder.description.reviews',
            existingLinks: [{ path: '/cases?review_status=pending', labelKey: 'menu.cases' }],
          },
        },
        {
          path: 'hermes',
          name: 'hermes',
          component: () => import('@/views/intelligence/HermesAssistantView.vue'),
          meta: {
            menuTitleKey: 'menu.intelligence.hermes',
            descriptionKey: 'navigation.placeholder.description.hermes',
            existingLinks: [{ path: '/runs', labelKey: 'menu.runs' }],
          },
        },
        {
          path: 'requirements',
          name: 'requirements',
          component: () => import('@/views/intelligence/RequirementTraceabilityView.vue'),
          meta: {
            menuTitleKey: 'menu.intelligence.requirements',
            descriptionKey: 'navigation.placeholder.description.requirements',
            existingLinks: [{ path: '/cases', labelKey: 'menu.cases' }],
          },
        },
        {
          path: 'knowledge',
          name: 'knowledge',
          component: () => import('@/views/intelligence/KnowledgeHubView.vue'),
          meta: {
            menuTitleKey: 'menu.intelligence.knowledge',
            descriptionKey: 'navigation.placeholder.description.knowledge',
            existingLinks: [
              { path: '/bugs', labelKey: 'menu.bugs' },
              { path: '/requirements', labelKey: 'menu.intelligence.requirements' },
              { path: '/runs', labelKey: 'menu.runs' },
            ],
          },
        },
        {
          path: 'system/toolbox',
          name: 'system-toolbox',
          component: () => import('@/views/system/RemoteToolboxView.vue'),
          meta: {
            roles: ENGINEER_ONLY,
            menuTitleKey: 'menu.system_center.toolbox',
            descriptionKey: 'navigation.placeholder.description.toolbox',
            existingLinks: [
              { path: '/devices', labelKey: 'menu.devices' },
              { path: '/system/performance', labelKey: 'menu.system.performance' },
            ],
          },
        },
        {
          path: 'system/config',
          name: 'system-config',
          component: () => import('@/views/system/ConfigurationCenterView.vue'),
          meta: {
            roles: ENGINEER_ONLY,
            menuTitleKey: 'menu.system_center.config',
            descriptionKey: 'navigation.placeholder.description.config',
            existingLinks: [
              { path: '/system/environments', labelKey: 'menu.system.environments' },
              { path: '/system/global-variables', labelKey: 'menu.system.global_variables' },
            ],
          },
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
          path: 'system/environments',
          name: 'environments',
          component: () => import('@/views/system/EnvironmentList.vue'),
        },
        {
          path: 'system/startup-config',
          name: 'system-startup-config',
          component: () => import('@/views/system/StartupConfigView.vue'),
          meta: { requireAdmin: true, roles: ADMIN_ONLY },
        },
        {
          path: 'system/notifications',
          name: 'notifications',
          component: () => import('@/views/system/NotificationList.vue'),
          meta: { roles: ENGINEER_ONLY },
        },
        {
          path: 'system/bug-trackers',
          name: 'bug-trackers',
          component: () => import('@/views/system/BugTrackerList.vue'),
          meta: { roles: ENGINEER_ONLY },
        },
        {
          path: 'devices',
          name: 'devices',
          component: () => import('@/views/device/DeviceList.vue'),
          meta: { roles: ENGINEER_ONLY },
        },
        {
          path: 'apks',
          name: 'apks',
          component: () => import('@/views/apk/ApkList.vue'),
          meta: { roles: ENGINEER_ONLY },
        },
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
        {
          path: 'mock-rules',
          name: 'mock-rules',
          component: () => import('@/views/mock/MockRuleList.vue'),
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
          path: 'system/storage',
          name: 'system-storage',
          component: () => import('@/views/system/StorageManagementView.vue'),
          meta: { roles: ENGINEER_ONLY },
        },
        {
          path: 'system/global-variables',
          name: 'global-variables',
          component: () => import('@/views/system/GlobalVariableLibrary.vue'),
        },
        {
          path: 'system/audit-logs',
          name: 'audit-logs',
          component: () => import('@/views/audit/AuditLogList.vue'),
          meta: { requireAdmin: true, roles: ADMIN_ONLY },
        },
        {
          path: 'system/users',
          name: 'system-users',
          component: () => import('@/views/system/UserManagementView.vue'),
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
          path: 'system/ai-llm-configs',
          name: 'system-ai-llm-configs',
          component: () => import('@/views/system/AILLMConfigList.vue'),
          meta: { roles: ADMIN_ONLY },
        },
        {
          path: 'system/healing-examples',
          name: 'system-healing-examples',
          component: () => import('@/views/system/HealingExamplesView.vue'),
          meta: { requireAdmin: true, roles: ADMIN_ONLY },
        },
        {
          path: 'system/ai-healing-stats',
          name: 'system-ai-healing-stats',
          component: () => import('@/views/system/AIHealingStatsView.vue'),
          meta: { requireAdmin: true, roles: ADMIN_ONLY },
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
        {
          path: 'system/web-assets',
          name: 'system-web-assets',
          component: () => import('@/views/system/WebAssetsView.vue'),
        },
        {
          path: 'system/api-contract-assets',
          name: 'system-api-contract-assets',
          component: () => import('@/views/system/ApiContractAssetsView.vue'),
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
