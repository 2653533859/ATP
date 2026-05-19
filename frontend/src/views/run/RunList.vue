<template>
  <div>
    <h2>{{ t('run.list_title') }}</h2>
    <a-table
      :columns="columns"
      :data-source="runs"
      :loading="loading"
      :pagination="pagination"
      row-key="id"
      @change="handleTableChange"
    >
      <template #bodyCell="{ column, record }">
        <template v-if="column.key === 'status'">
          <a-tag :color="statusColor(record.status)">{{ record.status }}</a-tag>
        </template>
        <template v-if="column.key === 'action'">
          <a-button type="link" @click="router.push(`/runs/${record.id}`)">{{ t('common.view_detail') }}</a-button>
        </template>
      </template>
    </a-table>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, reactive, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { runApi } from '@/api'

const router = useRouter()
const { t } = useI18n()
const runs = ref<any[]>([])
const loading = ref(false)

const pagination = reactive({
  current: 1,
  pageSize: 20,
  total: 0,
  showSizeChanger: true,
  showTotal: (total: number) => t('run.pagination_total', { total }),
})

const columns = computed(() => [
  { title: t('run.columns.id'), dataIndex: 'id', key: 'id', width: 80 },
  { title: t('run.columns.case_id'), dataIndex: 'case_id', key: 'case_id' },
  { title: t('run.columns.status'), key: 'status' },
  { title: t('run.columns.environment'), dataIndex: 'environment', key: 'environment' },
  { title: t('run.columns.duration_ms'), dataIndex: 'duration_ms', key: 'duration_ms' },
  { title: t('run.columns.created_at'), dataIndex: 'created_at', key: 'created_at' },
  { title: t('run.columns.action'), key: 'action' },
])

function statusColor(status: string) {
  return { passed: 'green', failed: 'red', running: 'blue', error: 'orange', pending: 'default' }[status] ?? 'default'
}

async function loadRuns() {
  loading.value = true
  try {
    const res = await runApi.list({ page: pagination.current, page_size: pagination.pageSize })
    runs.value = res.items
    pagination.total = res.total
  } finally {
    loading.value = false
  }
}

function handleTableChange(pag: any) {
  pagination.current = pag.current
  pagination.pageSize = pag.pageSize
  loadRuns()
}

onMounted(loadRuns)
</script>
