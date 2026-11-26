<template>
  <div class="fluency-stages-editor">
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
          {{ t('fluency_editor.mode_visual') }}
        </button>
        <button
          type="button"
          role="tab"
          class="mode-pill"
          :class="{ 'is-active': mode === 'raw' }"
          :aria-selected="mode === 'raw'"
          @click="switchMode('raw')"
        >
          {{ t('fluency_editor.mode_raw') }}
        </button>
      </div>

      <div v-if="mode === 'visual' && !disabled" class="preset-actions">
        <a-button size="small" type="link" @click="addPreset('swipe_up')">+ {{ t('fluency_editor.preset_swipe_up') }}</a-button>
        <a-button size="small" type="link" @click="addPreset('swipe_down')">+ {{ t('fluency_editor.preset_swipe_down') }}</a-button>
        <a-button size="small" type="link" @click="addPreset('tap_center')">+ {{ t('fluency_editor.preset_tap_center') }}</a-button>
      </div>
    </div>

    <div v-if="mode === 'visual'" class="visual-body">
      <div v-if="!rows.length" class="empty-hint">{{ t('fluency_editor.empty_hint') }}</div>
      <div v-for="(row, idx) in rows" :key="idx" class="stage-card">
        <div class="stage-head">
          <a-input
            v-model:value="row.name"
            size="small"
            class="stage-name"
            :placeholder="t('fluency_editor.stage_name')"
            :disabled="disabled"
            @change="emitRows"
          />
          <a-select
            v-model:value="row.action"
            size="small"
            style="width: 120px"
            :disabled="disabled"
            @change="emitRows"
          >
            <a-select-option value="swipe">{{ t('fluency_editor.action_swipe') }}</a-select-option>
            <a-select-option value="tap">{{ t('fluency_editor.action_tap') }}</a-select-option>
          </a-select>
          <a-input-number
            v-model:value="row.duration_seconds"
            size="small"
            :min="1"
            :max="120"
            addon-after="s"
            style="width: 96px"
            :disabled="disabled"
            @change="emitRows"
          />
          <MinusCircleOutlined v-if="!disabled" class="remove-icon" @click="removeRow(idx)" />
        </div>
        <div v-if="row.action === 'swipe'" class="coords-grid">
          <a-input-number v-model:value="row.x1" size="small" :min="0" addon-before="X1" :disabled="disabled" @change="emitRows" />
          <a-input-number v-model:value="row.y1" size="small" :min="0" addon-before="Y1" :disabled="disabled" @change="emitRows" />
          <a-input-number v-model:value="row.x2" size="small" :min="0" addon-before="X2" :disabled="disabled" @change="emitRows" />
          <a-input-number v-model:value="row.y2" size="small" :min="0" addon-before="Y2" :disabled="disabled" @change="emitRows" />
        </div>
        <div v-else class="coords-grid coords-tap">
          <a-input-number v-model:value="row.x" size="small" :min="0" addon-before="X" :disabled="disabled" @change="emitRows" />
          <a-input-number v-model:value="row.y" size="small" :min="0" addon-before="Y" :disabled="disabled" @change="emitRows" />
        </div>
      </div>

      <a-button v-if="!disabled" type="dashed" size="small" block @click="addPreset('swipe_up')">
        <PlusOutlined /> {{ t('fluency_editor.add_stage') }}
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
      <div v-if="rawInvalid" class="json-error">{{ t('fluency_editor.invalid_json_hint') }}</div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'
import { message } from 'ant-design-vue'
import { MinusCircleOutlined, PlusOutlined } from '@ant-design/icons-vue'
import { useI18n } from 'vue-i18n'
import {
  parseFluencyStagesText,
  serializeFluencyStages,
  type FluencyStageRow,
} from '@/utils/fluencyStages'

const props = withDefaults(
  defineProps<{
    value?: string
    rows?: number
    placeholder?: string
    disabled?: boolean
  }>(),
  {
    value: '',
    rows: 4,
    placeholder: '',
    disabled: false,
  },
)

const emit = defineEmits<{ 'update:value': [v: string] }>()
const { t } = useI18n()

const mode = ref<'visual' | 'raw'>('visual')
const rawText = ref(props.value ?? '')
const rows = ref<FluencyStageRow[]>([])
const rawInvalid = ref(false)

watch(
  () => props.value,
  (nextValue, prevValue) => {
    const normalized = nextValue ?? ''
    if (prevValue !== undefined && normalized === rawText.value) {
      return
    }
    rawText.value = normalized
    const parsed = parseFluencyStagesText(normalized)
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
  const serialized = serializeFluencyStages(rows.value)
  rawText.value = serialized
  rawInvalid.value = false
  emit('update:value', serialized)
}

function handleRawChange() {
  const parsed = parseFluencyStagesText(rawText.value)
  rawInvalid.value = !parsed.valid
  if (parsed.valid) rows.value = parsed.rows
  emit('update:value', rawText.value)
}

function switchMode(nextMode: 'visual' | 'raw') {
  if (nextMode === mode.value) return
  if (nextMode === 'visual') {
    const parsed = parseFluencyStagesText(rawText.value)
    if (!parsed.valid) {
      message.warning(t('fluency_editor.invalid_json_hint'))
      return
    }
    rows.value = parsed.rows
    rawInvalid.value = false
  }
  mode.value = nextMode
}

function addPreset(preset: 'swipe_up' | 'swipe_down' | 'tap_center') {
  const idx = rows.value.length + 1
  if (preset === 'swipe_down') {
    rows.value.push({
      name: `${t('fluency_editor.preset_swipe_down')}_${idx}`,
      action: 'swipe',
      duration_seconds: 5,
      x1: 540,
      y1: 500,
      x2: 540,
      y2: 1500,
      x: 540,
      y: 1000,
    })
  } else if (preset === 'tap_center') {
    rows.value.push({
      name: `${t('fluency_editor.preset_tap_center')}_${idx}`,
      action: 'tap',
      duration_seconds: 3,
      x1: 540,
      y1: 1400,
      x2: 540,
      y2: 400,
      x: 540,
      y: 1000,
    })
  } else {
    rows.value.push({
      name: `${t('fluency_editor.preset_swipe_up')}_${idx}`,
      action: 'swipe',
      duration_seconds: 5,
      x1: 540,
      y1: 1500,
      x2: 540,
      y2: 500,
      x: 540,
      y: 1000,
    })
  }
  emitRows()
}

function removeRow(idx: number) {
  rows.value.splice(idx, 1)
  emitRows()
}
</script>

<style scoped>
.fluency-stages-editor {
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
  flex-wrap: wrap;
  gap: 6px;
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

.preset-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 2px;
}

.visual-body {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.empty-hint {
  font-size: 12px;
  color: var(--c-text-tertiary);
}

.stage-card {
  padding: 8px;
  border-radius: var(--radius-sm);
  background: var(--c-bg-elevated);
  border: 1px solid var(--c-border-subtle);
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.stage-head {
  display: flex;
  align-items: center;
  gap: 6px;
}

.stage-name {
  flex: 1;
}

.coords-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(70px, 1fr));
  gap: 6px;
}

.coords-grid.coords-tap {
  grid-template-columns: repeat(2, minmax(90px, 1fr));
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
