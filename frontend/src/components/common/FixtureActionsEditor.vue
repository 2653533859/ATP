<template>
  <div class="fixture-actions-editor">
    <div class="editor-toolbar">
      <div class="mode-pills" role="tablist">
        <button
          type="button"
          role="tab"
          class="mode-pill"
          :class="{ 'is-active': mode === 'visual' }"
          :aria-selected="mode === 'visual'"
          @click="switchMode('visual')"
        >
          {{ t('fixture_editor.mode_visual') }}
        </button>
        <button
          type="button"
          role="tab"
          class="mode-pill"
          :class="{ 'is-active': mode === 'raw' }"
          :aria-selected="mode === 'raw'"
          @click="switchMode('raw')"
        >
          {{ t('fixture_editor.mode_raw') }}
        </button>
      </div>
    </div>

    <div v-if="mode === 'visual'" class="visual-body">
      <div v-if="!rows.length" class="empty-hint">{{ t('fixture_editor.empty_hint') }}</div>
      <div v-for="(row, idx) in rows" :key="idx" class="action-row">
        <a-select
          v-model:value="row.action"
          size="small"
          class="action-select"
          :disabled="disabled"
          @change="emitRows"
        >
          <a-select-option value="set_variable">{{ t('fixture_editor.action_set') }}</a-select-option>
          <a-select-option value="delete_variable">{{ t('fixture_editor.action_delete') }}</a-select-option>
          <a-select-option value="request">{{ t('fixture_editor.action_request') }}</a-select-option>
        </a-select>

        <template v-if="row.action === 'request'">
          <a-select
            v-model:value="row.method"
            size="small"
            style="width: 88px"
            :disabled="disabled"
            @change="emitRows"
          >
            <a-select-option value="GET">GET</a-select-option>
            <a-select-option value="POST">POST</a-select-option>
            <a-select-option value="PUT">PUT</a-select-option>
            <a-select-option value="DELETE">DELETE</a-select-option>
          </a-select>
          <a-input
            v-model:value="row.url"
            size="small"
            class="flex-main"
            :placeholder="t('fixture_editor.url')"
            :disabled="disabled"
            @change="emitRows"
          />
        </template>
        <template v-else>
          <a-input
            v-model:value="row.variable"
            size="small"
            class="flex-var"
            :placeholder="t('fixture_editor.variable')"
            :disabled="disabled"
            @change="emitRows"
          />
          <a-input
            v-if="row.action === 'set_variable'"
            v-model:value="row.value"
            size="small"
            class="flex-main"
            :placeholder="t('fixture_editor.value')"
            :disabled="disabled"
            @change="emitRows"
          />
        </template>

        <MinusCircleOutlined v-if="!disabled" class="remove-icon" @click="removeRow(idx)" />
      </div>

      <a-button v-if="!disabled" type="dashed" size="small" block @click="addRow">
        <PlusOutlined /> {{ t('fixture_editor.add_action') }}
      </a-button>
    </div>

    <div v-else>
      <a-textarea
        v-model:value="rawText"
        :rows="props.rows"
        :placeholder="placeholder"
        :disabled="disabled"
        class="mono-textarea"
        @change="handleRawChange"
      />
      <div v-if="rawInvalid" class="json-error">{{ t('fixture_editor.invalid_json_hint') }}</div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'
import { message } from 'ant-design-vue'
import { MinusCircleOutlined, PlusOutlined } from '@ant-design/icons-vue'
import { useI18n } from 'vue-i18n'
import {
  parseFixtureActionsText,
  serializeFixtureActions,
  type FixtureActionRow,
} from '@/utils/fixtureActions'

const props = withDefaults(
  defineProps<{
    value?: string
    rows?: number
    placeholder?: string
    disabled?: boolean
  }>(),
  {
    value: '[]',
    rows: 6,
    placeholder: '',
    disabled: false,
  },
)

const emit = defineEmits<{ 'update:value': [v: string] }>()
const { t } = useI18n()

const mode = ref<'visual' | 'raw'>('visual')
const rawText = ref(props.value ?? '[]')
const rows = ref<FixtureActionRow[]>([])
const rawInvalid = ref(false)

watch(
  () => props.value,
  (nextValue, prevValue) => {
    const normalized = nextValue ?? '[]'
    if (prevValue !== undefined && normalized === rawText.value) {
      return
    }
    rawText.value = normalized
    const parsed = parseFixtureActionsText(normalized)
    if (parsed.valid) {
      rows.value = parsed.rows
      rawInvalid.value = false
      mode.value = 'visual'
    } else {
      rows.value = []
      rawInvalid.value = true
      mode.value = 'raw'
    }
  },
  { immediate: true },
)

function emitRows() {
  const serialized = serializeFixtureActions(rows.value)
  rawText.value = serialized
  rawInvalid.value = false
  emit('update:value', serialized)
}

function handleRawChange() {
  const parsed = parseFixtureActionsText(rawText.value)
  rawInvalid.value = !parsed.valid
  if (parsed.valid) rows.value = parsed.rows
  emit('update:value', rawText.value)
}

function switchMode(nextMode: 'visual' | 'raw') {
  if (nextMode === mode.value) return
  if (nextMode === 'visual') {
    const parsed = parseFixtureActionsText(rawText.value)
    if (!parsed.valid) {
      message.warning(t('fixture_editor.invalid_json_hint'))
      return
    }
    rows.value = parsed.rows
    rawInvalid.value = false
  }
  mode.value = nextMode
}

function addRow() {
  rows.value.push({ action: 'set_variable', variable: '', value: '', method: 'GET', url: '' })
}

function removeRow(idx: number) {
  rows.value.splice(idx, 1)
  emitRows()
}
</script>

<style scoped>
.fixture-actions-editor {
  border: 1px solid var(--c-border);
  border-radius: var(--radius-md);
  background: var(--c-bg-body);
  padding: 8px 10px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.editor-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
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

.visual-body {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.empty-hint {
  font-size: 12px;
  color: var(--c-text-tertiary);
}

.action-row {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
}

.action-select {
  width: 112px;
  flex-shrink: 0;
}

.flex-var {
  width: 120px;
}

.flex-main {
  flex: 1;
  min-width: 110px;
}

.remove-icon {
  color: var(--c-text-tertiary);
  cursor: pointer;
  font-size: 14px;
}

.remove-icon:hover {
  color: var(--c-error);
}

.mono-textarea {
  font-family: monospace;
  font-size: 12px;
}

.json-error {
  margin-top: 4px;
  font-size: 12px;
  color: var(--c-error);
}
</style>
