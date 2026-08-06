<template>
  <div class="kv-editor">
    <div v-for="(row, i) in rows" :key="i" class="kv-row">
      <a-input
        v-model:value="row.key"
        :placeholder="t('common.key')"
        class="kv-input"
        @change="emit('update:value', toObject())"
      />
      <a-input
        v-model:value="row.value"
        :placeholder="t('common.value')"
        class="kv-input"
        @change="emit('update:value', toObject())"
      />
      <MinusCircleOutlined class="kv-remove" @click="removeRow(i)" />
    </div>
    <a-button type="dashed" block size="small" @click="addRow">
      <PlusOutlined /> {{ t('common.add') }}
    </a-button>
  </div>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'
import { PlusOutlined, MinusCircleOutlined } from '@ant-design/icons-vue'
import { useI18n } from 'vue-i18n'

const props = defineProps<{ value: Record<string, string> }>()
const emit = defineEmits<{ 'update:value': [v: Record<string, string>] }>()
const { t } = useI18n()

interface Row { key: string; value: string }
const rows = ref<Row[]>([])

watch(
  () => props.value,
  (v) => {
    rows.value = Object.entries(v ?? {}).map(([key, value]) => ({ key, value }))
    if (!rows.value.length) rows.value.push({ key: '', value: '' })
  },
  { immediate: true },
)

function addRow() { rows.value.push({ key: '', value: '' }) }
function removeRow(i: number) {
  rows.value.splice(i, 1)
  emit('update:value', toObject())
}
function toObject(): Record<string, string> {
  return Object.fromEntries(rows.value.filter(r => r.key).map(r => [r.key, r.value]))
}
</script>

<style scoped>
.kv-row {
  display: flex;
  gap: 8px;
  margin-bottom: 8px;
  align-items: center;
}
.kv-input { flex: 1; }
.kv-remove { color: #ff4d4f; cursor: pointer; flex-shrink: 0; }
</style>
