<template>
  <div class="dataset-rows-editor">
    <div class="editor-toolbar">
      <div class="mode-pills" role="tablist">
        <button
          type="button"
          role="tab"
          class="mode-pill"
          :class="{ 'is-active': mode === 'table' }"
          :aria-selected="mode === 'table'"
          @click="switchMode('table')"
        >
          {{ t('dataset_table_editor.mode_table') }} ({{ rows.length }})
        </button>
        <button
          type="button"
          role="tab"
          class="mode-pill"
          :class="{ 'is-active': mode === 'raw' }"
          :aria-selected="mode === 'raw'"
          @click="switchMode('raw')"
        >
          {{ t('dataset_table_editor.mode_raw') }}
        </button>
      </div>

      <div v-if="mode === 'table' && !disabled" class="table-actions">
        <a-button size="small" @click="pasteOpen = !pasteOpen">
          {{ t('dataset_table_editor.paste_import') }}
        </a-button>
        <a-button size="small" type="primary" ghost @click="addRow">
          <PlusOutlined /> {{ t('dataset_table_editor.add_row') }}
        </a-button>
      </div>
    </div>

    <div v-if="mode === 'table'" class="table-mode-body">
      <div v-if="pasteOpen && !disabled" class="paste-box">
        <a-textarea
          v-model:value="pasteText"
          :rows="4"
          class="mono-textarea"
          :placeholder="t('dataset_table_editor.paste_placeholder')"
        />
        <div class="paste-actions">
          <a-button size="small" @click="pasteOpen = false">{{ t('common.cancel') }}</a-button>
          <a-button size="small" @click="importPastedRows(true)">{{ t('dataset_table_editor.paste_append') }}</a-button>
          <a-button size="small" type="primary" @click="importPastedRows(false)">{{ t('dataset_table_editor.paste_replace') }}</a-button>
        </div>
      </div>

      <div v-if="!disabled" class="column-adder">
        <a-input
          v-model:value="newColumnName"
          size="small"
          style="width: 180px"
          :placeholder="t('dataset_table_editor.column_placeholder')"
          @press-enter="addColumn"
        />
        <a-button size="small" @click="addColumn">{{ t('dataset_table_editor.add_column') }}</a-button>
      </div>

      <div v-if="!columns.length" class="empty-tip">{{ t('dataset_table_editor.empty_columns') }}</div>
      <div v-else class="table-scroll">
        <table class="editable-grid">
          <thead>
            <tr>
              <th class="col-index">#</th>
              <th v-for="col in columns" :key="col">
                <div class="col-header">
                  <span>{{ col }}</span>
                  <DeleteOutlined
                    v-if="!disabled && !isSchemaColumn(col)"
                    class="col-remove"
                    @click="removeColumn(col)"
                  />
                </div>
              </th>
              <th v-if="!disabled" class="col-actions">{{ t('common.actions') }}</th>
            </tr>
          </thead>
          <tbody>
            <tr v-if="!rows.length">
              <td :colspan="columns.length + (disabled ? 1 : 2)" class="empty-row-cell">
                {{ t('dataset_table_editor.empty_rows') }}
              </td>
            </tr>
            <tr v-for="(row, rowIdx) in rows" :key="rowIdx">
              <td class="col-index">{{ rowIdx + 1 }}</td>
              <td v-for="col in columns" :key="col">
                <a-input
                  :value="formatCellDisplay(row[col])"
                  size="small"
                  :disabled="disabled"
                  @update:value="(val: string) => updateCell(rowIdx, col, val)"
                />
              </td>
              <td v-if="!disabled" class="col-actions">
                <a-button type="link" size="small" danger @click="removeRow(rowIdx)">
                  {{ t('common.delete') }}
                </a-button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <div v-else>
      <a-textarea
        v-model:value="rawText"
        :rows="rowsCount"
        :placeholder="placeholder"
        :disabled="disabled"
        class="mono-textarea"
        @change="handleRawChange"
      />
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { message } from 'ant-design-vue'
import { DeleteOutlined, PlusOutlined } from '@ant-design/icons-vue'
import { useI18n } from 'vue-i18n'
import {
  coerceCellValue,
  deriveDatasetColumns,
  formatCellDisplay,
  parseDatasetRowsText,
  parseDelimitedTable,
  type DatasetSchemaHint,
} from '@/utils/datasetTable'

const props = withDefaults(
  defineProps<{
    value?: string
    schemaFields?: readonly DatasetSchemaHint[]
    rowsCount?: number
    placeholder?: string
    disabled?: boolean
  }>(),
  {
    value: '[]',
    schemaFields: () => [],
    rowsCount: 10,
    placeholder: '',
    disabled: false,
  },
)

const emit = defineEmits<{ 'update:value': [v: string] }>()
const { t } = useI18n()

const mode = ref<'table' | 'raw'>('table')
const rawText = ref(props.value ?? '[]')
const rows = ref<Record<string, unknown>[]>([])
const extraColumns = ref<string[]>([])
const newColumnName = ref('')
const pasteOpen = ref(false)
const pasteText = ref('')

const columns = computed(() => {
  const base = deriveDatasetColumns(rows.value, props.schemaFields)
  const seen = new Set(base)
  for (const col of extraColumns.value) {
    if (col && !seen.has(col)) {
      seen.add(col)
      base.push(col)
    }
  }
  return base
})

const schemaColumnSet = computed(() => new Set((props.schemaFields || []).map((item) => item.name.trim()).filter(Boolean)))
const schemaTypeMap = computed(() => {
  const map = new Map<string, string | undefined>()
  for (const field of props.schemaFields || []) {
    const name = field.name.trim()
    if (name) map.set(name, field.type)
  }
  return map
})

function isSchemaColumn(col: string) {
  return schemaColumnSet.value.has(col)
}

function applyExternalValue(nextValue: string | undefined) {
  const normalized = nextValue ?? '[]'
  rawText.value = normalized
  extraColumns.value = []
  newColumnName.value = ''
  pasteOpen.value = false
  pasteText.value = ''
  const parsed = parseDatasetRowsText(normalized)
  if (parsed.valid) {
    rows.value = parsed.rows
    mode.value = 'table'
  } else {
    rows.value = []
    mode.value = 'raw'
  }
}

watch(
  () => props.value,
  (nextValue, prevValue) => {
    const normalized = nextValue ?? '[]'
    if (prevValue !== undefined && normalized === rawText.value) {
      return
    }
    applyExternalValue(normalized)
  },
  { immediate: true },
)

function emitRows() {
  const serialized = JSON.stringify(rows.value, null, 2)
  rawText.value = serialized
  emit('update:value', serialized)
}

function handleRawChange() {
  const parsed = parseDatasetRowsText(rawText.value)
  if (parsed.valid) {
    rows.value = parsed.rows
  }
  emit('update:value', rawText.value)
}

function switchMode(nextMode: 'table' | 'raw') {
  if (nextMode === mode.value) return
  if (nextMode === 'table') {
    const parsed = parseDatasetRowsText(rawText.value)
    if (!parsed.valid) {
      message.warning(t('dataset_table_editor.invalid_json_hint'))
      return
    }
    rows.value = parsed.rows
  }
  mode.value = nextMode
}

function addColumn() {
  const name = newColumnName.value.trim()
  if (!name) return
  if (!extraColumns.value.includes(name) && !columns.value.includes(name)) {
    extraColumns.value.push(name)
  }
  for (const row of rows.value) {
    if (!(name in row)) row[name] = ''
  }
  newColumnName.value = ''
  if (rows.value.length) emitRows()
}

function removeColumn(col: string) {
  extraColumns.value = extraColumns.value.filter((item) => item !== col)
  for (const row of rows.value) {
    delete row[col]
  }
  emitRows()
}

function addRow() {
  const newRow: Record<string, unknown> = {}
  for (const col of columns.value) {
    newRow[col] = ''
  }
  rows.value.push(newRow)
  emitRows()
}

function removeRow(idx: number) {
  rows.value.splice(idx, 1)
  emitRows()
}

function updateCell(rowIdx: number, col: string, rawVal: string) {
  const target = rows.value[rowIdx]
  if (!target) return
  target[col] = coerceCellValue(rawVal, schemaTypeMap.value.get(col))
  emitRows()
}

function importPastedRows(append: boolean) {
  const parsed = parseDelimitedTable(pasteText.value, props.schemaFields)
  if (!parsed.length) {
    message.warning(t('dataset_table_editor.paste_empty'))
    return
  }
  rows.value = append ? [...rows.value, ...parsed] : parsed
  pasteText.value = ''
  pasteOpen.value = false
  emitRows()
  message.success(t('dataset_table_editor.paste_success', { count: parsed.length }))
}
</script>

<style scoped>
.dataset-rows-editor {
  border: 1px solid var(--c-border);
  border-radius: var(--radius-md);
  background: var(--c-bg-body);
  padding: 10px 12px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.editor-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 8px;
}

.mode-pills {
  display: inline-flex;
  padding: 2px;
  border-radius: var(--radius-sm);
  background: var(--c-bg-subtle);
  border: 1px solid var(--c-border-subtle);
  gap: 2px;
}

.mode-pill {
  border: 0;
  background: transparent;
  padding: 2px 10px;
  border-radius: var(--radius-xs);
  font-size: 12px;
  font-weight: 500;
  color: var(--c-text-secondary);
  cursor: pointer;
  font-family: inherit;
}

.mode-pill.is-active {
  background: var(--c-bg-elevated);
  color: var(--c-primary);
  font-weight: 600;
  box-shadow: var(--shadow-xs);
}

.table-actions {
  display: flex;
  align-items: center;
  gap: 6px;
}

.paste-box {
  padding: 8px;
  border-radius: var(--radius-sm);
  background: var(--c-bg-elevated);
  border: 1px dashed var(--c-border-strong);
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.paste-actions {
  display: flex;
  justify-content: flex-end;
  gap: 6px;
}

.column-adder {
  display: flex;
  align-items: center;
  gap: 8px;
}

.table-mode-body {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.table-scroll {
  overflow-x: auto;
  border: 1px solid var(--c-border);
  border-radius: var(--radius-sm);
  background: var(--c-bg-elevated);
}

.editable-grid {
  width: 100%;
  border-collapse: collapse;
  font-size: 12px;
}

.editable-grid th,
.editable-grid td {
  padding: 6px 8px;
  border-bottom: 1px solid var(--c-border-subtle);
  border-right: 1px solid var(--c-border-subtle);
  min-width: 120px;
}

.editable-grid th {
  background: var(--c-bg-subtle);
  text-align: left;
  font-weight: 600;
  color: var(--c-text-secondary);
}

.editable-grid .col-index {
  width: 42px;
  min-width: 42px;
  text-align: center;
  color: var(--c-text-tertiary);
}

.editable-grid .col-actions {
  width: 72px;
  min-width: 72px;
  text-align: center;
}

.col-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 6px;
}

.col-remove {
  color: var(--c-text-tertiary);
  cursor: pointer;
}

.col-remove:hover {
  color: var(--c-error);
}

.empty-tip,
.empty-row-cell {
  padding: 12px;
  font-size: 12px;
  color: var(--c-text-tertiary);
  text-align: center;
}

.mono-textarea {
  font-family: monospace;
  font-size: 12px;
}
</style>
