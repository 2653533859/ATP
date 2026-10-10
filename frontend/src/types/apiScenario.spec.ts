import { describe, expect, it } from 'vitest'
import {
  parseStepFromCase,
  detectVariableReferences,
  detectVariableExtractions,
  type ApiScenarioStep,
} from './apiScenario'

describe('apiScenario helpers', () => {
  it('parses step from case item correctly', () => {
    const rawCase = {
      name: '用户登录',
      config: {
        method: 'POST',
        url: '/api/v1/auth/login',
        headers: { 'Content-Type': 'application/json' },
        body_type: 'json',
        body: '{"username":"admin"}',
        assertions: [{ target: 'status_code', operator: 'eq', expected: '200' }],
        extractions: [{ variable: 'token', type: 'jsonpath', expression: '$.token' }],
      },
    }

    const step = parseStepFromCase(rawCase)
    expect(step.name).toBe('用户登录')
    expect(step.method).toBe('POST')
    expect(step.url).toBe('/api/v1/auth/login')
    expect(step.headers?.['Content-Type']).toBe('application/json')
    expect(step.extractions?.length).toBe(1)
    expect(step.extractions?.[0].variable).toBe('token')
    expect(step.assertions?.length).toBe(1)
  })

  it('detects variable references across url, headers, and body', () => {
    const step: ApiScenarioStep = {
      name: '创建订单',
      method: 'POST',
      url: '/api/v1/orders/{{order_type}}',
      headers: {
        Authorization: 'Bearer {{token}}',
      },
      params: {
        tenant: '{{tenantId}}',
      },
      body: JSON.stringify({ userId: '{{user_id}}', amount: 100 }),
    }

    const refs = detectVariableReferences(step)
    expect(refs).toContain('order_type')
    expect(refs).toContain('token')
    expect(refs).toContain('tenantId')
    expect(refs).toContain('user_id')
    expect(refs.length).toBe(4)
  })

  it('detects variable extractions correctly', () => {
    const step: ApiScenarioStep = {
      name: '登录',
      method: 'POST',
      extractions: [
        { variable: 'token', type: 'jsonpath', expression: '$.token' },
        { variable: 'refresh_token', type: 'jsonpath', expression: '$.refresh' },
      ],
    }

    const extractions = detectVariableExtractions(step)
    expect(extractions).toEqual(['token', 'refresh_token'])
  })
})
