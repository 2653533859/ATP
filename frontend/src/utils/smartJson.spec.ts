import { describe, expect, it } from 'vitest'

import {
  jsonTextToRows,
  rowsToJsonText,
  validateJsonText,
} from './smartJson'

describe('smartJson helpers', () => {
  it('validates objects, arrays, primitives, invalid JSON, and template placeholders', () => {
    expect(validateJsonText('')).toEqual({ valid: true, empty: true, canUseVisual: true })
    expect(validateJsonText('{"a": 1}')).toEqual({ valid: true, empty: false, canUseVisual: true })
    expect(validateJsonText('[1, 2]')).toMatchObject({ valid: true, canUseVisual: false, reason: 'array' })
    expect(validateJsonText('"hello"')).toMatchObject({ valid: true, canUseVisual: false, reason: 'primitive' })
    expect(validateJsonText('{bad')).toMatchObject({ valid: false, canUseVisual: false, reason: 'invalid' })

    expect(validateJsonText('{"id": {{user_id}}}', false).valid).toBe(false)
    expect(validateJsonText('{"id": {{user_id}}}', true)).toEqual({
      valid: true,
      empty: false,
      canUseVisual: false,
      reason: 'template',
    })
  })

  it('converts plain JSON objects to typed rows and back cleanly', () => {
    const source = JSON.stringify({
      name: 'alice',
      age: 30,
      active: true,
      note: null,
      meta: { role: 'qa' },
      tags: ['smoke'],
    })

    const rows = jsonTextToRows(source)
    expect(rows).toEqual([
      { key: 'name', type: 'string', value: 'alice' },
      { key: 'age', type: 'number', value: '30' },
      { key: 'active', type: 'boolean', value: 'true' },
      { key: 'note', type: 'null', value: '' },
      { key: 'meta', type: 'json', value: '{"role":"qa"}' },
      { key: 'tags', type: 'json', value: '["smoke"]' },
    ])

    const regenerated = JSON.parse(rowsToJsonText(rows!))
    expect(regenerated).toEqual({
      name: 'alice',
      age: 30,
      active: true,
      note: null,
      meta: { role: 'qa' },
      tags: ['smoke'],
    })
  })

  it('ignores blank keys and gracefully handles incomplete values when serializing', () => {
    expect(rowsToJsonText([{ key: '  ', type: 'string', value: 'ignored' }])).toBe('{}')
    expect(
      JSON.parse(
        rowsToJsonText([
          { key: 'flag', type: 'boolean', value: 'false' },
          { key: 'tpl', type: 'number', value: '{{count}}' },
          { key: 'nested', type: 'json', value: '{bad' },
        ]),
      ),
    ).toEqual({
      flag: false,
      tpl: '{{count}}',
      nested: '{bad',
    })
  })
})
