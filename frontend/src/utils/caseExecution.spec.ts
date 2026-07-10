import { describe, expect, it } from 'vitest'

import { buildEnvironmentOptions, buildRunDetailLocation, buildRunPayload } from './caseExecution'

describe('case execution helpers', () => {
  it('omits env_id when no execution environment is selected', () => {
    expect(buildRunPayload(null)).toEqual({})
    expect(buildRunPayload(undefined)).toEqual({})
  })

  it('builds environment options and an explicit run payload', () => {
    expect(buildEnvironmentOptions([
      { id: 3, name: 'Staging' },
      { id: 8, name: 'Production-like' },
    ])).toEqual([
      { label: 'Staging', value: 3 },
      { label: 'Production-like', value: 8 },
    ])
    expect(buildRunPayload(8)).toEqual({ env_id: 8 })
  })

  it('returns a named run-detail route location', () => {
    expect(buildRunDetailLocation(42)).toEqual({ name: 'run-detail', params: { runId: 42 } })
  })
})
