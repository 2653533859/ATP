<template>
  <div class="smart-json-editor" :class="{ 'is-compact': compact }">
    <div class="smart-json-toolbar">
      <div class="smart-json-modes" role="tablist">
        <button
          type="button"
          role="tab"
          class="mode-pill"
          :class="{ 'is-active': mode === 'visual' }"
          :aria-selected="mode === 'visual'"
          @click="switchMode('visual')"
        >
          {{ t('smart_json.mode_visual') }}
        </button>
        <button
          type="button"
          role="tab"
          class="mode-pill"
          :class="{ 'is-active': mode === 'raw' }"
          :aria-selected="mode === 'raw'"
          @click="switchMode('raw')"
        >
          {{ t('smart_json.mode_raw') }}
        </button>
      </div>

      <div class="smart-json-actions">
        <span
          v-if="rawText.trim()"
          class="json-status-badge"
          :class="validation.valid ? 'is-valid' : 'is-invalid'"
        >
          {{ validation.valid ? t('smart_json.status_valid') : t('smart_json.status_invalid') }}
        </span>

        <a-dropdown v-if="templates.length && !disabled" :trigger="['click']">
          <template #overlay>
            <a-menu @click="handleSelectTemplate">
              <a-menu-item v-for="tpl in templates" :key="tpl.id">
                <div class="preset-menu-item">
                  <span class="preset-label">{{ tpl.label }}</span>
                  <code class="preset-code">{{ tpl.preview }}</code>
                </div>
              </a-menu-item>
            </a-menu>
          </template>
          <a-button size="small" type="text">
            <ThunderboltOutlined /> {{ t('smart_json.templates') }}
          </a-button>
        </a-dropdown>

        <template v-if="mode === 'raw' && !disabled">
          <a-button size="small" type="text" @click="formatRaw">
            <FormatPainterOutlined /> {{ t('smart_json.format') }}
          </a-button>
          <a-button v-if="!compact" size="small" type="text" @click="compressRaw">
            {{ t('smart_json.compress') }}
          </a-button>
        </template>

        <a-button
          v-if="mode === 'visual' && rows.length && !disabled"
          size="small"
          type="text"
          danger
          @click="clearRows"
        >
          {{ t('smart_json.clear_all') }}
        </a-button>
      </div>
    </div>

    <div v-if="mode === 'visual'" class="smart-json-visual">
      <div v-if="!rows.length" class="visual-empty-hint">
        {{ t('smart_json.empty_visual_hint') }}
      </div>
      <div v-for="(row, idx) in rows" :key="idx" class="visual-row">
        <a-auto-complete
          v-if="presetKind === 'headers'"
          v-model:value="row.key"
          :options="headerOptions"
          :placeholder="t('smart_json.key_placeholder')"
          size="small"
          class="visual-key"
          :disabled="disabled"
          @change="handleRowsChange"
        />
        <a-input
          v-else
          v-model:value="row.key"
          :placeholder="t('smart_json.key_placeholder')"
          size="small"
          class="visual-key"
          :disabled="disabled"
          @change="handleRowsChange"
        />

        <a-select
          v-model:value="row.type"
          size="small"
          class="visual-type"
          :disabled="disabled"
          @change="handleTypeChange(row)"
        >
          <a-select-option value="string">{{ t('smart_json.types.string') }}</a-select-option>
          <a-select-option value="number">{{ t('smart_json.types.number') }}</a-select-option>
          <a-select-option value="boolean">{{ t('smart_json.types.boolean') }}</a-select-option>
          <a-select-option value="null">{{ t('smart_json.types.null') }}</a-select-option>
          <a-select-option value="json">{{ t('smart_json.types.json') }}</a-select-option>
        </a-select>

        <a-select
          v-if="row.type === 'boolean'"
          v-model:value="row.value"
          size="small"
          class="visual-val"
          :disabled="disabled"
          @change="handleRowsChange"
        >
          <a-select-option value="true">true</a-select-option>
          <a-select-option value="false">false</a-select-option>
        </a-select>
        <a-input
          v-else-if="row.type === 'null'"
          value="null"
          size="small"
          class="visual-val"
          disabled
        />
        <a-input
          v-else
          v-model:value="row.value"
          size="small"
          class="visual-val"
          :class="{ 'is-mono': row.type === 'json' || row.type === 'number' }"
          :placeholder="row.type === 'json' ? t('smart_json.json_value_placeholder') : t('smart_json.value_placeholder')"
          :disabled="disabled"
          @change="handleRowsChange"
        />

        <MinusCircleOutlined v-if="!disabled" class="visual-remove" @click="removeRow(idx)" />
      </div>

      <a-button v-if="!disabled" type="dashed" size="small" block @click="addRow">
        <PlusOutlined /> {{ t('smart_json.add_field') }}
      </a-button>
      <div v-if="duplicateKeys.length" class="smart-json-notice">
        {{ t('smart_json.duplicate_keys_warning', { keys: duplicateKeys.join(', ') }) }}
      </div>
    </div>

    <div v-else class="smart-json-raw">
      <a-textarea
        v-model:value="rawText"
        :rows="rowsCount"
        :placeholder="placeholder || defaultPlaceholder"
        :disabled="disabled"
        class="smart-json-textarea"
        @change="handleRawChange"
      />
      <div v-if="rawBlockerMessage" class="smart-json-notice" :class="{ 'is-error': !validation.valid }">
        {{ rawBlockerMessage }}
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { message } from 'ant-design-vue'
import { FormatPainterOutlined, MinusCircleOutlined, PlusOutlined, ThunderboltOutlined } from '@ant-design/icons-vue'
import { useI18n } from 'vue-i18n'
import { tryCompressJson, tryFormatJson } from '@/utils/jsonFormat'
import {
  HEADER_KEY_SUGGESTIONS,
  jsonTextToRows,
  rowsToJsonText,
  validateJsonText,
  type JsonFieldRow,
  type JsonTemplateOption,
} from '@/utils/smartJson'

const props = withDefaults(
  defineProps<{
    value?: string | null
    rows?: number
    placeholder?: string
    compact?: boolean
    allowTemplates?: boolean
    presetKind?: 'headers' | 'none'
    templates?: readonly JsonTemplateOption[]
    defaultMode?: 'visual' | 'raw'
    disabled?: boolean
  }>(),
  {
    value: '',
    rows: 6,
    placeholder: '',
    compact: false,
    allowTemplates: false,
    presetKind: 'none',
    templates: () => [],
    defaultMode: 'visual',
    disabled: false,
  },
)

const emit = defineEmits<{ 'update:value': [v: string] }>()
const { t } = useI18n()

const rawText = ref(props.value ?? '')
const rows = ref<JsonFieldRow[]>([])
const mode = ref<'visual' | 'raw'>(props.defaultMode)

const headerOptions = HEADER_KEY_SUGGESTIONS.map((item) => ({ value: item }))
const defaultPlaceholder = '{\n  "key": "value"\n}'
const rowsCount = computed(() => Math.max(props.rows, props.compact ? 2 : 4))
const validation = computed(() => validateJsonText(rawText.value, props.allowTemplates))
const duplicateKeys = computed(() => {
  const seen = new Set<string>()
  const dupes: string[] = []
  for (const row of rows.value) {
    const key = row.key.trim()
    if (!key) continue
    if (seen.has(key) && !dupes.includes(key)) {
      dupes.push(key)
    }
    seen.add(key)
  }
  return dupes
})

const rawBlockerMessage = computed(() => {
  if (!rawText.value.trim()) return ''
  if (!validation.value.valid) {
    return `${t('smart_json.status_invalid')}${validation.value.error ? `：${validation.value.error}` : ''}`
  }
  if (validation.value.reason === 'array') return t('smart_json.visual_unavailable_array')
  if (validation.value.reason === 'template') return t('smart_json.visual_unavailable_template')
  if (validation.value.reason === 'primitive') return t('smart_json.visual_unavailable_primitive')
  return ''
})

function applyExternalValue(nextValue: string | null | undefined) {
  const normalized = nextValue ?? ''
  rawText.value = normalized
  const check = validateJsonText(normalized, props.allowTemplates)
  if (check.canUseVisual) {
    rows.value = jsonTextToRows(normalized) ?? []
    if (props.defaultMode === 'visual') {
      mode.value = 'visual'
    }
  } else {
    rows.value = []
    mode.value = 'raw'
  }
}

watch(
  () => props.value,
  (nextValue, prevValue) => {
    const normalized = nextValue ?? ''
    if (prevValue !== undefined && normalized === rawText.value) {
      return
    }
    applyExternalValue(normalized)
  },
  { immediate: true },
)

function emitRawText(next: string) {
  rawText.value = next
  emit('update:value', next)
}

function handleRowsChange() {
  const serialized = rowsToJsonText(rows.value, props.compact ? 2 : 2)
  emitRawText(serialized)
}

function handleRawChange() {
  emit('update:value', rawText.value)
}

function handleTypeChange(row: JsonFieldRow) {
  if (row.type === 'boolean' && row.value !== 'true' && row.value !== 'false') {
    row.value = 'true'
  } else if (row.type === 'null') {
    row.value = ''
  } else if (row.type === 'number' && !row.value.trim()) {
    row.value = '0'
  }
  handleRowsChange()
}

function addRow() {
  rows.value.push({ key: '', type: 'string', value: '' })
}

function removeRow(index: number) {
  rows.value.splice(index, 1)
  handleRowsChange()
}

function clearRows() {
  rows.value = []
  emitRawText('{}')
}

function switchMode(nextMode: 'visual' | 'raw') {
  if (nextMode === mode.value) return
  if (nextMode === 'visual') {
    const check = validateJsonText(rawText.value, props.allowTemplates)
    if (!check.canUseVisual) {
      const reasonKey = check.reason === 'array'
        ? 'smart_json.visual_unavailable_array'
        : check.reason === 'template'
          ? 'smart_json.visual_unavailable_template'
          : check.reason === 'primitive'
            ? 'smart_json.visual_unavailable_primitive'
            : 'smart_json.visual_unavailable_invalid'
      message.warning(t(reasonKey))
      return
    }
    rows.value = jsonTextToRows(rawText.value) ?? []
  }
  mode.value = nextMode
}

function formatRaw() {
  const next = tryFormatJson(rawText.value)
  if (next !== rawText.value) {
    emitRawText(next)
  }
}

function compressRaw() {
  const next = tryCompressJson(rawText.value)
  if (next !== rawText.value) {
    emitRawText(next)
  }
}

function handleSelectTemplate({ key }: { key: string | number }) {
  const tpl = props.templates.find((item) => item.id === String(key))
  if (!tpl) return
  emitRawText(tpl.value)
  const check = validateJsonText(tpl.value, props.allowTemplates)
  if (check.canUseVisual) {
    rows.value = jsonTextToRows(tpl.value) ?? []
  } else {
    rows.value = []
    mode.value = 'raw'
  }
}
</script>

<style scoped>
.smart-json-editor {
  border: 1px solid var(--c-border);
  border-radius: var(--radius-md);
  background: var(--c-bg-body);
  padding: 8px 10px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.smart-json-editor.is-compact {
  padding: 6px 8px;
  gap: 6px;
}

.smart-json-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 8px;
}

.smart-json-modes {
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
  transition: background 0.15s ease, color 0.15s ease;
}

.mode-pill.is-active {
  background: var(--c-bg-elevated);
  color: var(--c-primary);
  font-weight: 600;
  box-shadow: var(--shadow-xs);
}

.smart-json-actions {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 4px;
}

.json-status-badge {
  font-size: 11px;
  padding: 1px 6px;
  border-radius: var(--radius-full);
  font-weight: 500;
}

.json-status-badge.is-valid {
  color: var(--c-success);
  background: var(--c-success-soft);
}

.json-status-badge.is-invalid {
  color: var(--c-error);
  background: var(--c-error-soft);
}

.smart-json-visual {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.visual-empty-hint {
  font-size: 12px;
  color: var(--c-text-tertiary);
  padding: 4px 2px;
}

.visual-row {
  display: flex;
  align-items: center;
  gap: 6px;
}

.visual-key {
  flex: 1.1;
  min-width: 110px;
}

.visual-type {
  width: 96px;
  flex-shrink: 0;
}

.visual-val {
  flex: 1.5;
  min-width: 120px;
}

.visual-val.is-mono {
  font-family: monospace;
}

.visual-remove {
  color: var(--c-text-tertiary);
  cursor: pointer;
  font-size: 14px;
  flex-shrink: 0;
}

.visual-remove:hover {
  color: var(--c-error);
}

.smart-json-textarea {
  font-family: monospace;
  font-size: 12px;
}

.smart-json-notice {
  margin-top: 4px;
  font-size: 12px;
  color: var(--c-warning);
}

.smart-json-notice.is-error {
  color: var(--c-error);
}

.preset-menu-item {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.preset-label {
  font-size: 12px;
  font-weight: 500;
}

.preset-code {
  font-size: 11px;
  color: var(--c-text-tertiary);
}
</style>
