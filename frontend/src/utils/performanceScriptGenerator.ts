export type PerformanceLoadTemplate = 'smoke' | 'load' | 'stress' | 'spike' | 'soak'
export type PerformanceRequestBodyType = 'none' | 'json' | 'text'

export interface PerformanceStage {
  duration: string
  target: number
}

export interface PerformanceScenarioStep {
  name: string
  method: string
  url: string
  headers: Record<string, string>
  params: Record<string, string>
  bodyType: PerformanceRequestBodyType
  body: string
  authType: 'none' | 'bearer' | 'basic'
  bearerTokenKey: string
  basicUsernameKey: string
  basicPasswordKey: string
  expectedStatus: number
  bodyContains: string
  thinkTime: string
}

export interface PerformanceScenario {
  loadTemplate: PerformanceLoadTemplate
  method: string
  url: string
  headers: Record<string, string>
  params: Record<string, string>
  bodyType: PerformanceRequestBodyType
  body: string
  authType: 'none' | 'bearer' | 'basic'
  bearerTokenKey: string
  basicUsernameKey: string
  basicPasswordKey: string
  expectedStatus: number
  bodyContains: string
  vus: number
  duration: string
  stages: PerformanceStage[]
  p95ThresholdMs: number
  errorRateThresholdPercent: number
  steps?: PerformanceScenarioStep[]
}

interface LoadProfile {
  vus: number
  duration: string
  stages: PerformanceStage[]
}

const LOAD_PROFILES: Record<PerformanceLoadTemplate, LoadProfile> = {
  smoke: { vus: 1, duration: '30s', stages: [] },
  load: { vus: 10, duration: '2m', stages: [] },
  stress: {
    vus: 10,
    duration: '30s',
    stages: [
      { target: 10, duration: '30s' },
      { target: 50, duration: '2m' },
      { target: 0, duration: '30s' },
    ],
  },
  spike: {
    vus: 5,
    duration: '10s',
    stages: [
      { target: 5, duration: '10s' },
      { target: 50, duration: '10s' },
      { target: 50, duration: '1m' },
      { target: 0, duration: '10s' },
    ],
  },
  soak: { vus: 10, duration: '10m', stages: [] },
}

export function createDefaultPerformanceScenario(
  loadTemplate: PerformanceLoadTemplate = 'smoke',
): PerformanceScenario {
  const profile = LOAD_PROFILES[loadTemplate]
  return {
    loadTemplate,
    method: 'GET',
    url: 'https://example.test',
    headers: {},
    params: {},
    bodyType: 'none',
    body: '',
    authType: 'none',
    bearerTokenKey: 'API_TOKEN',
    basicUsernameKey: 'API_USERNAME',
    basicPasswordKey: 'API_PASSWORD',
    expectedStatus: 200,
    bodyContains: '',
    vus: profile.vus,
    duration: profile.duration,
    stages: profile.stages.map((stage) => ({ ...stage })),
    p95ThresholdMs: 500,
    errorRateThresholdPercent: 1,
    steps: [],
  }
}

export function createDefaultPerformanceStep(scenario: Partial<PerformanceScenario> = {}): PerformanceScenarioStep {
  return {
    name: 'Request',
    method: scenario.method || 'GET',
    url: scenario.url || 'https://example.test',
    headers: { ...(scenario.headers || {}) },
    params: { ...(scenario.params || {}) },
    bodyType: scenario.bodyType || 'none',
    body: scenario.body || '',
    authType: scenario.authType || 'none',
    bearerTokenKey: scenario.bearerTokenKey || 'API_TOKEN',
    basicUsernameKey: scenario.basicUsernameKey || 'API_USERNAME',
    basicPasswordKey: scenario.basicPasswordKey || 'API_PASSWORD',
    expectedStatus: scenario.expectedStatus || 200,
    bodyContains: scenario.bodyContains || '',
    thinkTime: '0s',
  }
}

export function applyPerformanceLoadTemplate(
  scenario: PerformanceScenario,
  loadTemplate: PerformanceLoadTemplate,
): PerformanceScenario {
  const profile = LOAD_PROFILES[loadTemplate]
  return {
    ...scenario,
    loadTemplate,
    vus: profile.vus,
    duration: profile.duration,
    stages: profile.stages.map((stage) => ({ ...stage })),
    steps: (scenario.steps || []).map((step) => ({
      ...step,
      headers: { ...step.headers },
      params: { ...step.params },
    })),
  }
}

export function buildPerformanceOptions(scenario: PerformanceScenario): Record<string, unknown> {
  const thresholds: Record<string, string[]> = {}
  if (scenario.p95ThresholdMs > 0) {
    thresholds.http_req_duration = ['p(95)<' + scenario.p95ThresholdMs]
  }
  if (scenario.errorRateThresholdPercent >= 0) {
    thresholds.http_req_failed = ['rate<' + scenario.errorRateThresholdPercent / 100]
  }

  const options: Record<string, unknown> = {
    env: { TARGET_URL: scenario.url },
    thresholds,
    atp_scenario: scenario,
  }
  if (scenario.stages.length) {
    options.stages = scenario.stages
  } else {
    options.vus = scenario.vus
    options.duration = scenario.duration
  }
  return options
}

function scriptScenario(scenario: PerformanceScenario) {
  if (scenario.steps?.length) {
    return { steps: scenario.steps }
  }
  return {
    method: scenario.method,
    url: scenario.url,
    headers: scenario.headers,
    params: scenario.params,
    bodyType: scenario.bodyType,
    body: scenario.body,
    authType: scenario.authType,
    bearerTokenKey: scenario.bearerTokenKey,
    basicUsernameKey: scenario.basicUsernameKey,
    basicPasswordKey: scenario.basicPasswordKey,
    expectedStatus: scenario.expectedStatus,
    bodyContains: scenario.bodyContains,
  }
}

export function generatePerformanceK6Script(scenario: PerformanceScenario): string {
  const scenarioOptions = buildPerformanceOptions(scenario)
  const k6Options = { ...scenarioOptions }
  delete k6Options.env
  delete k6Options.atp_scenario
  const defaultOptions = JSON.stringify(k6Options)
  const encodedScenario = JSON.stringify(scriptScenario(scenario))
  const lines = [
    "import http from 'k6/http';",
    "import encoding from 'k6/encoding';",
    "import { check, sleep } from 'k6';",
    '',
    'const defaultOptions = ' + defaultOptions + ';',
    "export const options = JSON.parse(__ENV.ATP_K6_OPTIONS || JSON.stringify(defaultOptions));",
    'const scenario = ' + encodedScenario + ';',
    '',
    'function datasetRow() {',
    "  try {",
    "    const rows = JSON.parse(__ENV.ATP_DATASET_JSON || '[]');",
    "    if (!Array.isArray(rows) || rows.length === 0) return {};",
    '    return rows[__ITER % rows.length] || {};',
    "  } catch (_) { return {}; }",
    '}',
    '',
    'function resolveValue(value, row) {',
    "  if (typeof value !== 'string') return value;",
    "  return value.replace(/\\{\\{([A-Za-z_][A-Za-z0-9_]*)\\}\\}/g, (_, key) => row?.[key] ?? __ENV[key] ?? ('{{' + key + '}}'));",
    '}',
    '',
    'function resolveObject(value, row) {',
    '  if (Array.isArray(value)) return value.map((item) => resolveObject(item, row));',
    "  if (value && typeof value === 'object') {",
    "    return Object.fromEntries(Object.entries(value).map(([key, item]) => [key, resolveObject(item, row)]));",
    '  }',
    '  return resolveValue(value, row);',
    '}',
    '',
    'function targetUrl(request, row) {',
    '  if (request.url === scenario.url && (row?.TARGET_URL ?? __ENV.TARGET_URL)) {',
    '    return row?.TARGET_URL ?? __ENV.TARGET_URL;',
    '  }',
    '  return resolveValue(request.url, row);',
    '}',
    '',
    'function requestUrl(request, row) {',
    '  const base = targetUrl(request, row);',
    '  const query = Object.entries(resolveObject(request.params || {}, row))',
    "    .map(([key, value]) => encodeURIComponent(key) + '=' + encodeURIComponent(String(value)))",
    "    .join('&');",
    '  if (!query) return base;',
    "  return base + (base.includes('?') ? '&' : '?') + query;",
    '}',
    '',
    'function requestBody(request, row) {',
    "  if (request.bodyType === 'none' || !request.body) return undefined;",
    "  if (request.bodyType === 'json') {",
    "    try { return JSON.stringify(resolveObject(JSON.parse(request.body), row)); } catch (_) { return resolveValue(request.body, row); }",
    '  }',
    '  return resolveValue(request.body, row);',
    '}',
    '',
    'function sleepSeconds(value) {',
    "  if (typeof value === 'number') return value;",
    "  const match = String(value || '').match(/^\\s*(\\d+(?:\\.\\d+)?)\\s*(ms|s|m)?\\s*$/i);",
    "  if (!match) return 0;",
    "  const multiplier = { ms: 0.001, s: 1, m: 60 }[(match[2] || 's').toLowerCase()] || 1;",
    '  return Number(match[1]) * multiplier;',
    '}',
    '',
    'function executeRequest(request, row) {',
    '  const headers = resolveObject(request.headers || {}, row);',
    "  if (request.authType === 'bearer' && __ENV[request.bearerTokenKey]) {",
    "    headers.Authorization = 'Bearer ' + __ENV[request.bearerTokenKey];",
    '  }',
    "  if (request.authType === 'basic' && __ENV[request.basicUsernameKey]) {",
    '    const username = __ENV[request.basicUsernameKey];',
    "    const password = __ENV[request.basicPasswordKey] || '';",
    "    headers.Authorization = 'Basic ' + encoding.b64encode(username + ':' + password);",
    '  }',
    '  const response = http.request(request.method, requestUrl(request, row), requestBody(request, row), { headers });',
    '  const checks = {};',
    "  checks['status is ' + request.expectedStatus] = (res) => res.status === request.expectedStatus;",
    "  if (request.bodyContains) checks.body_contains = (res) => String(res.body || '').includes(resolveValue(request.bodyContains, row));",
    '  check(response, checks);',
    '}',
    '',
    'export default function () {',
    '  const row = datasetRow();',
    '  const requests = Array.isArray(scenario.steps) && scenario.steps.length ? scenario.steps : [scenario];',
    '  requests.forEach((request, index) => {',
    '    executeRequest(request, row);',
    '    if (index < requests.length - 1) sleep(sleepSeconds(request.thinkTime));',
    '  });',
    '}',
  ]
  return lines.join('\n') + '\n'
}
