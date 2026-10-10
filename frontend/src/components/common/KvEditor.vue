<template>
  <div class="kv-editor">
    <!-- 顶部预设快捷操作栏 -->
    <div v-if="presetKind !== 'none'" class="kv-toolbar">
      <span class="kv-hint-tag">
        {{ presetKind === 'headers' ? t('api_scenario.headers_presets_hint') : t('api_scenario.params_presets_hint') }}
      </span>

      <div class="kv-toolbar-actions">
        <a-dropdown :trigger="['click']">
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
            <span>{{ t('api_scenario.preset_dropdown_label') }}</span>
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
        @change="handleRowChange"
      />

      <!-- Value 输入框 (根据当前 Key 智能推荐选项) -->
      <a-auto-complete
        v-model:value="row.value"
        :options="getValueOptions(row.key)"
        :placeholder="t('common.value')"
        class="kv-input kv-val-input"
        @change="handleRowChange"
      />

      <MinusCircleOutlined class="kv-remove" @click="removeRow(i)" />
    </div>

    <a-button type="dashed" block size="small" class="add-row-btn" @click="addRow">
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

interface PresetItem {
  id: string
  label: string
  preview: string
  pairs: Array<{ key: string; value: string }>
}

const props = withDefaults(
  defineProps<{
    value: Record<string, string>
    presetKind?: 'headers' | 'params' | 'cookies' | 'none'
  }>(),
  {
    presetKind: 'none',
  },
)

const emit = defineEmits<{ 'update:value': [v: Record<string, string>] }>()
const { t } = useI18n()

interface Row {
  key: string
  value: string
}
const rows = ref<Row[]>([])

watch(
  () => props.value,
  (v) => {
    rows.value = Object.entries(v ?? {}).map(([key, value]) => ({ key, value }))
    if (!rows.value.length) rows.value.push({ key: '', value: '' })
  },
  { immediate: true },
)

const hasActiveRows = computed(() => {
  return rows.value.some((r) => r.key.trim() || r.value.trim())
})

// ---------------- 常用预设定义 ----------------
const HEADER_PRESETS: PresetItem[] = [
  {
    id: 'json',
    label: 'JSON 请求头 (Content-Type: application/json)',
    preview: 'Content-Type: application/json',
    pairs: [{ key: 'Content-Type', value: 'application/json' }],
  },
  {
    id: 'bearer_token',
    label: 'Bearer 鉴权头 (Authorization: Bearer {{token}})',
    preview: 'Authorization: Bearer {{token}}',
    pairs: [{ key: 'Authorization', value: 'Bearer {{token}}' }],
  },
  {
    id: 'form',
    label: '表单提交头 (application/x-www-form-urlencoded)',
    preview: 'Content-Type: application/x-www-form-urlencoded',
    pairs: [{ key: 'Content-Type', value: 'application/x-www-form-urlencoded' }],
  },
  {
    id: 'accept_json',
    label: '接收格式 (Accept: application/json)',
    preview: 'Accept: application/json',
    pairs: [{ key: 'Accept', value: 'application/json' }],
  },
  {
    id: 'csrf_ajax',
    label: 'AJAX / CSRF (X-Requested-With: XMLHttpRequest)',
    preview: 'X-Requested-With: XMLHttpRequest',
    pairs: [{ key: 'X-Requested-With', value: 'XMLHttpRequest' }],
  },
  {
    id: 'no_cache',
    label: '禁用缓存 (Cache-Control: no-cache)',
    preview: 'Cache-Control: no-cache',
    pairs: [{ key: 'Cache-Control', value: 'no-cache' }],
  },
  {
    id: 'user_agent',
    label: '标准客户端 (User-Agent)',
    preview: 'User-Agent: Mozilla/5.0...',
    pairs: [{ key: 'User-Agent', value: 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36' }],
  },
]

const PARAM_PRESETS: PresetItem[] = [
  {
    id: 'pagination',
    label: '分页参数模板 (page=1, page_size=20)',
    preview: 'page=1, page_size=20',
    pairs: [
      { key: 'page', value: '1' },
      { key: 'page_size', value: '20' },
    ],
  },
  {
    id: 'sorting',
    label: '排序规则参数 (sort_by=created_at, order=desc)',
    preview: 'sort_by=created_at, order=desc',
    pairs: [
      { key: 'sort_by', value: 'created_at' },
      { key: 'order', value: 'desc' },
    ],
  },
  {
    id: 'search',
    label: '关键字检索 (keyword=)',
    preview: 'keyword=',
    pairs: [{ key: 'keyword', value: '' }],
  },
  {
    id: 'status',
    label: '状态过滤 (status=active)',
    preview: 'status=active',
    pairs: [{ key: 'status', value: 'active' }],
  },
  {
    id: 'timerange',
    label: '起止时间范围 (start_time, end_time)',
    preview: 'start_time=..., end_time=...',
    pairs: [
      { key: 'start_time', value: '{{start_time}}' },
      { key: 'end_time', value: '{{end_time}}' },
    ],
  },
]

const currentPresets = computed(() => {
  if (props.presetKind === 'headers') return HEADER_PRESETS
  if (props.presetKind === 'params') return PARAM_PRESETS
  return []
})

// ---------------- 常用候选词定义 ----------------
const HEADER_KEY_SUGGESTIONS = [
  'Content-Type',
  'Authorization',
  'Accept',
  'User-Agent',
  'X-Requested-With',
  'Cache-Control',
  'X-Token',
  'Origin',
  'Referer',
  'Cookie',
]

const PARAM_KEY_SUGGESTIONS = [
  'page',
  'page_size',
  'limit',
  'offset',
  'keyword',
  'sort_by',
  'order',
  'status',
  'start_time',
  'end_time',
  'id',
]

function getKeyOptions(): Array<{ value: string }> {
  if (props.presetKind === 'headers') {
    return HEADER_KEY_SUGGESTIONS.map((k) => ({ value: k }))
  }
  if (props.presetKind === 'params') {
    return PARAM_KEY_SUGGESTIONS.map((k) => ({ value: k }))
  }
  return []
}

function getValueOptions(key: string): Array<{ value: string }> {
  const normKey = (key || '').trim().toLowerCase()
  if (props.presetKind === 'headers') {
    if (normKey === 'content-type') {
      return [
        { value: 'application/json' },
        { value: 'application/x-www-form-urlencoded' },
        { value: 'multipart/form-data' },
        { value: 'application/xml' },
        { value: 'text/plain' },
      ]
    }
    if (normKey === 'authorization') {
      return [
        { value: 'Bearer {{token}}' },
        { value: 'Bearer {{access_token}}' },
        { value: 'Basic {{credentials}}' },
      ]
    }
    if (normKey === 'accept') {
      return [{ value: 'application/json' }, { value: '*/*' }, { value: 'text/html' }]
    }
    if (normKey === 'x-requested-with') {
      return [{ value: 'XMLHttpRequest' }]
    }
    if (normKey === 'cache-control') {
      return [{ value: 'no-cache' }, { value: 'no-store' }, { value: 'max-age=0' }]
    }
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
  }

  return []
}

function handleRowChange() {
  emit('update:value', toObject())
}

function addRow() {
  rows.value.push({ key: '', value: '' })
}

function removeRow(i: number) {
  rows.value.splice(i, 1)
  if (!rows.value.length) rows.value.push({ key: '', value: '' })
  emit('update:value', toObject())
}

function handleApplyPreset({ key }: { key: string | number }) {
  const preset = currentPresets.value.find((p) => p.id === String(key))
  if (!preset) return

  preset.pairs.forEach((pair) => {
    // 检查是否有空的行，如果有则直接替换
    const emptyIdx = rows.value.findIndex((r) => !r.key.trim())
    if (emptyIdx > -1) {
      rows.value[emptyIdx] = { key: pair.key, value: pair.value }
    } else {
      // 检查是否已经存在该 key，若存在则更新
      const existIdx = rows.value.findIndex((r) => r.key.toLowerCase() === pair.key.toLowerCase())
      if (existIdx > -1) {
        rows.value[existIdx].value = pair.value
      } else {
        rows.value.push({ key: pair.key, value: pair.value })
      }
    }
  })

  emit('update:value', toObject())
}

function clearAllRows() {
  rows.value = [{ key: '', value: '' }]
  emit('update:value', {})
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
