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
    expect(script).toContain("http.request(scenario.method")
    expect(script).toContain('__ENV[scenario.bearerTokenKey]')
    expect(script).toContain('{{TRACE_ID}}')
  })
})
