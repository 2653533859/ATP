import { describe, expect, it } from 'vitest'

import { parseFixtureActionsText, serializeFixtureActions } from './fixtureActions'

describe('fixtureActions helpers', () => {
  it('parses and serializes set_variable, delete_variable, and request actions preserving extra fields', () => {
    const source = JSON.stringify([
      { action: 'set_variable', variable: 'token', value: 'demo', note: 'keep-me' },
      { action: 'request', method: 'POST', url: 'https://api.example/init' },
      { action: 'delete_variable', variable: 'token' },
    ])
    const parsed = parseFixtureActionsText(source)
    expect(parsed.valid).toBe(true)
    expect(parsed.rows).toHaveLength(3)
    expect(JSON.parse(serializeFixtureActions(parsed.rows))).toEqual([
      { action: 'set_variable', variable: 'token', value: 'demo', note: 'keep-me' },
      { action: 'request', method: 'POST', url: 'https://api.example/init' },
      { action: 'delete_variable', variable: 'token' },
    ])
  })

  it('rejects malformed JSON or unsupported action types safely', () => {
    expect(parseFixtureActionsText('{bad').valid).toBe(false)
    expect(parseFixtureActionsText('{"action":"set_variable"}').valid).toBe(false)
    expect(parseFixtureActionsText('[{"action":"assert"}]').valid).toBe(false)
  })
})
