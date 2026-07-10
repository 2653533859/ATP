<template>
  <div class="page-shell">
    <div class="page-hero">
      <div>
        <h2 class="page-title">{{ t('run.list_title') }}</h2>
        <div class="page-subtitle">{{ t('run.list_subtitle') }}</div>
      </div>
      <a-button :loading="loading" @click="loadRuns">
        <ReloadOutlined /> {{ t('common.refresh') }}
      </a-button>
    </div>

    <a-row :gutter="12" class="page-summary">
      <a-col :span="6"><a-card size="small"><a-statistic :title="t('run.overview.total')" :value="pagination.total" /></a-card></a-col>
      <a-col :span="6"><a-card size="small"><a-statistic :title="t('run.overview.passed')" :value="pageStatusCount.passed" /></a-card></a-col>
      <a-col :span="6"><a-card size="small"><a-statistic :title="t('run.overview.failed')" :value="pageStatusCount.failed" /></a-card></a-col>
      <a-col :span="6"><a-card size="small"><a-statistic :title="t('run.overview.running')" :value="pageStatusCount.running" /></a-card></a-col>
    </a-row>

    <div class="page-toolbar">
      <div class="page-toolbar-main">
        <a-input-number
          v-model:value="(caseId as number | undefined)"
          :placeholder="t('run.filters.case_id')"
          :min="1"
          style="width: 150px"
          @press-enter="applyFilters"
        />
        <a-select
          v-model:value="statusFilter"
          :placeholder="t('run.filters.status')"
          :options="statusOptions"
          allow-clear
          style="width: 150px"
        />
        <a-input-search
          v-model:value="keyword"
          :placeholder="t('run.filters.keyword')"
          allow-clear
          style="width: 280px"
        />
        <a-button type="primary" @click="applyFilters">{{ t('common.search') }}</a-button>
        <a-button @click="resetFilters">{{ t('common.reset') }}</a-button>
      </div>
      <span class="muted-text">{{ t('run.page_scope_hint') }}</span>
    </div>

    <a-table
      :columns="columns"
      :data-source="filteredRuns"
      :loading="loading"
      :pagination="pagination"
      :locale="{ emptyText: t('run.empty') }"
      row-key="id"
      :scroll="{ x: 1120 }"
      @change="handleTableChange"
    >
      <template #bodyCell="{ column, record }">
        <template v-if="column.key === 'status'">
          <a-tag :color="statusColor(record.status)">{{ statusLabel(record.status) }}</a-tag>
        </template>
        <template v-else-if="column.key === 'environment'">
          <a-tag v-if="record.environment" color="blue">{{ record.environment }}</a-tag>
          <span v-else>-</span>
        </template>
        <template v-else-if="column.key === 'duration_ms'">
          {{ formatDuration(record.duration_ms) }}
        </template>
        <template v-else-if="column.key === 'error_message'">
          <span v-if="record.error_message" class="error-summary" :title="record.error_message">
            {{ record.error_message }}
          </span>
          <span v-else class="muted-text">-</span>
        </template>
        <template v-else-if="column.key === 'created_at'">
          {{ formatTime(record.created_at) }}
        </template>
        <template v-else-if="column.key === 'action'">
          <a-button type="link" @click="router.push(`/runs/${record.id}`)">{{ t('common.view_detail') }}</a-button>
        </template>
      </template>
    </a-table>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, reactive, onMounted } from 'vue'
import { ReloadOutlined } from '@ant-design/icons-vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { runApi, type RunDetailItem } from '@/api'

const router = useRouter()
const { t } = useI18n()
const runs = ref<RunDetailItem[]>([])
const loading = ref(false)
const caseId = ref<number | null>(null)
const statusFilter = ref<string>()
const keyword = ref('')

const pagination = reactive({
  current: 1,
  pageSize: 20,
  total: 0,
  showSizeChanger: true,
  showTotal: (total: number) => t('run.pagination_total', { total }),
})

const statusOptions = computed(() =>
  ['pending', 'running', 'passed', 'failed', 'error'].map((value) => ({
    label: statusLabel(value),
    value,
  })),
)

const columns = computed(() => [
  { title: t('run.columns.id'), dataIndex: 'id', key: 'id', width: 80 },
  { title: t('run.columns.case_id'), dataIndex: 'case_id', key: 'case_id', width: 100 },
  { title: t('run.columns.status'), key: 'status', width: 100 },
  { title: t('run.columns.environment'), dataIndex: 'environment', key: 'environment', width: 140 },
  { title: t('run.columns.duration_ms'), dataIndex: 'duration_ms', key: 'duration_ms', width: 120 },
  { title: t('run.columns.error_message'), dataIndex: 'error_message', key: 'error_message', width: 280 },
  { title: t('run.columns.created_at'), dataIndex: 'created_at', key: 'created_at', width: 180 },
  { title: t('run.columns.action'), key: 'action', width: 100, fixed: 'right' as const },
])

const filteredRuns = computed(() => {
  const needle = keyword.value.trim().toLowerCase()
  return runs.value.filter((run) => {
    if (statusFilter.value && run.status !== statusFilter.value) return false
    if (!needle) return true
    return [String(run.id), String(run.case_id), run.environment ?? '', run.error_message ?? '']
      .some((value) => value.toLowerCase().includes(needle))
  })
})

const pageStatusCount = computed(() => {
  const result = { passed: 0, failed: 0, running: 0 }
  runs.value.forEach((run) => {
    if (run.status === 'passed') result.passed += 1
    if (run.status === 'failed' || run.status === 'error') result.failed += 1
    if (run.status === 'running' || run.status === 'pending') result.running += 1
  })
  return result
})

function statusColor(status: string) {
  return { passed: 'green', failed: 'red', running: 'blue', error: 'orange', pending: 'default' }[status] ?? 'default'
}

function statusLabel(status: string) {
  return t(`run.statuses.${status}`)
}

function formatDuration(duration?: number | null) {
  if (duration == null) return '-'
  if (duration < 1000) return `${duration} ms`
  return `${(duration / 1000).toFixed(2)} s`
}

function formatTime(value: string) {
  return value?.slice(0, 19).replace('T', ' ') || '-'
}

async function loadRuns() {
  loading.value = true
  try {
    const res = await runApi.list({
      case_id: caseId.value ?? undefined,
      page: pagination.current,
      page_size: pagination.pageSize,
    })
    runs.value = res.items
    pagination.total = res.total
  } finally {
    loading.value = false
  }
}

function applyFilters() {
  pagination.current = 1
  loadRuns()
}

function resetFilters() {
  caseId.value = null
  statusFilter.value = undefined
  keyword.value = ''
  pagination.current = 1
  loadRuns()
}

function handleTableChange(pag: { current?: number; pageSize?: number }) {
  pagination.current = pag.current ?? pagination.current
  pagination.pageSize = pag.pageSize ?? pagination.pageSize
  loadRuns()
}

onMounted(loadRuns)
</script>

<style scoped>
.error-summary {
  display: block;
  max-width: 260px;
  overflow: hidden;
  color: var(--c-error);
  text-overflow: ellipsis;
  white-space: nowrap;
}
</style>
