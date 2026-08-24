/**
 * 集中存放 E2E 用例 mock JSON。
 * 注意：字段名保持与后端 schema 一致，避免前端反序列化失败。
 */
export const adminUser = {
  id: 1,
  username: 'admin',
  email: 'admin@example.com',
  is_active: true,
  role: 'admin',
  language: 'zh-CN',
}

export const adminTokens = {
  authenticated: true,
  token_type: 'bearer',
}

export const projects = [
  {
    id: 1,
    name: 'E2E 测试项目',
    project_code: 'E2E',
    description: 'Playwright fixture project',
    owner_id: 1,
    ai_llm_config_id: null,
    run_retention_days_override: null,
    created_at: '2026-05-21T00:00:00Z',
    updated_at: '2026-05-21T00:00:00Z',
  },
]

export const modules = [
  {
    id: 10,
    name: '根模块',
    module_code: 'root',
    project_id: 1,
    parent_id: null,
    sort_order: 0,
    created_at: '2026-05-21T00:00:00Z',
    children: [],
  },
]

export const cases = [
  {
    id: 100,
    name: 'GET /health 烟测',
    description: null,
    case_code: 'C-100',
    summary: '简单健康检查',
    case_type: 'api',
    status: 'active',
    priority: 'P1',
    case_level: 'smoke',
    review_status: 'approved',
    automation_status: 'auto',
    tags: ['smoke'],
    module_id: 10,
    creator_id: 1,
    owner_id: 1,
    is_ready_for_execution: true,
    created_at: '2026-05-21T00:00:00Z',
    updated_at: '2026-05-21T00:00:00Z',
  },
]

export const environments = [
  {
    id: 501,
    name: 'E2E 环境',
    description: 'Mocked E2E environment',
    project_id: 1,
    created_at: '2026-05-21T00:00:00Z',
    updated_at: '2026-05-21T00:00:00Z',
  },
]

export const workbenchOverview = {
  generated_at: '2026-05-21T10:00:00Z',
  project_id: null,
  counts: {
    pending_reviews: 0,
    failed_runs: 0,
    overdue_plans: 0,
    device_anomalies: 0,
    active_tasks: 0,
    total_todos: 0,
    returned_tasks: 0,
  },
  todos: [],
  tasks: [],
  has_more_todos: false,
  has_more_tasks: false,
}

export const suites = [
  {
    id: 200,
    name: 'E2E 冒烟套件',
    description: 'Suite for Playwright E2E',
    project_id: 1,
    status: 'active',
    creator_id: 1,
    case_ids: [{ case_id: 100, sort: 0 }],
    parameterization: null,
    config: {
      execution_mode: 'sequential',
      fail_strategy: 'continue',
      max_workers: 3,
      min_pass_rate: 0.8,
    },
    created_at: '2026-05-21T08:00:00Z',
    updated_at: '2026-05-21T08:00:00Z',
  },
]

export const triggeredSuiteRun = {
  id: 9201,
  suite_id: 200,
  triggered_by: 1,
  trace_id: 'e2e-suite-trace',
  status: 'pending',
  environment: null,
  duration_ms: null,
  error_message: null,
  result_summary: { total: 1, passed: 0, failed: 0, error: 0 },
  case_run_ids: [],
  created_at: '2026-05-21T10:10:00Z',
}

export const suiteRuns = [
  {
    ...triggeredSuiteRun,
    id: 9200,
    status: 'passed',
    duration_ms: 456,
    result_summary: { total: 1, passed: 1, failed: 0, error: 0, execution_mode: 'sequential', fail_strategy: 'continue' },
    case_run_ids: [{ case_id: 100, case_name: 'GET /health 烟测', run_id: 9000, status: 'passed' }],
  },
]

export const plans = [
  {
    id: 300,
    name: 'E2E 每日计划',
    description: 'Plan for Playwright E2E',
    project_id: 1,
    status: 'active',
    creator_id: 1,
    suite_ids: [{ suite_id: 200, sort: 0 }],
    schedule_type: 'manual',
    cron_expression: null,
    webhook_secret: 'e2e-webhook-secret',
    is_enabled: true,
    auto_create_bugs: true,
    env_id: null,
    config: {
      execution_mode: 'sequential',
      fail_strategy: 'continue',
      max_workers: 3,
      min_pass_rate: 0.8,
    },
    last_run_at: null,
    next_run_at: null,
    created_at: '2026-05-21T08:30:00Z',
    updated_at: '2026-05-21T08:30:00Z',
  },
]

export const triggeredPlanRun = {
  id: 9301,
  plan_id: 300,
  triggered_by: 1,
  trace_id: 'e2e-plan-trace',
  trigger_type: 'manual',
  status: 'pending',
  duration_ms: null,
  error_message: null,
  suite_run_ids: [],
  result_summary: { total: 1, passed: 0, failed: 0, error: 0 },
  created_at: '2026-05-21T10:20:00Z',
}

export const planRuns = [
  {
    ...triggeredPlanRun,
    id: 9300,
    status: 'passed',
    duration_ms: 789,
    suite_run_ids: [{ suite_id: 200, suite_name: 'E2E 冒烟套件', suite_run_id: 9200, status: 'passed' }],
    result_summary: {
      total: 1,
      passed: 1,
      failed: 0,
      error: 0,
      auto_bugs: [],
    },
  },
]

export const caseDetail = {
  ...cases[0],
  preconditions: [],
  postconditions: [],
  submitted_at: null,
  reviewed_at: null,
  reviewed_by: null,
  review_comment: null,
  steps: [
    {
      id: 1,
      step_order: 1,
      name: '主请求',
      config: { method: 'GET', url: 'http://example.com/health', assertions: [{ type: 'status_code', expected: 200 }] },
    },
  ],
  config: {},
}

export const triggeredRun = {
  id: 9001,
  case_id: 100,
  triggered_by: 1,
  trace_id: 'e2e-trace-id',
  status: 'pending',
  environment: null,
  duration_ms: null,
  error_message: null,
  result_summary: {},
  created_at: '2026-05-21T10:00:00Z',
  steps: [],
}

export const completedRun = {
  ...triggeredRun,
  id: 9000,
  status: 'passed',
  duration_ms: 123,
  result_summary: { total: 1, passed: 1, failed: 0 },
  steps: [
    {
      id: 1,
      step_index: 0,
      name: '主请求',
      status: 'passed',
      duration_ms: 88,
      request_data: { method: 'GET', url: 'http://example.com/health' },
      response_data: { status_code: 200, body: { ok: true } },
      error_message: null,
      screenshot_url: null,
      healing_suggestion: null,
      healing_status: null,
      healing_at: null,
    },
  ],
}

export const overviewStats = {
  total_cases: 12,
  total_runs: 99,
  pass_rate: 0.875,
  recent_runs_7d: 21,
}

export const passRateTrend = Array.from({ length: 7 }, (_, i) => ({
  date: `2026-05-${15 + i}`,
  total: 10 + i,
  passed: 8 + i,
  rate: 0.8,
}))

export const durationTrend = passRateTrend.map((d) => ({
  date: d.date,
  avg_duration_ms: 500 + 10 * d.total,
  max_duration_ms: 1500,
  run_count: d.total,
}))
