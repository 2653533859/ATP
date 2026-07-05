<template>
  <div class="page-shell system-page dashboard-alert-page">
    <div class="page-hero">
      <div>
        <h2 class="page-title">{{ t('system_pages.dashboard_alert.title') }}</h2>
        <div class="page-subtitle">{{ t('system_pages.dashboard_alert.subtitle') }}</div>
      </div>
      <a-button type="primary" :disabled="!projectId" @click="openCreate">
        <PlusOutlined /> {{ t('system_pages.dashboard_alert.create') }}
      </a-button>
    </div>

    <div class="page-toolbar">
      <a-space>
        <a-select
          v-model:value="projectId"
          :placeholder="t('system_pages.dashboard_alert.select_project')"
          style="width: 220px"
          allow-clear
          :options="projectOptions"
          @change="handleProjectChange"
        />
        <a-button :disabled="!projectId" :loading="loading" @click="loadData">
          <ReloadOutlined /> {{ t('common.refresh') }}
        </a-button>
      </a-space>
    </div>

    <a-card class="table-panel" :bordered="false">
      <a-table
        :columns="columns"
        :data-source="rules"
        :loading="loading"
        row-key="id"
        size="middle"
        :pagination="{ pageSize: 20 }"
        :locale="{ emptyText: t('system_pages.dashboard_alert.empty_rules') }"
      >
        <template #bodyCell="{ column, record }">
          <template v-if="column.key === 'metric'">
            <a-tag color="blue">{{ metricLabel(record.metric) }}</a-tag>
          </template>
          <template v-if="column.key === 'condition'">
            {{ operatorLabel(record.op) }} {{ record.threshold }}
          </template>
          <template v-if="column.key === 'window'">
            {{ record.window_minutes }} / {{ record.suppress_minutes }}
          </template>
          <template v-if="column.key === 'notification'">
            {{ notificationName(record.notification_config_id) }}
          </template>
          <template v-if="column.key === 'enabled'">
            <a-tag :color="record.enabled ? 'green' : 'default'">
              {{ record.enabled ? t('common.enabled') : t('common.disabled') }}
            </a-tag>
          </template>
          <template v-if="column.key === 'action'">
            <a-space>
              <a-button type="link" size="small" @click="openEdit(record)">{{ t('common.edit') }}</a-button>
              <a-popconfirm :title="t('common.confirm_delete')" @confirm="handleDelete(record.id)">
                <a-button type="link" size="small" danger>{{ t('common.delete') }}</a-button>
              </a-popconfirm>
            </a-space>
          </template>
        </template>
      </a-table>
    </a-card>

    <a-card
      class="page-panel"
      :title="t('system_pages.dashboard_alert.recent_events')"
      :bordered="false"
    >
      <a-table
        :columns="eventColumns"
        :data-source="events"
        :loading="eventLoading"
        row-key="id"
        size="small"
        :pagination="false"
        :locale="{ emptyText: t('system_pages.dashboard_alert.empty_events') }"
      />
    </a-card>

    <a-modal
      v-model:open="formOpen"
      :title="isEdit ? t('system_pages.dashboard_alert.edit') : t('system_pages.dashboard_alert.create')"
      :confirm-loading="saving"
      width="620px"
      @ok="handleSave"
    >
      <a-form layout="vertical">
        <a-form-item :label="t('common.name')">
          <a-input v-model:value="form.name" :placeholder="t('system_pages.dashboard_alert.name_placeholder')" />
        </a-form-item>
        <a-form-item :label="t('system_pages.dashboard_alert.metric')">
          <a-select v-model:value="form.metric" :options="metricOptions" />
        </a-form-item>
        <a-form-item :label="t('system_pages.dashboard_alert.operator')">
          <a-select v-model:value="form.op" :options="operatorOptions" />
        </a-form-item>
        <a-form-item :label="t('system_pages.dashboard_alert.threshold')">
          <a-input-number v-model:value="form.threshold" style="width: 100%" />
        </a-form-item>
        <a-row :gutter="12">
          <a-col :span="12">
            <a-form-item :label="t('system_pages.dashboard_alert.window_minutes')">
              <a-input-number v-model:value="form.window_minutes" :min="1" :max="10080" style="width: 100%" />
            </a-form-item>
          </a-col>
          <a-col :span="12">
            <a-form-item :label="t('system_pages.dashboard_alert.suppress_minutes')">
              <a-input-number v-model:value="form.suppress_minutes" :min="1" :max="10080" style="width: 100%" />
            </a-form-item>
          </a-col>
        </a-row>
        <a-form-item :label="t('system_pages.dashboard_alert.notification')">
          <a-select
            v-model:value="form.notification_config_id"
            allow-clear
            :options="notificationOptions"
            :placeholder="t('system_pages.dashboard_alert.no_notification')"
          />
        </a-form-item>
        <a-form-item :label="t('common.enabled')">
          <a-switch v-model:checked="form.enabled" />
        </a-form-item>
      </a-form>
    </a-modal>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { message } from 'ant-design-vue'
import { PlusOutlined, ReloadOutlined } from '@ant-design/icons-vue'
import { useI18n } from 'vue-i18n'
import {
  dashboardAlertApi,
  notificationApi,
  projectApi,
  type DashboardAlertEventItem,
  type DashboardAlertMetric,
  type DashboardAlertOperator,
  type DashboardAlertRuleItem,
  type DashboardAlertRulePayload,
} from '@/api'

type NotificationOption = {
  id: number
  name: string
}

type RuleForm = {
  name: string
  metric: DashboardAlertMetric
  op: DashboardAlertOperator
  threshold: number
  window_minutes: number
  suppress_minutes: number
  notification_config_id?: number | null
  enabled: boolean
}

const { t } = useI18n()

const projectId = ref<number | undefined>(undefined)
const projectOptions = ref<Array<{ label: string; value: number }>>([])
const notifications = ref<NotificationOption[]>([])
const rules = ref<DashboardAlertRuleItem[]>([])
const events = ref<DashboardAlertEventItem[]>([])
const loading = ref(false)
const eventLoading = ref(false)
const formOpen = ref(false)
const saving = ref(false)
const isEdit = ref(false)
const editingId = ref<number | null>(null)

const form = reactive<RuleForm>({
  name: '',
  metric: 'pass_rate',
  op: 'lt',
  threshold: 80,
  window_minutes: 60,
  suppress_minutes: 60,
  notification_config_id: null,
  enabled: true,
})

const metricOptions = computed(() => [
  { label: t('system_pages.dashboard_alert.metrics.pass_rate'), value: 'pass_rate' },
  { label: t('system_pages.dashboard_alert.metrics.avg_duration_ms'), value: 'avg_duration_ms' },
  { label: t('system_pages.dashboard_alert.metrics.failure_count'), value: 'failure_count' },
  { label: t('system_pages.dashboard_alert.metrics.error_count'), value: 'error_count' },
  { label: t('system_pages.dashboard_alert.metrics.total_runs'), value: 'total_runs' },
])

const operatorOptions = computed(() => [
  { label: '>', value: 'gt' },
  { label: '>=', value: 'gte' },
  { label: '<', value: 'lt' },
  { label: '<=', value: 'lte' },
  { label: '=', value: 'eq' },
])

const notificationOptions = computed(() =>
  notifications.value.map(item => ({ label: item.name, value: item.id })),
)

const columns = computed(() => [
  { title: t('system_pages.dashboard_alert.columns.name'), dataIndex: 'name', key: 'name', ellipsis: true },
  { title: t('system_pages.dashboard_alert.columns.metric'), key: 'metric', width: 150 },
  { title: t('system_pages.dashboard_alert.columns.condition'), key: 'condition', width: 110 },
  { title: t('system_pages.dashboard_alert.columns.window'), key: 'window', width: 150 },
  { title: t('system_pages.dashboard_alert.columns.notification'), key: 'notification', width: 180 },
  { title: t('system_pages.dashboard_alert.columns.status'), key: 'enabled', width: 90 },
  { title: t('system_pages.dashboard_alert.columns.action'), key: 'action', width: 130, fixed: 'right' as const },
])

const eventColumns = computed(() => [
  { title: t('system_pages.dashboard_alert.event_columns.rule'), dataIndex: 'rule_id', width: 90 },
  { title: t('system_pages.dashboard_alert.event_columns.actual'), dataIndex: 'actual_value', width: 120 },
  {
    title: t('system_pages.dashboard_alert.event_columns.triggered_at'),
    dataIndex: 'triggered_at',
    customRender: ({ text }: { text?: string }) => formatTime(text),
  },
  {
    title: t('system_pages.dashboard_alert.event_columns.snoozed_until'),
    dataIndex: 'snoozed_until',
    customRender: ({ text }: { text?: string }) => formatTime(text),
  },
])

function metricLabel(metric: DashboardAlertMetric): string {
  return t(`system_pages.dashboard_alert.metrics.${metric}`)
}

function operatorLabel(op: DashboardAlertOperator): string {
  return operatorOptions.value.find(item => item.value === op)?.label ?? op
}

function notificationName(id?: number | null): string {
  if (!id) return t('system_pages.dashboard_alert.no_notification')
  return notifications.value.find(item => item.id === id)?.name ?? `#${id}`
}

function formatTime(value?: string | null): string {
  if (!value) return '-'
  return value.slice(0, 19).replace('T', ' ')
}

function resetForm() {
  Object.assign(form, {
    name: '',
    metric: 'pass_rate',
    op: 'lt',
    threshold: 80,
    window_minutes: 60,
    suppress_minutes: 60,
    notification_config_id: null,
    enabled: true,
  })
}

async function loadProjects() {
  try {
    const projects = await projectApi.list()
    projectOptions.value = projects.map(project => ({ label: project.name, value: project.id }))
  } catch {
    message.error(t('system_pages.dashboard_alert.msg.load_projects_failed'))
  }
}

async function loadNotifications() {
  if (!projectId.value) {
    notifications.value = []
    return
  }
  try {
    const list = await notificationApi.list({ project_id: projectId.value })
    notifications.value = list.map(item => ({ id: item.id, name: item.name }))
  } catch {
    notifications.value = []
  }
}

async function loadRules() {
  if (!projectId.value) {
    rules.value = []
    return
  }
  loading.value = true
  try {
    rules.value = await dashboardAlertApi.listRules({ project_id: projectId.value })
  } catch {
    message.error(t('system_pages.dashboard_alert.msg.load_rules_failed'))
  } finally {
    loading.value = false
  }
}

async function loadEvents() {
  if (!projectId.value) {
    events.value = []
    return
  }
  eventLoading.value = true
  try {
    events.value = await dashboardAlertApi.listEvents({ project_id: projectId.value, limit: 20 })
  } catch {
    events.value = []
  } finally {
    eventLoading.value = false
  }
}

async function loadData() {
  await Promise.all([loadNotifications(), loadRules(), loadEvents()])
}

async function handleProjectChange() {
  await loadData()
}

function openCreate() {
  resetForm()
  isEdit.value = false
  editingId.value = null
  formOpen.value = true
}

function openEdit(record: DashboardAlertRuleItem) {
  Object.assign(form, {
    name: record.name,
    metric: record.metric,
    op: record.op,
    threshold: record.threshold,
    window_minutes: record.window_minutes,
    suppress_minutes: record.suppress_minutes,
    notification_config_id: record.notification_config_id ?? null,
    enabled: record.enabled,
  })
  isEdit.value = true
  editingId.value = record.id
  formOpen.value = true
}

function validateForm(): boolean {
  if (!projectId.value && !isEdit.value) {
    message.warning(t('system_pages.dashboard_alert.msg.select_project'))
    return false
  }
  if (!form.name.trim()) {
    message.warning(t('system_pages.dashboard_alert.msg.name_required'))
    return false
  }
  return true
}

async function handleSave() {
  if (!validateForm()) return
  saving.value = true
  try {
    const payload: DashboardAlertRulePayload = {
      name: form.name.trim(),
      metric: form.metric,
      op: form.op,
      threshold: form.threshold,
      window_minutes: form.window_minutes,
      suppress_minutes: form.suppress_minutes,
      notification_config_id: form.notification_config_id ?? null,
      enabled: form.enabled,
    }
    if (isEdit.value && editingId.value) {
      await dashboardAlertApi.updateRule(editingId.value, payload)
    } else {
      await dashboardAlertApi.createRule({ ...payload, project_id: projectId.value })
    }
    message.success(isEdit.value ? t('system_pages.dashboard_alert.msg.update_success') : t('system_pages.dashboard_alert.msg.create_success'))
    formOpen.value = false
    await loadData()
  } catch {
    message.error(t('system_pages.dashboard_alert.msg.save_failed'))
  } finally {
    saving.value = false
  }
}

async function handleDelete(id: number) {
  try {
    await dashboardAlertApi.deleteRule(id)
    message.success(t('system_pages.dashboard_alert.msg.delete_success'))
    await loadData()
  } catch {
    message.error(t('system_pages.dashboard_alert.msg.delete_failed'))
  }
}

onMounted(async () => {
  await loadProjects()
})
</script>
