import { describe, expect, it } from 'vitest'
import {
  applyPerformanceLoadTemplate,
  buildPerformanceOptions,
  createDefaultPerformanceScenario,
  generatePerformanceK6Script,
} from './performanceScriptGenerator'

describe('performanceScriptGenerator', () => {
  it('creates a smoke profile with safe defaults', () => {
    const scenario = createDefaultPerformanceScenario()
    expect(scenario.vus).toBe(1)
    expect(scenario.duration).toBe('30s')
    expect(scenario.authType).toBe('none')
  })

  it('applies stage-based load templates without losing request settings', () => {
    const scenario = createDefaultPerformanceScenario()
    scenario.url = 'https://api.example.test/items'
    const stress = applyPerformanceLoadTemplate(scenario, 'stress')

    expect(stress.url).toBe('https://api.example.test/items')
    expect(stress.stages.length).toBe(3)
    expect(stress.stages[1]).toEqual({ target: 50, duration: '2m' })
  })

  it('builds k6 options and interpolated request script', () => {
    const scenario = createDefaultPerformanceScenario('load')
    scenario.url = 'https://example.test/items'
    scenario.method = 'POST'
    scenario.headers = { 'X-Trace': '{{TRACE_ID}}' }
    scenario.bodyType = 'json'
    scenario.body = '{"name":"{{NAME}}"}'
    scenario.authType = 'bearer'
    scenario.bearerTokenKey = 'API_TOKEN'

    const options = buildPerformanceOptions(scenario)
    const script = generatePerformanceK6Script(scenario)

    expect(options).toMatchObject({ vus: 10, duration: '2m' })
    expect((options.thresholds as Record<string, string[]>).http_req_failed).toEqual(['rate<0.01'])
    expect(script).toContain("http.request(request.method")
    expect(script).toContain('__ENV[request.bearerTokenKey]')
    expect(script).toContain('__ENV.ATP_DATASET_JSON')
    expect(script).toContain('row?.[key]')
    expect(script).toContain('{{TRACE_ID}}')
  })

  it('generates sequential user behavior steps with think time', () => {
    const scenario = createDefaultPerformanceScenario()
    scenario.steps = [
      {
        name: 'Login',
        method: 'POST',
        url: 'https://example.test/login',
        headers: {},
        params: {},
        bodyType: 'json',
        body: '{"user":"{{USER}}"}',
        authType: 'none',
        bearerTokenKey: 'API_TOKEN',
        basicUsernameKey: 'API_USERNAME',
        basicPasswordKey: 'API_PASSWORD',
        expectedStatus: 200,
        bodyContains: '',
        thinkTime: '1s',
      },
      {
        name: 'List',
        method: 'GET',
        url: 'https://example.test/items',
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
        thinkTime: '0s',
      },
    ]

    const script = generatePerformanceK6Script(scenario)

    expect(script).toContain('scenario.steps')
    expect(script).toContain('sleepSeconds(request.thinkTime)')
    expect(script).toContain('Login')
  })
})
