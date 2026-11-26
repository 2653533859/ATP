import { isPlainJsonObject } from './smartJson'

export interface DatasetSchemaHint {
  name: string
  type?: string
}

export function parseDatasetRowsText(text: string): {
  valid: boolean
  rows: Record<string, unknown>[]
} {
  const trimmed = text.trim()
  if (!trimmed) {
    return { valid: true, rows: [] }
  }
  try {
    const parsed = JSON.parse(trimmed)
    if (!Array.isArray(parsed) || !parsed.every(isPlainJsonObject)) {
      return { valid: false, rows: [] }
    }
    return { valid: true, rows: parsed.map((row) => ({ ...row })) }
  } catch {
    return { valid: false, rows: [] }
  }
}

export function deriveDatasetColumns(
  rows: readonly Record<string, unknown>[],
  schemaFields?: readonly DatasetSchemaHint[],
): string[] {
  const columns: string[] = []
  const seen = new Set<string>()
  for (const field of schemaFields || []) {
    const name = field.name.trim()
    if (name && !seen.has(name)) {
      seen.add(name)
      columns.push(name)
    }
  }
  for (const row of rows) {
    for (const key of Object.keys(row)) {
      if (key && !seen.has(key)) {
        seen.add(key)
        columns.push(key)
      }
    }
  }
  return columns
}

export function formatCellDisplay(value: unknown): string {
  if (value === undefined || value === null) return ''
  if (typeof value === 'object') return JSON.stringify(value)
  return String(value)
}

export function coerceCellValue(raw: string, fieldType?: string): unknown {
  const trimmed = raw.trim()
  if (fieldType === 'integer') {
    if (!trimmed) return null
    const parsed = Number.parseInt(trimmed, 10)
    return Number.isFinite(parsed) && String(parsed) === trimmed ? parsed : raw
  }
  if (fieldType === 'number') {
    if (!trimmed) return null
    const parsed = Number(trimmed)
    return Number.isFinite(parsed) ? parsed : raw
  }
  if (fieldType === 'boolean') {
    if (!trimmed) return null
    if (trimmed.toLowerCase() === 'true') return true
    if (trimmed.toLowerCase() === 'false') return false
    return raw
  }
  if (fieldType === 'json') {
    if (!trimmed) return null
    try {
      return JSON.parse(trimmed)
    } catch {
      return raw
    }
  }
  return raw
}

function splitCsvLine(line: string, delimiter: '\t' | ','): string[] {
  if (delimiter === '\t') {
    return line.split('\t').map((cell) => cell.trim())
  }
  const cells: string[] = []
  let current = ''
  let inQuotes = false
  for (let i = 0; i < line.length; i += 1) {
    const ch = line[i]
    if (ch === '"') {
      if (inQuotes && line[i + 1] === '"') {
        current += '"'
        i += 1
      } else {
        inQuotes = !inQuotes
      }
    } else if (ch === ',' && !inQuotes) {
      cells.push(current.trim())
      current = ''
    } else {
      current += ch
    }
  }
  cells.push(current.trim())
  return cells
}

export function parseDelimitedTable(
  text: string,
  schemaFields?: readonly DatasetSchemaHint[],
): Record<string, unknown>[] {
  const lines = text
    .split(/\r?\n/)
    .map((line) => line.trimEnd())
    .filter((line) => line.trim().length > 0)
  if (lines.length < 2) return []

  const delimiter: '\t' | ',' = lines[0].includes('\t') ? '\t' : ','
  const headers = splitCsvLine(lines[0], delimiter).map((h) => h.trim()).filter(Boolean)
  if (!headers.length) return []

  const typeMap = new Map<string, string | undefined>()
  for (const field of schemaFields || []) {
    typeMap.set(field.name.trim(), field.type)
  }

  return lines.slice(1).map((line) => {
    const cells = splitCsvLine(line, delimiter)
    const row: Record<string, unknown> = {}
    headers.forEach((header, idx) => {
      const rawCell = cells[idx] ?? ''
      row[header] = coerceCellValue(rawCell, typeMap.get(header))
    })
    return row
  })
}
