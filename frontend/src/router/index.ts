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
          path: 'projects',
          name: 'projects',
          component: () => import('@/views/project/ProjectList.vue'),
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
      ],
    },
    { path: '/:pathMatch(.*)*', redirect: '/' },
  ],
})

// 路由守卫：未登录跳转 /login；按路由声明校验角色
router.beforeEach(async (to) => {
  const auth = useAuthStore()
  if (!to.meta.public && !auth.token) {
    return { name: 'login', query: { redirect: to.fullPath } }
  }
  // 已登录但用户信息未加载（如刷新页面）时恢复，避免管理员菜单与权限校验失效
  if (auth.token && !auth.user) {
    await auth.fetchMe()
  }
  const allowedRoles = (to.meta.roles ?? (to.meta.requireAdmin ? ADMIN_ONLY : undefined)) as UserRole[] | undefined
  if (!hasAnyRole(auth.user?.role, allowedRoles)) {
    message.error('无权限访问该页面')
    return { name: 'dashboard' }
  }
})

export default router
