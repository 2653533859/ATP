<template>
  <div class="body-viewer">
    <div class="viewer-toolbar">
      <a-radio-group v-model:value="viewMode" size="small">
        <a-radio-button value="fields">{{ t('api_workbench.console.body_view.fields') }}</a-radio-button>
        <a-radio-button value="raw">{{ t('api_workbench.console.body_view.raw') }}</a-radio-button>
      </a-radio-group>
      <span class="format-label">{{ formatLabel }}<template v-if="rows.length"> · {{ t('api_workbench.console.body_view.field_count', { count: rows.length }) }}</template></span>
    </div>

    <pre v-if="viewMode === 'raw'" class="raw-body">{{ rawDisplay }}</pre>
    <template v-else-if="rows.length">
      <a-input-search v-model:value="filter" allow-clear class="field-search" :placeholder="t('api_workbench.console.body_view.search')" />
      <div class="field-scroll">
        <table class="field-table">
          <thead><tr><th>{{ t('api_workbench.console.body_view.path') }}</th><th>{{ t('api_workbench.console.body_view.type') }}</th><th>{{ t('api_workbench.console.body_view.value') }}</th></tr></thead>
          <tbody>
            <tr v-for="(row, index) in visibleRows" :key="`${row.path}-${index}`">
              <td><code :style="{ paddingLeft: `${Math.min(row.depth, 8) * 12}px` }">{{ row.path }}</code></td>
              <td><span class="type-chip">{{ row.type }}</span></td>
              <td class="field-value">{{ row.value }}</td>
            </tr>
          </tbody>
        </table>
        <div v-if="!visibleRows.length" class="viewer-note">{{ t('api_workbench.console.body_view.no_match') }}</div>
      </div>
      <div v-if="limited" class="viewer-note">{{ t('api_workbench.console.body_view.limited') }}</div>
    </template>
    <template v-else-if="body.trim()">
      <div class="viewer-note">{{ t('api_workbench.console.body_view.text_note') }}</div>
      <div class="text-lines">
        <div v-for="(line, index) in textLines" :key="index" class="text-line"><span>{{ index + 1 }}</span><code>{{ line }}</code></div>
      </div>
      <div v-if="textLimited" class="viewer-note">{{ t('api_workbench.console.body_view.limited') }}</div>
    </template>
    <div v-else class="empty-body">{{ t('api_workbench.console.no_response_body_detail') }}</div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'

type FieldRow = { path: string; type: string; value: string; depth: number }
type ParsedBody = { format: string; rows: FieldRow[]; limited: boolean }
const MAX_ROWS = 500
const MAX_DEPTH = 14
const MAX_VALUE = 300

const props = defineProps<{ body: string; contentType: string; sizeBytes: number }>()
const { t } = useI18n()
const viewMode = ref<'fields' | 'raw'>('fields')
const filter = ref('')
watch(() => [props.body, props.contentType, props.sizeBytes], () => { viewMode.value = 'fields'; filter.value = '' })

function previewValue(value: unknown): string {
  const text = String(value)
  return text.length > MAX_VALUE ? `${text.slice(0, MAX_VALUE)}…` : text
}

function parseJson(body: string): ParsedBody | null {
  try {
    const root: unknown = JSON.parse(body)
    const rows: FieldRow[] = []
    let limited = false
    function add(value: unknown, path: string, depth: number) {
      if (rows.length >= MAX_ROWS || depth > MAX_DEPTH) { limited = true; return }
      if (Array.isArray(value)) {
        rows.push({ path, type: 'array', value: `${value.length} items`, depth })
        value.forEach((item, index) => add(item, `${path}[${index}]`, depth + 1))
      } else if (value !== null && typeof value === 'object') {
        const entries = Object.entries(value)
        rows.push({ path, type: 'object', value: `${entries.length} fields`, depth })
        entries.forEach(([key, item]) => add(item, path === '$' ? key : `${path}.${key}`, depth + 1))
      } else {
        rows.push({ path, type: value === null ? 'null' : typeof value, value: value === null ? 'null' : previewValue(value), depth })
      }
    }
    add(root, '$', 0)
    return { format: 'JSON', rows, limited }
  } catch { return null }
}

function parseXml(body: string): ParsedBody | null {
  if (/<!\s*(?:DOCTYPE|ENTITY)/i.test(body)) return null
  const doc = new DOMParser().parseFromString(body, 'application/xml')
  if (doc.querySelector('parsererror')) return null
  const rows: FieldRow[] = []
  let limited = false
  function visit(element: Element, path: string, depth: number) {
    if (rows.length >= MAX_ROWS || depth > MAX_DEPTH) { limited = true; return }
    const children = Array.from(element.children)
    rows.push({ path, type: 'element', value: children.length ? `${children.length} children` : previewValue(element.textContent?.trim() || ''), depth })
    Array.from(element.attributes).forEach((attribute) => {
      if (rows.length >= MAX_ROWS) { limited = true; return }
      rows.push({ path: `${path}.@${attribute.name}`, type: 'attribute', value: previewValue(attribute.value), depth: depth + 1 })
    })
    const counts = new Map<string, number>()
    children.forEach((child) => {
      const index = counts.get(child.tagName) || 0
      counts.set(child.tagName, index + 1)
      visit(child, `${path}.${child.tagName}[${index}]`, depth + 1)
    })
  }
  visit(doc.documentElement, doc.documentElement.tagName, 0)
  return { format: 'XML', rows, limited }
}

function parseForm(body: string): ParsedBody {
  const rows: FieldRow[] = []
  for (const [key, value] of new URLSearchParams(body)) {
    if (rows.length >= MAX_ROWS) return { format: 'Form', rows, limited: true }
    rows.push({ path: key, type: 'string', value: previewValue(value), depth: 0 })
  }
  return { format: 'Form', rows, limited: false }
}

function parseDelimited(body: string, separator: string, format: string): ParsedBody {
  const records: string[][] = []
  let record: string[] = []
  let field = ''
  let quoted = false
  let limited = false
  for (let index = 0; index < body.length; index += 1) {
    const char = body[index]
    if (char === '"') {
      if (quoted && body[index + 1] === '"') { field += '"'; index += 1 } else quoted = !quoted
    } else if (char === separator && !quoted) {
      record.push(field); field = ''
    } else if ((char === '\n' || char === '\r') && !quoted) {
      record.push(field); records.push(record); record = []; field = ''
      if (char === '\r' && body[index + 1] === '\n') index += 1
      if (records.length >= 101) { limited = true; break }
    } else field += char
  }
  if (!limited && (record.length || field)) { record.push(field); records.push(record) }
  const headers = records.shift() || []
  const rows: FieldRow[] = []
  records.forEach((values, recordIndex) => values.forEach((value, fieldIndex) => {
    if (rows.length >= MAX_ROWS) { limited = true; return }
    rows.push({ path: `[${recordIndex}].${headers[fieldIndex] || `column_${fieldIndex + 1}`}`, type: 'string', value: previewValue(value), depth: 0 })
  }))
  return { format, rows, limited }
}

const parsed = computed<ParsedBody>(() => {
  const body = props.body.trim()
  const mime = props.contentType.toLowerCase()
  if (!body) return { format: 'Empty', rows: [], limited: false }
  if (mime.includes('json') || /^[\[{]/.test(body)) {
    const json = parseJson(body)
    if (json) return json
  }
  if (mime.includes('xml') || (!mime.includes('html') && body.startsWith('<'))) {
    const xml = parseXml(body)
    if (xml) return xml
  }
  if (mime.includes('x-www-form-urlencoded')) return parseForm(body)
  if (mime.includes('text/csv') || mime.includes('application/csv')) return parseDelimited(props.body, ',', 'CSV')
  if (mime.includes('tab-separated-values')) return parseDelimited(props.body, '\t', 'TSV')
  return { format: mime.includes('html') ? 'HTML' : 'Text', rows: [], limited: false }
})
const rows = computed(() => parsed.value.rows)
const limited = computed(() => parsed.value.limited)
const formatLabel = computed(() => parsed.value.format)
const visibleRows = computed(() => {
  const query = filter.value.trim().toLowerCase()
  return query ? rows.value.filter((row) => `${row.path} ${row.type} ${row.value}`.toLowerCase().includes(query)) : rows.value
})
const textLines = computed(() => props.body.split(/\r?\n/).slice(0, 200).map((line) => previewValue(line)))
const textLimited = computed(() => props.body.split(/\r?\n/).length > 200 || props.body.split(/\r?\n/).some((line) => line.length > MAX_VALUE))
const rawDisplay = computed(() => props.sizeBytes === 0 ? t('api_workbench.console.no_response_body_detail') : props.body)
</script>

<style scoped>
.body-viewer { min-width: 0; }
.viewer-toolbar { display: flex; align-items: center; justify-content: space-between; gap: 12px; margin-bottom: 12px; }
.format-label { color: var(--c-text-tertiary); font-size: 12px; }
.field-search { max-width: 360px; margin-bottom: 10px; }
.field-scroll, .text-lines, .raw-body { max-height: 460px; overflow: auto; border: 1px solid var(--c-border); border-radius: var(--radius-sm); background: var(--c-bg-subtle); color: var(--c-text); }
.field-table { width: 100%; border-collapse: collapse; font-size: 12px; text-align: left; }
.field-table th { position: sticky; top: 0; z-index: 1; padding: 10px 12px; background: var(--c-bg-elevated); color: var(--c-text-secondary); font-weight: 650; border-bottom: 1px solid var(--c-border); }
.field-table td { padding: 9px 12px; border-top: 1px solid var(--c-border-subtle); vertical-align: top; color: var(--c-text); }
.field-table td:first-child { width: 42%; }
.field-table code, .text-line code { color: var(--c-primary); font: 12px/1.5 'JetBrains Mono', Consolas, monospace; overflow-wrap: anywhere; }
.type-chip { color: var(--c-info); font: 11px 'JetBrains Mono', Consolas, monospace; }
.field-value { white-space: pre-wrap; overflow-wrap: anywhere; color: var(--c-text); }
.viewer-note { padding: 10px 12px; color: var(--c-text-tertiary); font-size: 12px; }
.text-line { display: grid; grid-template-columns: 42px minmax(0, 1fr); gap: 12px; padding: 3px 12px; }
.text-line:first-child { padding-top: 12px; }
.text-line:last-child { padding-bottom: 12px; }
.text-line > span { color: var(--c-text-tertiary); text-align: right; font: 11px/1.6 'JetBrains Mono', Consolas, monospace; user-select: none; }
.raw-body { min-height: 210px; margin: 0; padding: 16px 18px; color: var(--c-text); font: 12px/1.65 'JetBrains Mono', Consolas, monospace; white-space: pre-wrap; overflow-wrap: anywhere; }
.empty-body { padding: 22px; border: 1px dashed var(--c-border); border-radius: var(--radius-sm); color: var(--c-text-tertiary); font-size: 12px; }
@media (max-width: 560px) { .viewer-toolbar { align-items: flex-start; flex-direction: column; } .field-table td:first-child { width: auto; } }
</style>
