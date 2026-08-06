<template>
  <div class="variable-reference-input">
    <a-auto-complete
      v-model:value="inputValue"
      :options="suggestions"
      :filter-option="false"
      :placeholder="placeholder"
      allow-clear
      class="variable-input"
      @search="handleSearch"
      @focus="rememberCaret"
      @click="rememberCaret"
      @keyup="rememberCaret"
    >
      <template #option="option">
        <div class="variable-suggestion">
          <code>{{ option.label }}</code>
          <span>{{ option.environmentLabel }}</span>
        </div>
      </template>
    </a-auto-complete>

    <a-popover v-model:open="pickerOpen" trigger="click" placement="bottomRight">
      <template #content>
        <div class="variable-picker">
          <div class="variable-picker-title">{{ t('case.lowcode_editor.variable_picker.title') }}</div>
          <div v-if="loading" class="variable-picker-state">
            {{ t('case.lowcode_editor.variable_picker.loading') }}
          </div>
          <div v-else-if="!variables.length" class="variable-picker-state">
            {{ t('case.lowcode_editor.variable_picker.empty') }}
          </div>
          <template v-else>
            <button
              v-for="variable in variables"
              :key="variable.key"
              type="button"
              class="variable-picker-item"
              @mousedown.prevent
              @click="insertVariable(variable.key)"
            >
              <code>{{ variable.token }}</code>
              <span>{{ variable.environmentLabel }}</span>
            </button>
          </template>
        </div>
      </template>
      <a-button
        class="variable-picker-trigger"
        type="text"
        size="small"
        :aria-label="t('case.lowcode_editor.variable_picker.open')"
      >
        <CodeOutlined />
      </a-button>
    </a-popover>
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, ref } from 'vue'
import { CodeOutlined } from '@ant-design/icons-vue'
import { useI18n } from 'vue-i18n'

export type VariableReference = {
  key: string
  token: string
  environmentLabel: string
}

const props = withDefaults(defineProps<{
  modelValue: string
  variables: VariableReference[]
  loading?: boolean
  placeholder?: string
}>(), {
  loading: false,
  placeholder: undefined,
})

const emit = defineEmits<{
  'update:modelValue': [value: string]
}>()

const { t } = useI18n()
const pickerOpen = ref(false)
const caretPosition = ref<number | null>(null)

const inputValue = computed({
  get: () => props.modelValue,
  set: (value: string) => emit('update:modelValue', value ?? ''),
})

const activeVariableQuery = computed(() => {
  const match = inputValue.value.match(/\{\{([A-Za-z_][A-Za-z0-9_]*)?$/)
  if (!match || match.index === undefined) return null
  return {
    prefix: inputValue.value.slice(0, match.index),
    query: match[1] ?? '',
  }
})

const suggestions = computed(() => {
  const activeQuery = activeVariableQuery.value
  if (!activeQuery) return []

  const query = activeQuery.query.toLowerCase()
  return props.variables
    .filter((variable) => variable.key.toLowerCase().includes(query))
    .map((variable) => ({
      value: `${activeQuery.prefix}${variable.token}`,
      label: variable.token,
      environmentLabel: variable.environmentLabel,
    }))
})

function handleSearch() {
  rememberCaret()
}

function rememberCaret() {
  void nextTick(() => {
    const input = document.activeElement instanceof HTMLInputElement
      ? document.activeElement
      : null
    if (input) {
      caretPosition.value = input.selectionStart
    }
  })
}

function insertVariable(key: string) {
  const source = inputValue.value
  const position = Math.min(caretPosition.value ?? source.length, source.length)
  const before = source.slice(0, position)
  const after = source.slice(position)
  const match = before.match(/\{\{[A-Za-z_][A-Za-z0-9_]*$/)
  const token = `{{${key}}}`
  const start = match?.index ?? (before.endsWith('{{') ? position - 2 : position)
  const nextValue = `${before.slice(0, start)}${token}${after}`
  const nextCaret = start + token.length

  emit('update:modelValue', nextValue)
  pickerOpen.value = false
  void nextTick(() => {
    const input = document.activeElement instanceof HTMLInputElement
      ? document.activeElement
      : null
    if (input) {
      input.focus()
      input.setSelectionRange(nextCaret, nextCaret)
      caretPosition.value = nextCaret
    }
  })
}
</script>

<style scoped>
.variable-reference-input {
  display: flex;
  align-items: center;
  gap: 4px;
  width: 100%;
}

.variable-input {
  flex: 1;
  min-width: 0;
}

.variable-picker-trigger {
  flex: 0 0 auto;
  color: var(--c-primary, #635bff);
}

.variable-suggestion,
.variable-picker-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
}

.variable-suggestion code,
.variable-picker-item code {
  color: var(--c-primary, #635bff);
  font-size: 12px;
}

.variable-suggestion span,
.variable-picker-item span {
  color: var(--c-text-tertiary, #8c8c8c);
  font-size: 11px;
}

.variable-picker {
  width: 250px;
  max-height: 280px;
  overflow-y: auto;
}

.variable-picker-title {
  margin-bottom: 6px;
  color: var(--c-text-secondary, #595959);
  font-size: 12px;
  font-weight: 600;
}

.variable-picker-state {
  padding: 12px 4px;
  color: var(--c-text-tertiary, #8c8c8c);
  font-size: 12px;
  text-align: center;
}

.variable-picker-item {
  width: 100%;
  padding: 7px 4px;
  border: 0;
  border-radius: 4px;
  background: transparent;
  cursor: pointer;
  text-align: left;
}

.variable-picker-item:hover {
  background: var(--c-primary-soft, #f0efff);
}
</style>
