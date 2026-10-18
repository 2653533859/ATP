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
          path: 'api-workbench',
          name: 'api-workbench',
          component: () => import('@/views/workbench/ApiWorkbenchView.vue'),
          meta: {
            menuTitleKey: 'menu.capabilities.api',
            descriptionKey: 'navigation.placeholder.description.api',
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
          },
        },
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
          path: 'performance-workbench',
          name: 'performance-workbench',
          component: () => import('@/views/workbench/PerformanceWorkbenchView.vue'),
          meta: {
            menuTitleKey: 'menu.capabilities.performance',
            descriptionKey: 'navigation.placeholder.description.performance',
          },
        },
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
          path: 'workbench/hybrid-orchestrator',
          name: 'hybrid-workflow-workbench',
          component: () => import('@/views/workbench/HybridWorkflowWorkbenchView.vue'),
          meta: {
            roles: ENGINEER_ONLY,
          },
        },
        {
          path: 'workbench/ai-exploration',
          name: 'ai-autonomous-exploration-workbench',
          component: () => import('@/views/workbench/AiAutonomousExplorationView.vue'),
          meta: {
            roles: ENGINEER_ONLY,
          },
        },
        {
          path: 'workbench/cross-platform-parity',
          name: 'cross-platform-parity-workbench',
          component: () => import('@/views/workbench/CrossPlatformParityWorkbenchView.vue'),
          meta: {
            roles: ENGINEER_ONLY,
          },
        },
        {
          path: 'workbench/fleet-scheduler',
          name: 'fleet-scheduler-workbench',
          component: () => import('@/views/workbench/FleetSchedulerWorkbenchView.vue'),
          meta: {
            roles: ENGINEER_ONLY,
          },
        },
        {
          path: 'workbench/test-self-healing',
          name: 'test-self-healing-workbench',
          component: () => import('@/views/workbench/TestSelfHealingWorkbenchView.vue'),
          meta: {
            roles: ENGINEER_ONLY,
          },
        },
        {
          path: 'workbench/traffic-replay',
          name: 'traffic-replay-workbench',
          component: () => import('@/views/workbench/TrafficReplayWorkbenchView.vue'),
          meta: {
            roles: ENGINEER_ONLY,
          },
        },
        {
          path: 'workbench/precision-regression',
          name: 'precision-regression-workbench',
          component: () => import('@/views/workbench/PrecisionRegressionWorkbenchView.vue'),
          meta: {
            roles: ENGINEER_ONLY,
          },
        },
        {
          path: 'workbench/chaos-engineering',
          name: 'chaos-engineering-workbench',
          component: () => import('@/views/workbench/ChaosEngineeringWorkbenchView.vue'),
          meta: {
            roles: ENGINEER_ONLY,
          },
        },
        {
          path: 'workbench/code-coverage',
          name: 'code-coverage-workbench',
          component: () => import('@/views/workbench/CodeCoverageWorkbenchView.vue'),
          meta: {
            roles: ENGINEER_ONLY,
          },
        },
        {
          path: 'workbench/defect-intelligence',
          name: 'defect-intelligence-workbench',
          component: () => import('@/views/workbench/DefectIntelligenceWorkbenchView.vue'),
          meta: {
            roles: ENGINEER_ONLY,
          },
        },
        {
          path: 'workbench/canary-verification',
          name: 'canary-verification-workbench',
          component: () => import('@/views/workbench/CanaryVerificationWorkbenchView.vue'),
          meta: {
            roles: ENGINEER_ONLY,
          },
        },
        {
          path: 'workbench/stress-testing',
          name: 'stress-testing-workbench',
          component: () => import('@/views/workbench/StressTestingWorkbenchView.vue'),
          meta: {
            roles: ENGINEER_ONLY,
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
          },
        },
        {
          path: 'reports/dora',
          name: 'dora-metrics-compass',
          component: () => import('@/views/report/DoraMetricsCompassView.vue'),
          meta: { roles: ENGINEER_ONLY },
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
          component: () => import('@/views/intelligence/AiChatView.vue'),
          meta: {
            menuTitleKey: 'menu.intelligence.ai_chat',
            descriptionKey: 'navigation.placeholder.description.ai_chat',
          },
        },
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
          path: 'devices/ios-center',
          name: 'ios-device-center',
          component: () => import('@/views/device/IosDeviceCenterView.vue'),
          meta: { roles: ENGINEER_ONLY },
        },
        {
          path: 'apks',
          name: 'apks',
          component: () => import('@/views/apk/ApkList.vue'),
          meta: { roles: ENGINEER_ONLY },
        },
        {
          path: 'ios-assets',
          name: 'ios-assets',
          component: () => import('@/views/device/IosAssetsView.vue'),
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
          path: 'system/audit-chain',
          name: 'system-audit-chain',
          component: () => import('@/views/audit/AuditTamperEvidentChainView.vue'),
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
          path: 'diagnostics/web-vitals',
          name: 'web-vitals-diagnostics',
          component: () => import('@/views/diagnostics/WebVitalsDiagnosticsView.vue'),
          meta: { roles: ENGINEER_ONLY },
        },
        {
          path: 'quality/code-to-test-graph',
          name: 'code-to-test-dependency-graph',
          component: () => import('@/views/quality/CodeToTestDependencyGraphView.vue'),
          meta: { roles: ENGINEER_ONLY },
        },
        {
          path: 'quality/change-risk',
          name: 'change-risk-radar-dashboard',
          component: () => import('@/views/quality/ChangeRiskRadarDashboard.vue'),
          meta: { roles: ENGINEER_ONLY },
        },
        {
          path: 'quality/mutation-score',
          name: 'mutation-score-heatmap-report',
          component: () => import('@/views/quality/MutationScoreHeatmapReportView.vue'),
          meta: { roles: ENGINEER_ONLY },
        },
        {
          path: 'quality/ci-pipeline-checkpoint',
          name: 'ci-pipeline-checkpoint-monitor',
          component: () => import('@/views/quality/CiPipelineCheckpointMonitorView.vue'),
          meta: { roles: ENGINEER_ONLY },
        },
        {
          path: 'quality/golden-baselines',
          name: 'golden-response-baseline-dashboard',
          component: () => import('@/views/quality/GoldenResponseBaselineDashboardView.vue'),
          meta: { roles: ENGINEER_ONLY },
        },
        {
          path: 'quality/contract-drift-topology',
          name: 'contract-drift-impact-topology',
          component: () => import('@/views/quality/ContractDriftImpactTopologyView.vue'),
          meta: { roles: ENGINEER_ONLY },
        },
        {
          path: 'quality/traffic-guard-pipeline',
          name: 'traffic-guard-pipeline-monitor',
          component: () => import('@/views/quality/TrafficGuardPipelineMonitorView.vue'),
          meta: { roles: ENGINEER_ONLY },
        },
        {
          path: 'quality/trace-flamegraph',
          name: 'critical-path-flamegraph-dashboard',
          component: () => import('@/views/quality/CriticalPathFlamegraphDashboardView.vue'),
          meta: { roles: ENGINEER_ONLY },
        },
        {
          path: 'quality/cross-db-audit',
          name: 'cross-db-consistency-audit-dashboard',
          component: () => import('@/views/quality/CrossDbConsistencyAuditDashboardView.vue'),
          meta: { roles: ENGINEER_ONLY },
        },
        {
          path: 'quality/self-healing-pipeline',
          name: 'self-healing-audit-patch-pipeline',
          component: () => import('@/views/quality/SelfHealingAuditPatchPipelineView.vue'),
          meta: { roles: ENGINEER_ONLY },
        },
        {
          path: 'quality/ephemeral-env',
          name: 'ephemeral-test-env-dashboard',
          component: () => import('@/views/quality/EphemeralTestEnvDashboardView.vue'),
          meta: { roles: ENGINEER_ONLY },
        },
        {
          path: 'quality/db-schema-drift',
          name: 'db-schema-drift-audit-dashboard',
          component: () => import('@/views/quality/DbSchemaDriftAuditDashboardView.vue'),
          meta: { roles: ENGINEER_ONLY },
        },
        {
          path: 'quality/audit-report',
          name: 'comprehensive-quality-audit-report',
          component: () => import('@/views/quality/ComprehensiveAuditReportView.vue'),
          meta: { roles: ENGINEER_ONLY },
        },
        {
          path: 'quality/visual-regression',
          name: 'visual-regression-audit-dashboard',
          component: () => import('@/views/quality/VisualRegressionAuditDashboardView.vue'),
          meta: { roles: ENGINEER_ONLY },
        },
        {
          path: 'quality/color-blindness',
          name: 'color-blindness-audit-dashboard',
          component: () => import('@/views/quality/ColorBlindnessAuditDashboardView.vue'),
          meta: { roles: ENGINEER_ONLY },
        },
        {
          path: 'quality/web-vitals',
          name: 'client-web-vitals-experience-dashboard',
          component: () => import('@/views/quality/ClientWebVitalsExperienceDashboardView.vue'),
          meta: { roles: ENGINEER_ONLY },
        },
        {
          path: 'quality/shadow-isolation',
          name: 'full-link-shadow-isolation-dashboard',
          component: () => import('@/views/quality/FullLinkShadowIsolationDashboardView.vue'),
          meta: { roles: ENGINEER_ONLY },
        },
        {
          path: 'quality/cell-failover',
          name: 'cell-failover-resilience-dashboard',
          component: () => import('@/views/quality/CellFailoverResilienceDashboardView.vue'),
          meta: { roles: ENGINEER_ONLY },
        },
        {
          path: 'quality/full-link-drill',
          name: 'full-link-stress-drill-summary-dashboard',
          component: () => import('@/views/quality/FullLinkStressDrillSummaryDashboardView.vue'),
          meta: { roles: ENGINEER_ONLY },
        },
        {
          path: 'quality/trace-alignment',
          name: 'distributed-trace-alignment-dashboard',
          component: () => import('@/views/quality/DistributedTraceAlignmentDashboardView.vue'),
          meta: { roles: ENGINEER_ONLY },
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
        {
          path: 'system/finops',
          name: 'system-finops',
          component: () => import('@/views/system/FinOpsCostCenterView.vue'),
          meta: { roles: ENGINEER_ONLY },
        },
        {
          path: 'quality/metrics',
          name: 'quality-metrics',
          component: () => import('@/views/quality/QualityMetricsDashboardView.vue'),
        },
        {
          path: 'system/mesh-resilience',
          name: 'system-mesh-resilience',
          component: () => import('@/views/system/MeshResilienceReportView.vue'),
          meta: { roles: ENGINEER_ONLY },
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
