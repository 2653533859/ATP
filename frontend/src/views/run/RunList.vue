<template>
  <div>
    <h2>执行记录</h2>
    <a-table :columns="columns" :data-source="runs" :loading="loading" row-key="id">
      <template #bodyCell="{ column, record }">
        <template v-if="column.key === 'status'">
          <a-tag :color="statusColor(record.status)">{{ record.status }}</a-tag>
        </template>
        <template v-if="column.key === 'action'">
          <a-button type="link" @click="router.push(`/runs/${record.id}`)">查看详情</a-button>
        </template>
      </template>
    </a-table>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { runApi } from '@/api'

const router = useRouter()
const runs = ref<any[]>([])
const loading = ref(false)

const columns = [
  { title: 'ID', dataIndex: 'id', key: 'id', width: 80 },
  { title: '用例 ID', dataIndex: 'case_id', key: 'case_id' },
  { title: '状态', key: 'status' },
  { title: '环境', dataIndex: 'environment', key: 'environment' },
  { title: '耗时(ms)', dataIndex: 'duration_ms', key: 'duration_ms' },
  { title: '触发时间', dataIndex: 'created_at', key: 'created_at' },
  { title: '操作', key: 'action' },
]

function statusColor(status: string) {
  return { passed: 'green', failed: 'red', running: 'blue', error: 'orange', pending: 'default' }[status] ?? 'default'
}

async function loadRuns() {
  loading.value = true
  try { runs.value = await runApi.list() } finally { loading.value = false }
}

onMounted(loadRuns)
</script>
