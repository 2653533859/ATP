const NAIVE_ISO_DATETIME_RE = /^\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}(?:\.\d+)?$/

function pad2(n: number): string {
  return String(n).padStart(2, '0')
}

export function formatLocalDateTime(value?: string | null, fallback = '-'): string {
  if (!value || !value.trim()) return fallback
  const trimmed = value.trim()
  const normalized = NAIVE_ISO_DATETIME_RE.test(trimmed)
    ? `${trimmed.replace(' ', 'T')}Z`
    : trimmed
  const parsed = new Date(normalized)
  if (Number.isNaN(parsed.getTime())) {
    return trimmed.slice(0, 19).replace('T', ' ')
  }
  return `${parsed.getFullYear()}-${pad2(parsed.getMonth() + 1)}-${pad2(parsed.getDate())} ${pad2(parsed.getHours())}:${pad2(parsed.getMinutes())}:${pad2(parsed.getSeconds())}`
}
