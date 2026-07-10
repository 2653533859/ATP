<template>
  <div class="healing-examples">
    <div class="toolbar">
      <h2>AI 自愈示例库</h2>
      <a-space>
        <a-input
          v-model:value="filters.error_fingerprint"
          allow-clear
          placeholder="错误特征"
          style="width: 220px"
          @press-enter="loadExamples"
        />
        <a-select
          v-model:value="filters.case_type"
          allow-clear
          placeholder="用例类型"
          style="width: 140px"
          :options="caseTypeOptions"
        />
        <a-select
          v-model:value="qualityFilter"
          style="width: 140px"
          :options="qualityOptions"
        />
        <a-button @click="loadExamples">刷新</a-button>
      </a-space>
    </div>

    <a-table
      :loading="loading"
      :data-source="examples"
      :columns="columns"
      :pagination="{ pageSize: 20 }"
      row-key="id"
    >
      <template #bodyCell="{ column, record }">
        <template v-if="column.key === 'case_type'">
          <a-tag color="blue">{{ record.case_type }}</a-tag>
        </template>
        <template v-else-if="column.key === 'marked_high_quality'">
          <a-switch
            :checked="record.marked_high_quality"
            size="small"
            @change="(checked: unknown) => toggleQuality(asExample(record), Boolean(checked))"
          />
        </template>
        <template v-else-if="column.key === 'suggestion_text'">
          <div class="suggestion">{{ record.suggestion_text }}</div>
        </template>
        <template v-else-if="column.key === 'step'">
          {{ stepName(asExample(record)) }}
        </template>
        <template v-else-if="column.key === 'action'">
          <a-button type="link" size="small" @click="openDetail(asExample(record))">详情</a-button>
          <a-popconfirm title="确认删除该示例？" @confirm="deleteExample(record.id)">
            <a-button type="link" size="small" danger>删除</a-button>
          </a-popconfirm>
        </template>
      </template>
    </a-table>

    <a-modal v-model:open="detailOpen" title="示例详情" width="760px" :footer="null">
      <template v-if="selected">
        <a-descriptions bordered size="small" :column="1">
          <a-descriptions-item label="错误特征">{{ selected.error_fingerprint }}</a-descriptions-item>
          <a-descriptions-item label="用例类型">{{ selected.case_type }}</a-descriptions-item>
          <a-descriptions-item label="来源步骤">{{ selected.source_step_result_id ?? '-' }}</a-descriptions-item>
        </a-descriptions>
        <h3>上下文</h3>
        <pre class="json-block">{{ JSON.stringify(selected.step_context_json, null, 2) }}</pre>
        <h3>建议</h3>
        <a-textarea v-model:value="detailSuggestion" :rows="6" />
        <div class="modal-actions">
          <a-button type="primary" @click="saveSuggestion">保存</a-button>
        </div>
      </template>
    </a-modal>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { message } from 'ant-design-vue'
import { aiHealingExampleApi, type HealingPromptExampleItem } from '@/api'
// a-table #bodyCell 的 record 是 Record<string, any>；数据源类型在此断言收窄
const asExample = (record: unknown) => record as HealingPromptExampleItem

const loading = ref(false)
const examples = ref<HealingPromptExampleItem[]>([])
const detailOpen = ref(false)
const selected = ref<HealingPromptExampleItem | null>(null)
const detailSuggestion = ref('')
const qualityFilter = ref<'all' | 'true' | 'false'>('all')

const filters = ref({
  error_fingerprint: '',
  case_type: undefined as string | undefined,
})

const caseTypeOptions = [
  { label: 'API', value: 'api' },
  { label: 'Web', value: 'web' },
  { label: 'Android', value: 'android' },
  { label: 'GraphQL', value: 'graphql' },
  { label: 'WebSocket', value: 'websocket' },
  { label: 'gRPC', value: 'grpc' },
]

const qualityOptions = [
  { label: '全部', value: 'all' },
  { label: '高质量', value: 'true' },
  { label: '未标注', value: 'false' },
]

const columns = computed(() => [
  { title: '错误特征', dataIndex: 'error_fingerprint', key: 'error_fingerprint', ellipsis: true },
  { title: '类型', key: 'case_type', width: 100 },
  { title: '步骤', key: 'step', width: 160, ellipsis: true },
  { title: '建议', key: 'suggestion_text', ellipsis: true },
  { title: '高质量', key: 'marked_high_quality', width: 100 },
  { title: '操作', key: 'action', width: 120 },
])

function stepName(record: HealingPromptExampleItem) {
  const value = record.step_context_json?.step_name
  return typeof value === 'string' && value ? value : '-'
}

function buildParams() {
  return {
    error_fingerprint: filters.value.error_fingerprint.trim() || undefined,
    case_type: filters.value.case_type,
    high_quality:
      qualityFilter.value === 'all' ? undefined : qualityFilter.value === 'true',
    limit: 100,
  }
}

async function loadExamples() {
  loading.value = true
  try {
    examples.value = await aiHealingExampleApi.list(buildParams())
  } catch (error) {
    message.error(error instanceof Error ? error.message : '加载失败')
  } finally {
    loading.value = false
  }
}

async function toggleQuality(record: HealingPromptExampleItem, checked: boolean) {
  try {
    await aiHealingExampleApi.update(record.id, { marked_high_quality: checked })
    record.marked_high_quality = checked
    message.success('已更新')
  } catch (error) {
    message.error(error instanceof Error ? error.message : '更新失败')
  }
}

function openDetail(record: HealingPromptExampleItem) {
  selected.value = record
  detailSuggestion.value = record.suggestion_text
  detailOpen.value = true
}

async function saveSuggestion() {
  if (!selected.value) return
  try {
    const updated = await aiHealingExampleApi.update(selected.value.id, {
      suggestion_text: detailSuggestion.value.trim(),
    })
    Object.assign(selected.value, updated)
    message.success('已保存')
  } catch (error) {
    message.error(error instanceof Error ? error.message : '保存失败')
  }
}

async function deleteExample(id: number) {
  try {
    await aiHealingExampleApi.delete(id)
    message.success('已删除')
    await loadExamples()
  } catch (error) {
    message.error(error instanceof Error ? error.message : '删除失败')
  }
}

onMounted(loadExamples)
</script>

<style scoped>
.healing-examples {
  display: flex;
  flex-direction: column;
  gap: 16px;
}
.toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
}
.toolbar h2 {
  margin: 0;
}
.suggestion {
  max-width: 520px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.json-block {
  max-height: 280px;
  overflow: auto;
  padding: 12px;
  background: #f6f8fa;
  border: 1px solid #e5e7eb;
  border-radius: 6px;
}
.modal-actions {
  display: flex;
  justify-content: flex-end;
  margin-top: 12px;
}
</style>
