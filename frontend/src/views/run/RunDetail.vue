<template>
  <div>
    <a-page-header title="执行详情" @back="router.back()" />
    <a-spin :spinning="loading">
      <template v-if="run">
        <a-descriptions bordered :column="3" style="margin-bottom: 24px">
          <a-descriptions-item label="状态">
            <a-tag :color="statusColor(run.status)">{{ run.status }}</a-tag>
          </a-descriptions-item>
          <a-descriptions-item label="环境">{{ run.environment ?? '-' }}</a-descriptions-item>
          <a-descriptions-item label="耗时">{{ run.duration_ms ? `${run.duration_ms}ms` : '-' }}</a-descriptions-item>
          <a-descriptions-item label="错误信息" :span="3">{{ run.error_message ?? '-' }}</a-descriptions-item>
        </a-descriptions>

        <h3>步骤详情</h3>
        <a-collapse>
          <a-collapse-panel
            v-for="step in run.steps"
            :key="step.id"
            :header="`[${step.step_index + 1}] ${step.name}`"
          >
            <template #extra>
              <a-tag :color="statusColor(step.status)">{{ step.status }}</a-tag>
            </template>
            <a-row :gutter="16">
              <a-col :span="12">
                <strong>请求</strong>
                <pre>{{ JSON.stringify(step.request_data, null, 2) }}</pre>
              </a-col>
              <a-col :span="12">
                <strong>响应</strong>
                <pre>{{ JSON.stringify(step.response_data, null, 2) }}</pre>
              </a-col>
            </a-row>
            <div v-if="step.error_message" style="color: red">{{ step.error_message }}</div>
            <a-image v-if="step.screenshot_url" :src="step.screenshot_url" width="300" />
          </a-collapse-panel>
        </a-collapse>
      </template>
    </a-spin>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { runApi } from '@/api'

const router = useRouter()
const route = useRoute()
const run = ref<any>(null)
const loading = ref(false)

function statusColor(status: string) {
  return { passed: 'green', failed: 'red', running: 'blue', error: 'orange', pending: 'default' }[status] ?? 'default'
}

onMounted(async () => {
  loading.value = true
  try { run.value = await runApi.get(Number(route.params.runId)) } finally { loading.value = false }
})
</script>

<style scoped>
pre { background: #f5f5f5; padding: 8px; border-radius: 4px; overflow-x: auto; font-size: 12px; }
</style>
