import { describe, expect, it } from 'vitest'

import {
  coerceCellValue,
  deriveDatasetColumns,
  parseDatasetRowsText,
  parseDelimitedTable,
} from './datasetTable'

describe('datasetTable helpers', () => {
  it('parses row arrays and derives ordered columns from schema and row keys', () => {
    const parsed = parseDatasetRowsText('[{"username":"alice","age":28,"extra":"x"}]')
    expect(parsed.valid).toBe(true)
    expect(parsed.rows).toEqual([{ username: 'alice', age: 28, extra: 'x' }])

    expect(
      deriveDatasetColumns(parsed.rows, [{ name: 'username' }, { name: 'role' }]),
    ).toEqual(['username', 'role', 'age', 'extra'])

    expect(parseDatasetRowsText('{bad').valid).toBe(false)
    expect(parseDatasetRowsText('{"a": 1}').valid).toBe(false)
  })

  it('coerces typed values and imports tab-separated or CSV pasted tables', () => {
    expect(coerceCellValue('42', 'integer')).toBe(42)
    expect(coerceCellValue('3.14', 'number')).toBe(3.14)
    expect(coerceCellValue('true', 'boolean')).toBe(true)
    expect(coerceCellValue('{"k":1}', 'json')).toEqual({ k: 1 })

    const tsv = 'username\tage\tactive\nalice\t25\ttrue\nbob\t30\tfalse'
    expect(
      parseDelimitedTable(tsv, [
        { name: 'username', type: 'string' },
        { name: 'age', type: 'integer' },
        { name: 'active', type: 'boolean' },
      ]),
    ).toEqual([
      { username: 'alice', age: 25, active: true },
      { username: 'bob', age: 30, active: false },
    ])

    const csv = 'name,note\n"Alice, A.",ok\nBob,done'
    expect(parseDelimitedTable(csv)).toEqual([
      { name: 'Alice, A.', note: 'ok' },
      { name: 'Bob', note: 'done' },
    ])
  })
})
