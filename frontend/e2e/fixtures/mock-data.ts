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
  access_token: 'e2e-access-token',
  refresh_token: 'e2e-refresh-token',
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
