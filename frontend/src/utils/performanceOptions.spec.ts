import { describe, expect, it } from 'vitest'

import { mergePerformanceOptionsText, parsePerformanceOptionsText } from './performanceOptions'

describe('performanceOptions helpers', () => {
  it('parses executor options and thresholds while tracking preserved extra keys', () => {
    const parsed = parsePerformanceOptionsText(JSON.stringify({
      vus: 20,
      duration: '45s',
      iterations: 200,
      host: 'https://api.example.test',
      env: { TARGET_URL: 'https://api.example.test', TOKEN: 'abc' },
      thresholds: { max_p95_ms: 500, max_error_rate: 1.5, custom_gate: true },
      stages: [{ duration: '10s', target: 20 }],
    }))

    expect(parsed.valid).toBe(true)
    expect(parsed.state).toEqual({
      vus: 20,
      duration: '45s',
      spawn_rate: undefined,
      iterations: 200,
      host: 'https://api.example.test',
      max_p95_ms: 500,
      max_error_rate: 1.5,
      env: { TARGET_URL: 'https://api.example.test', TOKEN: 'abc' },
      extraKeys: ['stages'],
    })
  })

  it('merges changes per executor while preserving unknown fields', () => {
    const base = JSON.stringify({
      atp_scenario: { version: 1 },
      thresholds: { custom_gate: true },
    })

    const locustJson = JSON.parse(
      mergePerformanceOptionsText(
        base,
        {
          vus: 30,
          duration: '60s',
          spawn_rate: 5,
          host: 'https://locust.test',
          max_p95_ms: 300,
          env: { ENV: 'staging' },
          extraKeys: [],
        },
        'locust',
      ),
    )
    expect(locustJson).toEqual({
      atp_scenario: { version: 1 },
      users: 30,
      run_time: '60s',
      spawn_rate: 5,
      host: 'https://locust.test',
      env: { ENV: 'staging' },
      thresholds: { custom_gate: true, max_p95_ms: 300 },
    })

    const grpcJson = JSON.parse(
      mergePerformanceOptionsText(
        '{}',
        { vus: 10, duration: '30s', host: '', env: {}, extraKeys: [] },
        'grpc',
      ),
    )
    expect(grpcJson).toEqual({ concurrency: 10, duration_seconds: 30 })
  })

  it('rejects malformed JSON safely', () => {
    expect(parsePerformanceOptionsText('{bad').valid).toBe(false)
    expect(parsePerformanceOptionsText('[]').valid).toBe(false)
  })
})
