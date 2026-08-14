<template>
  <div class="page-shell">
    <div class="page-hero">
      <div>
        <h2 class="page-title">{{ t('audit_logs.title') }}</h2>
        <div class="page-subtitle">{{ t('audit_logs.subtitle') }}</div>
      </div>
    </div>

    <a-card class="filter-card" :bordered="false" style="margin-bottom: 16px">
      <a-form layout="inline" :model="filter">
        <a-form-item :label="t('audit_logs.filters.project_id')">
          <a-input-number v-model:value="filter.project_id" :min="1" style="width: 140px" allow-clear />
        </a-form-item>
        <a-form-item :label="t('audit_logs.filters.user_id')">
          <a-input-number v-model:value="filter.user_id" :min="1" style="width: 140px" allow-clear />
        </a-form-item>
        <a-form-item :label="t('audit_logs.filters.action')">
          <a-select
            v-model:value="filter.action"
            style="width: 200px"
            allow-clear
            :options="actionOptions"
          />
        </a-form-item>
        <a-form-item>
          <a-range-picker
            v-model:value="(dateRange as [Dayjs, Dayjs] | undefined)"
            :placeholder="[t('audit_logs.filters.start_time'), t('audit_logs.filters.end_time')]"
            show-time
            allow-clear
            style="width: 340px"
            @change="() => loadLogs(1)"
          />
        </a-form-item>
        <a-form-item>
          <a-button type="primary" @click="loadLogs(1)">{{ t('common.search') }}</a-button>
          <a-button style="margin-left: 8px" @click="onReset">{{ t('common.reset') }}</a-button>
          <a-button style="margin-left: 8px" :loading="exporting" @click="exportLogs">
            {{ t('audit_logs.export') }}
          </a-button>
        </a-form-item>
      </a-form>
    </a-card>

    <a-card :bordered="false">
      <a-table
        :columns="columns"
        :data-source="logs"
        :loading="loading"
        :pagination="false"
        row-key="id"
        size="small"
      >
        <template #bodyCell="{ column, record }">
          <template v-if="column.dataIndex === 'action'">
            <a-tag :color="actionColor(record.action)">{{ record.action }}</a-tag>
          </template>
          <template v-else-if="column.dataIndex === 'created_at'">
            {{ record.created_at?.slice(0, 19).replace('T', ' ') }}
          </template>
          <template v-else-if="column.dataIndex === 'detail'">
            <span style="font-size: 12px; color: var(--c-text-secondary); white-space: pre-wrap">{{ record.detail || '-' }}</span>
          </template>
        </template>
      </a-table>
      <a-pagination
        v-model:current="page"
        :total="total"
        :page-size="pageSize"
        :show-size-changer="true"
        :page-size-options="['20', '50', '100']"
        style="margin-top: 16px; text-align: right"
        @change="(p: number, ps: number) => loadLogs(p, ps)"
      />
    </a-card>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { message } from 'ant-design-vue'
import { useI18n } from 'vue-i18n'
import type { Dayjs } from 'dayjs'
import { auditLogApi, type AuditLogItem } from '@/api'

const { t } = useI18n()

const filter = reactive<{ project_id?: number; user_id?: number; action?: string }>({})
const logs = ref<AuditLogItem[]>([])
const loading = ref(false)
const page = ref(1)
const pageSize = ref(50)
const total = ref(0)
const dateRange = ref<[Dayjs, Dayjs] | null>(null)
const exporting = ref(false)

const actionOptions = computed(() => [
  { label: 'access_denied', value: 'access_denied' },
  { label: 'create', value: 'create' },
  { label: 'delete', value: 'delete' },
  { label: 'update', value: 'update' },
  { label: 'login', value: 'login' },
  { label: 'logout', value: 'logout' },
  { label: 'case.rollback', value: 'case.rollback' },
  { label: 'audit_log_cleanup', value: 'audit_log_cleanup' },
  { label: 'audit_log_export', value: 'audit_log_export' },
])

const columns = computed(() => [
  { title: 'ID', dataIndex: 'id', key: 'id', width: 70 },
  { title: t('audit_logs.col.action'), dataIndex: 'action', key: 'action', width: 130 },
  { title: t('audit_logs.col.resource'), dataIndex: 'resource_type', key: 'resource_type', width: 100 },
  { title: t('audit_logs.col.resource_id'), dataIndex: 'resource_id', key: 'resource_id', width: 80 },
  { title: t('audit_logs.col.project_id'), dataIndex: 'project_id', key: 'project_id', width: 80 },
  { title: t('audit_logs.col.username'), dataIndex: 'username', key: 'username', width: 100 },
  { title: t('audit_logs.col.detail'), dataIndex: 'detail', key: 'detail', ellipsis: true },
  { title: t('audit_logs.col.created_at'), dataIndex: 'created_at', key: 'created_at', width: 170 },
])

function actionColor(action: string) {
  if (action === 'access_denied') return 'red'
  if (action === 'delete') return 'volcano'
  if (action === 'create') return 'green'
  if (action === 'update') return 'blue'
  return 'default'
}

type ErrorLike = {
  response?: {
    data?: {
      detail?: unknown
    }
  }
}

function errorMessage(error: unknown, fallback: string) {
  if (typeof error === 'object' && error !== null) {
    const typed = error as ErrorLike
    if (typeof typed.response?.data?.detail === 'string') return typed.response.data.detail
  }
  if (error instanceof Error) return error.message
  if (typeof error === 'string') return error
  return fallback
}

async function loadLogs(targetPage = page.value, targetPageSize = pageSize.value) {
  loading.value = true
  page.value = targetPage
  pageSize.value = targetPageSize
  try {
    const result = await auditLogApi.list({
      project_id: filter.project_id,
      user_id: filter.user_id,
      action: filter.action,
      created_from: dateRange.value?.[0]?.toISOString(),
      created_to: dateRange.value?.[1]?.toISOString(),
      page: targetPage,
      page_size: targetPageSize,
    })
    logs.value = result.items
    total.value = result.total
  } catch (e: unknown) {
    message.error(errorMessage(e, t('audit_logs.load_failed')))
  } finally {
    loading.value = false
  }
}

function onReset() {
  filter.project_id = undefined
  filter.user_id = undefined
  filter.action = undefined
  dateRange.value = null
  loadLogs(1)
}

async function exportLogs() {
  exporting.value = true
  try {
    const blob = await auditLogApi.export({
      project_id: filter.project_id,
      user_id: filter.user_id,
      action: filter.action,
      created_from: dateRange.value?.[0]?.toISOString(),
      created_to: dateRange.value?.[1]?.toISOString(),
      limit: 5000,
    })
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = `audit-logs-${new Date().toISOString().slice(0, 10)}.csv`
    link.click()
    URL.revokeObjectURL(url)
    message.success(t('audit_logs.export_success'))
  } catch (e: unknown) {
    message.error(errorMessage(e, t('audit_logs.export_failed')))
  } finally {
    exporting.value = false
  }
}

onMounted(() => loadLogs(1))
</script>

<style scoped>
.page-shell {
  padding-bottom: 12px;
}
</style>
