export type PerformanceLoadTemplate = 'smoke' | 'load' | 'stress' | 'spike' | 'soak'
export type PerformanceRequestBodyType = 'none' | 'json' | 'text'

export interface PerformanceStage {
  duration: string
  target: number
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
    "import { check } from 'k6';",
    '',
    'const defaultOptions = ' + defaultOptions + ';',
    "export const options = JSON.parse(__ENV.ATP_K6_OPTIONS || JSON.stringify(defaultOptions));",
    'const scenario = ' + encodedScenario + ';',
    '',
    'function resolveValue(value) {',
    "  if (typeof value !== 'string') return value;",
    "  return value.replace(/\\{\\{([A-Za-z_][A-Za-z0-9_]*)\\}\\}/g, (_, key) => __ENV[key] ?? ('{{' + key + '}}'));",
    '}',
    '',
    'function resolveObject(value) {',
    '  if (Array.isArray(value)) return value.map(resolveObject);',
    "  if (value && typeof value === 'object') {",
    "    return Object.fromEntries(Object.entries(value).map(([key, item]) => [key, resolveObject(item)]));",
    '  }',
    '  return resolveValue(value);',
    '}',
    '',
    'function targetUrl() {',
    '  return __ENV.TARGET_URL || resolveValue(scenario.url);',
    '}',
    '',
    'function requestUrl() {',
    '  const base = targetUrl();',
    '  const query = Object.entries(resolveObject(scenario.params || {}))',
    "    .map(([key, value]) => encodeURIComponent(key) + '=' + encodeURIComponent(String(value)))",
    "    .join('&');",
    '  if (!query) return base;',
    "  return base + (base.includes('?') ? '&' : '?') + query;",
    '}',
    '',
    'function requestBody() {',
    "  if (scenario.bodyType === 'none' || !scenario.body) return undefined;",
    "  if (scenario.bodyType === 'json') {",
    "    try { return JSON.stringify(resolveObject(JSON.parse(scenario.body))); } catch (_) { return resolveValue(scenario.body); }",
    '  }',
    '  return resolveValue(scenario.body);',
    '}',
    '',
    'export default function () {',
    '  const headers = resolveObject(scenario.headers || {});',
    "  if (scenario.authType === 'bearer' && __ENV[scenario.bearerTokenKey]) {",
    "    headers.Authorization = 'Bearer ' + __ENV[scenario.bearerTokenKey];",
    '  }',
    "  if (scenario.authType === 'basic' && __ENV[scenario.basicUsernameKey]) {",
    '    const username = __ENV[scenario.basicUsernameKey];',
    "    const password = __ENV[scenario.basicPasswordKey] || '';",
    "    headers.Authorization = 'Basic ' + encoding.b64encode(username + ':' + password);",
    '  }',
    '  const response = http.request(scenario.method, requestUrl(), requestBody(), { headers });',
    '  const checks = {};',
    "  checks['status is ' + scenario.expectedStatus] = (res) => res.status === scenario.expectedStatus;",
    "  if (scenario.bodyContains) checks.body_contains = (res) => String(res.body || '').includes(resolveValue(scenario.bodyContains));",
    '  check(response, checks);',
    '}',
  ]
  return lines.join('\n') + '\n'
}
