<template>
  <div class="kv-editor">
    <!-- 顶部预设快捷操作栏 -->
    <div v-if="!disabled && (presetKind !== 'none' || showDynamicVars)" class="kv-toolbar">
      <span class="kv-hint-tag">
        {{ toolbarHint }}
      </span>

      <div class="kv-toolbar-actions">
        <a-dropdown v-if="currentPresets.length" :trigger="['click']">
          <template #overlay>
            <a-menu @click="handleApplyPreset">
              <a-menu-item v-for="item in currentPresets" :key="item.id">
                <div class="preset-menu-item">
                  <span class="preset-label">{{ item.label }}</span>
                  <code class="preset-code">{{ item.preview }}</code>
                </div>
              </a-menu-item>
            </a-menu>
          </template>
          <a-button size="small" class="preset-btn">
            <ThunderboltOutlined />
            <span>{{ presetButtonLabel }}</span>
            <DownOutlined class="dropdown-arrow" />
          </a-button>
        </a-dropdown>

        <a-dropdown v-if="presetKind !== 'none' || showDynamicVars" :trigger="['click']">
          <template #overlay>
            <a-menu @click="handleInsertDynamicVar">
              <a-menu-item v-for="dv in DYNAMIC_VARIABLE_PRESETS" :key="dv.id">
                <div class="preset-menu-item">
                  <span class="preset-label">{{ dv.label }}</span>
                  <code class="preset-code">{{ dv.token }}</code>
                </div>
              </a-menu-item>
            </a-menu>
          </template>
          <a-button size="small" class="preset-btn">
            <span>{{ t('smart_json.dynamic_vars') }}</span>
            <DownOutlined class="dropdown-arrow" />
          </a-button>
        </a-dropdown>

        <a-button
          v-if="hasActiveRows"
          type="text"
          danger
          size="small"
          class="clear-btn"
          @click="clearAllRows"
        >
          {{ t('api_scenario.clear_all') }}
        </a-button>
      </div>
    </div>

    <!-- 键值对列表行 -->
    <div v-for="(row, i) in rows" :key="i" class="kv-row">
      <!-- Key 输入框 (支持自动补全) -->
      <a-auto-complete
        v-model:value="row.key"
        :options="getKeyOptions()"
        :placeholder="t('common.key')"
        class="kv-input kv-key-input"
        :disabled="disabled"
        @change="handleRowChange"
      />

      <!-- Value 输入框 (根据当前 Key 智能推荐选项) -->
      <a-auto-complete
        v-model:value="row.value"
        :options="getValueOptions(row.key)"
        :placeholder="t('common.value')"
        class="kv-input kv-val-input"
        :disabled="disabled"
        @change="handleRowChange"
      />

      <MinusCircleOutlined v-if="!disabled" class="kv-remove" @click="removeRow(i)" />
    </div>

    <a-button v-if="!disabled" type="dashed" block size="small" class="add-row-btn" @click="addRow">
      <PlusOutlined /> {{ t('common.add') }}
    </a-button>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import {
  PlusOutlined,
  MinusCircleOutlined,
  ThunderboltOutlined,
  DownOutlined,
} from '@ant-design/icons-vue'
import { useI18n } from 'vue-i18n'
import {
  COOKIE_KEY_SUGGESTIONS,
  COOKIE_PRESETS,
  DYNAMIC_VARIABLE_PRESETS,
  HEADER_KEY_SUGGESTIONS,
  HEADER_PRESETS,
  HEADER_VALUE_SUGGESTIONS,
  PARAM_KEY_SUGGESTIONS,
  PARAM_PRESETS,
} from '@/utils/apiTemplates'

const props = withDefaults(
  defineProps<{
    value: Record<string, string>
    presetKind?: 'headers' | 'params' | 'cookies' | 'none'
    showDynamicVars?: boolean
    disabled?: boolean
  }>(),
  {
    presetKind: 'none',
    showDynamicVars: false,
    disabled: false,
  },
)

const emit = defineEmits<{ 'update:value': [v: Record<string, string>] }>()
const { t } = useI18n()

interface Row {
  key: string
  value: string
}
const rows = ref<Row[]>([])
let internalSync = false

function recordsEqual(a: Record<string, string>, b: Record<string, string>): boolean {
  const keysA = Object.keys(a)
  const keysB = Object.keys(b)
  if (keysA.length !== keysB.length) return false
  return keysA.every((k) => Object.prototype.hasOwnProperty.call(b, k) && a[k] === b[k])
}

watch(
  () => props.value,
  (v) => {
    if (internalSync) {
      internalSync = false
      return
    }
    const incoming = v ?? {}
    if (rows.value.length > 0 && recordsEqual(toObject(), incoming)) {
      return
    }
    rows.value = Object.entries(incoming).map(([key, value]) => ({ key, value }))
    if (!rows.value.length) rows.value.push({ key: '', value: '' })
  },
  { immediate: true },
)

const hasActiveRows = computed(() => {
  return rows.value.some((r) => r.key.trim() || r.value.trim())
})

const currentPresets = computed(() => {
  if (props.presetKind === 'headers') return HEADER_PRESETS
  if (props.presetKind === 'params') return PARAM_PRESETS
  if (props.presetKind === 'cookies') return COOKIE_PRESETS
  return []
})

const toolbarHint = computed(() => {
  if (props.presetKind === 'headers') return t('api_scenario.headers_presets_hint')
  if (props.presetKind === 'cookies') return t('api_scenario.cookies_presets_hint')
  if (props.presetKind === 'params') return t('api_scenario.params_presets_hint')
  return t('smart_json.dynamic_vars')
})

const presetButtonLabel = computed(() => {
  if (props.presetKind === 'cookies') return t('api_scenario.cookies_preset_dropdown_label')
  return t('api_scenario.preset_dropdown_label')
})

function getKeyOptions(): Array<{ value: string }> {
  if (props.presetKind === 'headers') {
    return HEADER_KEY_SUGGESTIONS.map((k) => ({ value: k }))
  }
  if (props.presetKind === 'params') {
    return PARAM_KEY_SUGGESTIONS.map((k) => ({ value: k }))
  }
  if (props.presetKind === 'cookies') {
    return COOKIE_KEY_SUGGESTIONS.map((k) => ({ value: k }))
  }
  return []
}

function getValueOptions(key: string): Array<{ value: string }> {
  const normKey = (key || '').trim().toLowerCase()
  const dynamicOptions = DYNAMIC_VARIABLE_PRESETS.slice(0, 6).map((d) => ({ value: d.token }))
  if (props.presetKind === 'headers') {
    if (normKey === 'content-type') {
      return [
        { value: 'application/json' },
        { value: 'application/x-www-form-urlencoded' },
        { value: 'multipart/form-data' },
        { value: 'application/xml' },
        { value: 'text/plain; charset=utf-8' },
      ]
    }
    if (normKey === 'authorization') {
      return [
        { value: 'Bearer {{token}}' },
        { value: 'Bearer {{access_token}}' },
        { value: 'Basic {{basic_token}}' },
      ]
    }
    if (normKey === 'accept') {
      return [{ value: 'application/json' }, { value: '*/*' }, { value: 'text/html' }]
    }
    if (normKey === 'x-request-id' || normKey === 'x-trace-id' || normKey === 'idempotency-key') {
      return [{ value: '{{$uuid}}' }, { value: '{{$uuid_hex}}' }]
    }
    if (normKey === 'cache-control') {
      return [{ value: 'no-cache' }, { value: 'no-store' }, { value: 'max-age=0' }]
    }
    return HEADER_VALUE_SUGGESTIONS.map((v) => ({ value: v }))
  }

  if (props.presetKind === 'cookies') {
    if (normKey === 'session_id') return [{ value: '{{session_id}}' }, { value: '{{$uuid_hex}}' }]
    if (normKey === 'csrf_token') return [{ value: '{{csrf_token}}' }, { value: '{{$random_str(16)}}' }]
    if (normKey === 'auth_token') return [{ value: '{{token}}' }]
    if (normKey === 'locale') return [{ value: 'zh-CN' }, { value: 'en-US' }]
    return [{ value: '{{session_id}}' }, { value: '{{token}}' }, { value: '{{$uuid_hex}}' }]
  }

  if (props.presetKind === 'params') {
    if (normKey === 'page') return [{ value: '1' }]
    if (normKey === 'page_size' || normKey === 'limit') {
      return [{ value: '10' }, { value: '20' }, { value: '50' }, { value: '100' }]
    }
    if (normKey === 'order') return [{ value: 'desc' }, { value: 'asc' }]
    if (normKey === 'status') {
      return [{ value: 'active' }, { value: 'inactive' }, { value: 'pending' }, { value: 'all' }]
    }
    if (normKey === 'start_date' || normKey === 'end_date') {
      return [{ value: '{{$date}}' }, { value: '{{$iso_now}}' }]
    }
    return dynamicOptions
  }

  return []
}

function emitCurrentValue(nextValue = toObject()) {
  internalSync = true
  emit('update:value', nextValue)
  queueMicrotask(() => {
    internalSync = false
  })
}

function handleRowChange() {
  emitCurrentValue()
}

function addRow() {
  rows.value.push({ key: '', value: '' })
}

function removeRow(i: number) {
  rows.value.splice(i, 1)
  if (!rows.value.length) rows.value.push({ key: '', value: '' })
  emitCurrentValue()
}

function handleApplyPreset({ key }: { key: string | number }) {
  const preset = currentPresets.value.find((p) => p.id === String(key))
  if (!preset) return

  Object.entries(preset.entries).forEach(([pairKey, pairValue]) => {
    const emptyIdx = rows.value.findIndex((r) => !r.key.trim())
    if (emptyIdx > -1) {
      rows.value[emptyIdx] = { key: pairKey, value: pairValue }
    } else {
      const existIdx = rows.value.findIndex((r) => r.key.toLowerCase() === pairKey.toLowerCase())
      if (existIdx > -1) {
        rows.value[existIdx].value = pairValue
      } else {
        rows.value.push({ key: pairKey, value: pairValue })
      }
    }
  })

  emitCurrentValue()
}

function handleInsertDynamicVar({ key }: { key: string | number }) {
  const preset = DYNAMIC_VARIABLE_PRESETS.find((d) => d.id === String(key))
  if (!preset) return

  const emptyRowIdx = rows.value.findIndex((r) => !r.key.trim() && !r.value.trim())
  if (emptyRowIdx > -1) {
    rows.value[emptyRowIdx] = { key: preset.suggestedKey, value: preset.token }
  } else {
    const missingValIdx = rows.value.findIndex((r) => r.key.trim() && !r.value.trim())
    if (missingValIdx > -1) {
      rows.value[missingValIdx].value = preset.token
    } else {
      rows.value.push({ key: preset.suggestedKey, value: preset.token })
    }
  }

  emitCurrentValue()
}

function clearAllRows() {
  rows.value = [{ key: '', value: '' }]
  emitCurrentValue({})
}

function toObject(): Record<string, string> {
  return Object.fromEntries(rows.value.filter((r) => r.key.trim()).map((r) => [r.key.trim(), r.value]))
}
</script>

<style scoped>
.kv-editor {
  display: flex;
  flex-direction: column;
}

.kv-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 8px;
  padding: 4px 8px;
  background: var(--c-bg-subtle, #f8fafc);
  border: 1px dashed var(--c-border, #e2e8f0);
  border-radius: 6px;
}

.kv-hint-tag {
  font-size: 11px;
  font-weight: 600;
  color: var(--c-text-secondary, #64748b);
}

.kv-toolbar-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}

.preset-btn {
  font-size: 11px;
  display: inline-flex;
  align-items: center;
  gap: 4px;
  font-weight: 600;
  color: var(--c-primary, #1677ff);
}

.dropdown-arrow {
  font-size: 9px;
}

.clear-btn {
  font-size: 11px;
  padding: 0 4px;
}

.preset-menu-item {
  display: flex;
  flex-direction: column;
  gap: 2px;
  padding: 2px 0;
}

.preset-label {
  font-size: 12px;
  font-weight: 600;
  color: var(--c-text, #1e293b);
}

.preset-code {
  font-size: 11px;
  color: var(--c-text-tertiary, #94a3b8);
  font-family: monospace;
}

.kv-row {
  display: flex;
  gap: 8px;
  margin-bottom: 8px;
  align-items: center;
}

.kv-key-input {
  width: 220px;
  flex-shrink: 0;
}

.kv-val-input {
  flex: 1;
}

.kv-remove {
  color: #ff4d4f;
  cursor: pointer;
  flex-shrink: 0;
  font-size: 14px;
  padding: 4px;
  transition: transform 0.15s ease;
}

.kv-remove:hover {
  transform: scale(1.15);
}

.add-row-btn {
  margin-top: 4px;
  border-style: dashed;
}
</style>
