<template>
  <div class="perf-options-editor" :class="{ 'is-compact': compact }">
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
          {{ t('perf_options_editor.mode_visual') }}
        </button>
        <button
          type="button"
          role="tab"
          class="mode-pill"
          :class="{ 'is-active': mode === 'raw' }"
          :aria-selected="mode === 'raw'"
          @click="switchMode('raw')"
        >
          {{ t('perf_options_editor.mode_raw') }}
        </button>
      </div>
      <span v-if="form.extraKeys.length && mode === 'visual'" class="extra-hint">
        {{ t('perf_options_editor.extra_preserved', { keys: form.extraKeys.join(', ') }) }}
      </span>
    </div>

    <div v-if="mode === 'visual'" class="visual-panel">
      <a-row :gutter="10">
        <a-col :xs="12" :sm="8">
          <div class="field-item">
            <label>{{ t('perf_options_editor.vus') }}</label>
            <a-input-number
              v-model:value="form.vus"
              :min="1"
              :max="100000"
              size="small"
              style="width: 100%"
              :disabled="disabled"
              placeholder="10"
              @change="syncFormToRaw"
            />
          </div>
        </a-col>
        <a-col :xs="12" :sm="8">
          <div class="field-item">
            <label>{{ t('perf_options_editor.duration') }}</label>
            <a-input
              v-model:value="form.duration"
              size="small"
              :disabled="disabled"
              :placeholder="t('perf_options_editor.duration_placeholder')"
              @change="syncFormToRaw"
            />
          </div>
        </a-col>
        <a-col :xs="12" :sm="8">
          <div class="field-item">
            <label>{{ executor === 'locust' ? t('perf_options_editor.spawn_rate') : t('perf_options_editor.iterations') }}</label>
            <a-input-number
              v-if="executor === 'locust'"
              v-model:value="form.spawn_rate"
              :min="0.1"
              :step="1"
              size="small"
              style="width: 100%"
              :disabled="disabled"
              placeholder="1"
              @change="syncFormToRaw"
            />
            <a-input-number
              v-else
              v-model:value="form.iterations"
              :min="1"
              size="small"
              style="width: 100%"
              :disabled="disabled"
              @change="syncFormToRaw"
            />
          </div>
        </a-col>
      </a-row>

      <a-row :gutter="10">
        <a-col :xs="24" :sm="10">
          <div class="field-item">
            <label>{{ t('perf_options_editor.host') }}</label>
            <a-input
              v-model:value="form.host"
              size="small"
              :disabled="disabled"
              :placeholder="t('perf_options_editor.host_placeholder')"
              @change="syncFormToRaw"
            />
          </div>
        </a-col>
        <a-col :xs="12" :sm="7">
          <div class="field-item">
            <label>{{ t('perf_options_editor.max_p95_ms') }}</label>
            <a-input-number
              v-model:value="form.max_p95_ms"
              :min="0"
              size="small"
              style="width: 100%"
              :disabled="disabled"
              placeholder="500"
              @change="syncFormToRaw"
            />
          </div>
        </a-col>
        <a-col :xs="12" :sm="7">
          <div class="field-item">
            <label>{{ t('perf_options_editor.max_error_rate') }}</label>
            <a-input-number
              v-model:value="form.max_error_rate"
              :min="0"
              :max="100"
              :step="0.5"
              size="small"
              style="width: 100%"
              :disabled="disabled"
              placeholder="1"
              @change="syncFormToRaw"
            />
          </div>
        </a-col>
      </a-row>

      <div class="field-item">
        <label>{{ t('perf_options_editor.env_vars') }}</label>
        <KvEditor :value="form.env" :disabled="disabled" @update:value="updateEnv" />
      </div>
    </div>

    <div v-else class="raw-panel">
      <a-textarea
        v-model:value="rawText"
        :rows="rows"
        :disabled="disabled"
        class="mono-textarea"
        @change="handleRawChange"
      />
      <div v-if="parseError" class="json-error">{{ parseError }}</div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { reactive, ref, watch } from 'vue'
import { message } from 'ant-design-vue'
import { useI18n } from 'vue-i18n'
import KvEditor from '@/components/common/KvEditor.vue'
import {
  mergePerformanceOptionsText,
  parsePerformanceOptionsText,
  type PerformanceOptionsFormState,
} from '@/utils/performanceOptions'

const props = withDefaults(
  defineProps<{
    value?: string
    executor?: string
    rows?: number
    disabled?: boolean
    compact?: boolean
  }>(),
  {
    value: '{}',
    executor: 'k6',
    rows: 6,
    disabled: false,
    compact: false,
  },
)

const emit = defineEmits<{ 'update:value': [v: string] }>()
const { t } = useI18n()

const mode = ref<'visual' | 'raw'>('visual')
const rawText = ref(props.value ?? '{}')
const parseError = ref('')

const form = reactive<PerformanceOptionsFormState>({
  vus: undefined,
  duration: '',
  spawn_rate: undefined,
  iterations: undefined,
  host: '',
  max_p95_ms: undefined,
  max_error_rate: undefined,
  env: {},
  extraKeys: [],
})

function applyExternalValue(next: string | undefined) {
  const normalized = next ?? '{}'
  rawText.value = normalized
  const result = parsePerformanceOptionsText(normalized)
  if (result.valid) {
    Object.assign(form, result.state)
    parseError.value = ''
    mode.value = 'visual'
  } else {
    parseError.value = result.error || t('perf_options_editor.invalid_json_hint')
    mode.value = 'raw'
  }
}

watch(
  () => props.value,
  (nextValue, prevValue) => {
    const normalized = nextValue ?? '{}'
    if (prevValue !== undefined && normalized === rawText.value) {
      return
    }
    applyExternalValue(normalized)
  },
  { immediate: true },
)

watch(
  () => props.executor,
  () => {
    if (!props.disabled && mode.value === 'visual' && !parseError.value) {
      syncFormToRaw()
    }
  },
)

function emitRaw(next: string) {
  rawText.value = next
  emit('update:value', next)
}

function syncFormToRaw() {
  const merged = mergePerformanceOptionsText(rawText.value, form, props.executor)
  parseError.value = ''
  emitRaw(merged)
}

function updateEnv(nextEnv: Record<string, string>) {
  form.env = { ...nextEnv }
  syncFormToRaw()
}

function handleRawChange() {
  const check = parsePerformanceOptionsText(rawText.value)
  parseError.value = check.valid ? '' : check.error || t('perf_options_editor.invalid_json_hint')
  emitRaw(rawText.value)
}

function switchMode(nextMode: 'visual' | 'raw') {
  if (nextMode === mode.value) return
  if (nextMode === 'visual') {
    const check = parsePerformanceOptionsText(rawText.value)
    if (!check.valid) {
      message.warning(t('perf_options_editor.invalid_json_hint'))
      return
    }
    Object.assign(form, check.state)
    parseError.value = ''
  }
  mode.value = nextMode
}
</script>

<style scoped>
.perf-options-editor {
  border: 1px solid var(--c-border);
  border-radius: var(--radius-md);
  background: var(--c-bg-body);
  padding: 10px 12px;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.perf-options-editor.is-compact {
  padding: 8px 10px;
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

.extra-hint {
  font-size: 11px;
  color: var(--c-text-tertiary);
}

.visual-panel {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.field-item {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.field-item label {
  font-size: 12px;
  color: var(--c-text-secondary);
  font-weight: 500;
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
