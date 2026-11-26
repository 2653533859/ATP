import { isNavItemVisible, type HubVisibilityContext, type VisibilityRule } from './hubConfig'

export interface QuickSearchItem extends VisibilityRule {
  path: string
  titleKey: string
  groupKey: string
  parentKey?: string
  keywords: readonly string[]
  pinned?: boolean
}

export type QuickSearchContext = HubVisibilityContext

export const QUICK_SEARCH_RECENT_KEY = 'atp_quick_search_recent_paths'
const MAX_RECENT_ITEMS = 5

export const QUICK_SEARCH_ITEMS: readonly QuickSearchItem[] = [
  // 工作台
  {
    path: '/dashboard',
    titleKey: 'menu.workbench.home',
    groupKey: 'menu.groups.workbench',
    keywords: ['home', 'dashboard', '看板', '统计', '首页', '概览'],
    pinned: true,
  },
  {
    path: '/workbench/todos',
    titleKey: 'menu.workbench.todos',
    groupKey: 'menu.groups.workbench',
    keywords: ['todo', 'worklist', '待办', '我的待办', '审批'],
    serverOnly: true,
  },
  {
    path: '/projects',
    titleKey: 'menu.workbench.projects',
    groupKey: 'menu.groups.workbench',
    keywords: ['project', 'projects', '项目', '项目中心', '成员'],
  },
  {
    path: '/tasks',
    titleKey: 'menu.workbench.tasks',
    groupKey: 'menu.groups.workbench',
    keywords: ['task', 'run', 'execution', '任务', '任务中心', '执行记录'],
    serverOnly: true,
  },
  {
    path: '/cloud-sync',
    titleKey: 'menu.workbench.cloud_sync',
    groupKey: 'menu.groups.test_assets_new',
    parentKey: 'menu.assets.reports',
    keywords: ['cloud', 'sync', '云端', '云端结果', '同步汇总'],
    localOrAdmin: true,
  },

  // 测试能力
  {
    path: '/api-workbench',
    titleKey: 'menu.capabilities.api',
    groupKey: 'menu.groups.test_capabilities',
    keywords: ['api', 'http', 'grpc', 'graphql', 'websocket', '接口', '调试', '场景'],
    pinned: true,
  },
  {
    path: '/mock-rules',
    titleKey: 'menu.mock_rules',
    groupKey: 'menu.groups.test_capabilities',
    parentKey: 'menu.capabilities.api',
    keywords: ['mock', 'stub', '挡板', '模拟接口'],
  },
  {
    path: '/system/api-contract-assets',
    titleKey: 'menu.system.api_contract_assets',
    groupKey: 'menu.groups.test_capabilities',
    parentKey: 'menu.capabilities.api',
    keywords: ['contract', 'openapi', 'swagger', 'schema', '契约', 'API 契约'],
  },
  {
    path: '/mobile-special/workbench',
    titleKey: 'menu.capabilities.app',
    groupKey: 'menu.groups.test_capabilities',
    keywords: ['app', 'android', 'ios', 'mobile', 'adb', 'apk', 'device', '设备', '专项', 'APP'],
  },
  {
    path: '/ui-workbench',
    titleKey: 'menu.capabilities.ui',
    groupKey: 'menu.groups.test_capabilities',
    keywords: ['ui', 'web', 'playwright', 'browser', 'recorder', '录制', '浏览器'],
  },
  {
    path: '/system/web-assets',
    titleKey: 'menu.system.web_assets',
    groupKey: 'menu.groups.test_capabilities',
    parentKey: 'menu.capabilities.ui',
    keywords: ['web', 'pom', 'page object', 'locator', 'baseline', '元素', '视觉基线', '页面对象'],
  },
  {
    path: '/performance-workbench',
    titleKey: 'menu.capabilities.performance',
    groupKey: 'menu.groups.test_capabilities',
    keywords: ['performance', 'load', 'stress', '压测', '性能', '并发', '基线'],
    feature: 'performance',
  },

  // 测试资产
  {
    path: '/cases',
    titleKey: 'menu.assets.cases',
    groupKey: 'menu.groups.test_assets_new',
    keywords: ['case', 'cases', 'test case', '用例', '测试用例', '用例库'],
    pinned: true,
  },
  {
    path: '/case-reviews',
    titleKey: 'menu.assets.reviews',
    groupKey: 'menu.groups.test_assets_new',
    parentKey: 'menu.assets.cases',
    keywords: ['review', 'approval', '评审', '用例评审'],
  },
  {
    path: '/plans',
    titleKey: 'menu.assets.plans',
    groupKey: 'menu.groups.test_assets_new',
    parentKey: 'menu.assets.plans_and_suites',
    keywords: ['plan', 'schedule', '计划', '测试计划', '定时'],
    feature: 'plans',
  },
  {
    path: '/suites',
    titleKey: 'menu.assets.suites',
    groupKey: 'menu.groups.test_assets_new',
    parentKey: 'menu.assets.plans_and_suites',
    keywords: ['suite', 'collection', '套件', '测试套件'],
    feature: 'suites',
  },
  {
    path: '/system/datasets',
    titleKey: 'menu.system.datasets',
    groupKey: 'menu.groups.test_assets_new',
    keywords: ['dataset', 'csv', 'data', '数据集', '参数化'],
  },
  {
    path: '/bugs',
    titleKey: 'menu.assets.bugs',
    groupKey: 'menu.groups.test_assets_new',
    keywords: ['bug', 'defect', 'issue', '缺陷', '故障'],
    feature: 'defects',
  },
  {
    path: '/reports',
    titleKey: 'menu.assets.reports',
    groupKey: 'menu.groups.test_assets_new',
    keywords: ['report', 'quality', 'trend', '报告', '质量报告', '测试报告'],
  },

  // 智能中枢
  {
    path: '/hermes',
    titleKey: 'menu.intelligence.hermes',
    groupKey: 'menu.groups.intelligence_center',
    keywords: ['hermes', 'assistant', 'copilot', 'chat', '智能助手', '对话'],
    feature: 'hermes',
    pinned: true,
  },
  {
    path: '/ai-workbench',
    titleKey: 'menu.capabilities.ai',
    groupKey: 'menu.groups.intelligence_center',
    parentKey: 'menu.intelligence.ai_hub',
    keywords: ['ai', 'generate', '智能测试', 'AI 生成', '诊断'],
    feature: 'ai_generation',
  },
  {
    path: '/system/ai-healing-stats',
    titleKey: 'menu.system.ai_healing_stats',
    groupKey: 'menu.groups.intelligence_center',
    parentKey: 'menu.intelligence.ai_hub',
    keywords: ['healing', 'stats', 'report', '自愈报表', '采纳率'],
    roles: ['admin'],
  },
  {
    path: '/system/healing-examples',
    titleKey: 'menu.system.ai_healing_examples',
    groupKey: 'menu.groups.intelligence_center',
    parentKey: 'menu.intelligence.ai_hub',
    keywords: ['healing', 'examples', '自愈示例', '经验库'],
    roles: ['admin'],
  },
  {
    path: '/requirements',
    titleKey: 'menu.intelligence.requirements',
    groupKey: 'menu.groups.intelligence_center',
    parentKey: 'menu.intelligence.requirements_knowledge',
    keywords: ['requirement', 'traceability', '需求', '需求追踪', '覆盖率'],
  },
  {
    path: '/knowledge',
    titleKey: 'menu.intelligence.knowledge',
    groupKey: 'menu.groups.intelligence_center',
    parentKey: 'menu.intelligence.requirements_knowledge',
    keywords: ['knowledge', 'doc', 'wiki', 'runbook', '知识', '知识库', '知识中枢'],
  },

  // 系统 -> 配置与集成
  {
    path: '/system/config',
    titleKey: 'menu.system_center.config',
    groupKey: 'menu.groups.system_center',
    parentKey: 'hub.settings.group_platform',
    keywords: ['config', 'configuration', 'snapshot', 'rollback', '配置中心', '版本', '回滚'],
    roles: ['admin', 'engineer'],
  },
  {
    path: '/system/environments',
    titleKey: 'menu.system.environments',
    groupKey: 'menu.groups.system_center',
    parentKey: 'hub.settings.group_project',
    keywords: ['env', 'environment', 'base url', '环境', '环境管理'],
  },
  {
    path: '/system/global-variables',
    titleKey: 'menu.system.global_variables',
    groupKey: 'menu.groups.system_center',
    parentKey: 'hub.settings.group_project',
    keywords: ['variable', 'global', 'secret', '变量', '全局变量'],
  },
  {
    path: '/system/notifications',
    titleKey: 'menu.system.notifications',
    groupKey: 'menu.groups.system_center',
    parentKey: 'hub.settings.group_project',
    keywords: ['notification', 'webhook', 'smtp', 'dingtalk', 'wecom', '通知', '告警通知'],
    roles: ['admin', 'engineer'],
    serverOnly: true,
  },
  {
    path: '/system/bug-trackers',
    titleKey: 'menu.system.bug_trackers',
    groupKey: 'menu.groups.test_assets_new',
    keywords: ['tracker', 'jira', 'zentao', 'gitlab', 'github', '缺陷跟踪', '缺陷追踪', '外部缺陷'],
    roles: ['admin', 'engineer'],
    serverOnly: true,
  },
  {
    path: '/system/ai-llm-configs',
    titleKey: 'menu.system.ai_llm_configs',
    groupKey: 'menu.groups.system_center',
    keywords: ['llm', 'model', 'openai', 'gemini', 'ollama', '模型', '大模型', 'AI 模型'],
    roles: ['admin'],
  },
  {
    path: '/system/storage',
    titleKey: 'menu.system.storage',
    groupKey: 'menu.groups.system_center',
    parentKey: 'hub.settings.group_platform',
    keywords: ['storage', 'minio', 'bucket', '存储', '对象存储'],
    roles: ['admin', 'engineer'],
    serverOnly: true,
  },
  {
    path: '/system/startup-config',
    titleKey: 'menu.system.startup_config',
    groupKey: 'menu.groups.system_center',
    parentKey: 'hub.settings.group_platform',
    keywords: ['startup', 'boot', 'worker', '启动配置', '开关'],
    roles: ['admin'],
  },

  // 系统 -> 平台治理
  {
    path: '/system/users',
    titleKey: 'menu.system.users',
    groupKey: 'menu.groups.system_center',
    parentKey: 'menu.system_center.governance',
    keywords: ['user', 'role', 'rbac', 'password', '用户', '用户管理', '角色'],
    roles: ['admin'],
    serverOnly: true,
  },
  {
    path: '/system/audit-logs',
    titleKey: 'menu.system.audit_logs',
    groupKey: 'menu.groups.system_center',
    parentKey: 'menu.system_center.governance',
    keywords: ['audit', 'log', '审计', '操作日志'],
    roles: ['admin'],
  },
  {
    path: '/system/run-retention',
    titleKey: 'menu.system.run_retention',
    groupKey: 'menu.groups.system_center',
    parentKey: 'menu.system_center.governance',
    keywords: ['retention', 'cleanup', 'purge', '清理', '保留策略', '执行记录清理'],
    roles: ['admin'],
    serverOnly: true,
  },
  {
    path: '/system/dashboard-alerts',
    titleKey: 'menu.system.dashboard_alerts',
    groupKey: 'menu.groups.system_center',
    parentKey: 'menu.system_center.governance',
    keywords: ['alert', 'rule', 'threshold', '告警', '看板告警'],
    roles: ['admin'],
    serverOnly: true,
  },

  // 系统 -> 远程运维
  {
    path: '/system/toolbox',
    titleKey: 'menu.system_center.toolbox',
    groupKey: 'menu.groups.system_center',
    parentKey: 'menu.system_center.remote_ops',
    keywords: ['toolbox', 'health', 'diagnostic', '工具箱', '远程工具箱', '依赖检查'],
    roles: ['admin', 'engineer'],
    serverOnly: true,
  },
  {
    path: '/system/remote-nodes',
    titleKey: 'menu.system_center.remote_nodes',
    groupKey: 'menu.groups.system_center',
    parentKey: 'menu.system_center.remote_ops',
    keywords: ['node', 'remote', 'grant', '节点', '远程节点', '授权'],
    roles: ['admin'],
    serverOnly: true,
  },
]

const KNOWN_PATH_SET = new Set(QUICK_SEARCH_ITEMS.map((item) => item.path))

export const isQuickSearchItemVisible = isNavItemVisible

export function getVisibleQuickSearchItems(ctx: QuickSearchContext): QuickSearchItem[] {
  return QUICK_SEARCH_ITEMS.filter((item) => isQuickSearchItemVisible(item, ctx))
}

export function filterQuickSearchItems(
  query: string,
  translate: (key: string) => string,
  ctx: QuickSearchContext,
): QuickSearchItem[] {
  const visible = getVisibleQuickSearchItems(ctx)
  const normalized = query.trim().toLowerCase()
  if (!normalized) {
    return visible.filter((item) => item.pinned)
  }

  const scored = visible
    .map((item) => {
      const title = translate(item.titleKey).toLowerCase()
      const group = translate(item.groupKey).toLowerCase()
      const parent = item.parentKey ? translate(item.parentKey).toLowerCase() : ''
      const pathLower = item.path.toLowerCase()
      const keywords = item.keywords.map((kw) => kw.toLowerCase())

      let score = 0
      if (title === normalized) score = 100
      else if (title.startsWith(normalized)) score = 85
      else if (title.includes(normalized)) score = 70
      else if (keywords.some((kw) => kw === normalized)) score = 65
      else if (keywords.some((kw) => kw.startsWith(normalized))) score = 55
      else if (keywords.some((kw) => kw.includes(normalized))) score = 45
      else if (parent.includes(normalized) || group.includes(normalized)) score = 30
      else if (pathLower.includes(normalized)) score = 20

      return { item, score }
    })
    .filter((entry) => entry.score > 0)

  scored.sort((a, b) => b.score - a.score)
  return scored.map((entry) => entry.item)
}

export function readRecentQuickSearchPaths(): string[] {
  try {
    const raw = window.localStorage.getItem(QUICK_SEARCH_RECENT_KEY)
    if (!raw) return []
    const parsed = JSON.parse(raw)
    if (!Array.isArray(parsed)) return []
    return parsed.filter((item): item is string => typeof item === 'string' && KNOWN_PATH_SET.has(item))
  } catch {
    return []
  }
}

export function recordRecentQuickSearchPath(path: string): string[] {
  if (!KNOWN_PATH_SET.has(path)) return readRecentQuickSearchPaths()
  const next = [path, ...readRecentQuickSearchPaths().filter((item) => item !== path)].slice(0, MAX_RECENT_ITEMS)
  try {
    window.localStorage.setItem(QUICK_SEARCH_RECENT_KEY, JSON.stringify(next))
  } catch {
    // 忽略隐私模式下 localStorage 不可写异常
  }
  return next
}
