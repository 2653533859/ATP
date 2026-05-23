import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

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
          path: 'system/notifications',
          name: 'notifications',
          component: () => import('@/views/system/NotificationList.vue'),
        },
        {
          path: 'system/bug-trackers',
          name: 'bug-trackers',
          component: () => import('@/views/system/BugTrackerList.vue'),
        },
        {
          path: 'devices',
          name: 'devices',
          component: () => import('@/views/device/DeviceList.vue'),
        },
        {
          path: 'apks',
          name: 'apks',
          component: () => import('@/views/apk/ApkList.vue'),
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
          meta: { requireAdmin: true },
        },
        {
          path: 'system/ai-llm-configs',
          name: 'system-ai-llm-configs',
          component: () => import('@/views/system/AILLMConfigList.vue'),
        },
        {
          path: 'system/datasets',
          name: 'system-datasets',
          component: () => import('@/views/system/DatasetLibrary.vue'),
        },
      ],
    },
    { path: '/:pathMatch(.*)*', redirect: '/' },
  ],
})

// 路由守卫：未登录跳转 /login
router.beforeEach((to) => {
  const auth = useAuthStore()
  if (!to.meta.public && !auth.token) {
    return { name: 'login', query: { redirect: to.fullPath } }
  }
})

export default router
