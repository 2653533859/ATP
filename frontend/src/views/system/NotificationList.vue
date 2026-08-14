<template>
  <div class="page-shell system-page notification-page">
    <div class="page-hero">
      <div>
        <h2 class="page-title">{{ t('system_pages.notification.title') }}</h2>
        <div class="page-subtitle">{{ t('system_pages.notification.subtitle') }}</div>
      </div>
      <a-button type="primary" :disabled="!projectId" @click="openCreate">
        <PlusOutlined /> {{ t('system_pages.notification.add') }}
      </a-button>
    </div>
    <div class="page-toolbar">
      <a-space>
        <a-select
          v-model:value="projectId"
          :placeholder="t('mobile_special.select_project')"
          style="width: 200px"
          allow-clear
          :options="projectOptions"
          @change="handleProjectChange"
        />
      </a-space>
    </div>

    <a-card class="table-panel" :bordered="false">
      <a-table
        :columns="columns"
        :data-source="configs"
        :loading="loading"
        row-key="id"
        size="middle"
        :pagination="{ pageSize: 20 }"
      >
        <template #bodyCell="{ column, record }">
          <template v-if="column.key === 'channel'">
            <a-tag :color="channelColor(record.channel)">{{ channelLabel(record.channel) }}</a-tag>
          </template>
          <template v-if="column.key === 'is_enabled'">
            <a-tag :color="record.is_enabled ? 'green' : 'default'">{{ record.is_enabled ? t('common.enabled') : t('common.disabled') }}</a-tag>
          </template>
          <template v-if="column.key === 'action'">
            <a-space>
              <a-button type="link" size="small" @click="openEdit(asNotification(record))">{{ t('common.edit') }}</a-button>
              <a-button type="link" size="small" :loading="testingId === record.id" @click="handleTest(asNotification(record))">{{ t('system_pages.notification.test') }}</a-button>
              <a-popconfirm :title="t('common.confirm_delete')" @confirm="handleDelete(record.id)">
                <a-button type="link" size="small" danger>{{ t('common.delete') }}</a-button>
              </a-popconfirm>
            </a-space>
          </template>
        </template>
      </a-table>
    </a-card>

    <a-card v-if="projectId" class="table-panel delivery-panel" :bordered="false">
      <template #title>
        <a-space>
          <span>{{ t('system_pages.notification.delivery_history') }}</span>
          <a-button type="link" size="small" :loading="deliveryLoading" @click="loadDeliveries">
            {{ t('common.refresh') }}
          </a-button>
        </a-space>
      </template>
      <a-table
        :columns="deliveryColumns"
        :data-source="deliveries"
        :loading="deliveryLoading"
        row-key="id"
        size="small"
        :pagination="false"
      >
        <template #bodyCell="{ column, record }">
          <template v-if="column.key === 'deliveryStatus'">
            <a-tag :color="record.status === 'sent' ? 'green' : 'red'">
              {{ deliveryStatusLabel(record.status) }}
            </a-tag>
          </template>
          <template v-else-if="column.key === 'deliveryCreatedAt'">
            {{ formatDate(record.created_at) }}
          </template>
          <template v-else-if="column.key === 'deliveryError'">
            <span class="delivery-error">{{ record.error_message || '-' }}</span>
          </template>
        </template>
      </a-table>
    </a-card>

    <a-modal
      v-model:open="formOpen"
      :title="isEdit ? t('system_pages.notification.edit') : t('system_pages.notification.add')"
      :confirm-loading="saving"
      width="560px"
      @ok="handleSave"
    >
      <a-form layout="vertical">
        <a-form-item :label="t('common.name')">
          <a-input v-model:value="form.name" :placeholder="t('system_pages.notification.name_placeholder')" />
        </a-form-item>

        <a-form-item :label="t('system_pages.notification.channel')">
          <a-select v-model:value="form.channel" :disabled="isEdit" style="width: 100%">
            <a-select-option value="email">{{ t('system_pages.notification.channels.email_full') }}</a-select-option>
            <a-select-option value="wechat">{{ t('system_pages.notification.channels.wechat_full') }}</a-select-option>
            <a-select-option value="dingtalk">{{ t('system_pages.notification.channels.dingtalk_full') }}</a-select-option>
          </a-select>
        </a-form-item>

        <a-form-item :label="t('system_pages.notification.language')">
          <a-select v-model:value="notificationLanguage" style="width: 100%">
            <a-select-option value="zh-CN">{{ t('lang.zh') }}</a-select-option>
            <a-select-option value="en-US">{{ t('lang.en') }}</a-select-option>
          </a-select>
        </a-form-item>

        <a-divider orientation="left">{{ t('system_pages.notification.strategy') }}</a-divider>

        <a-form-item :label="t('system_pages.notification.scope')">
          <a-select v-model:value="notificationScope" style="width: 100%">
            <a-select-option value="all">{{ t('system_pages.notification.scopes.all') }}</a-select-option>
            <a-select-option value="suites">{{ t('system_pages.notification.scopes.suites') }}</a-select-option>
            <a-select-option value="plans">{{ t('system_pages.notification.scopes.plans') }}</a-select-option>
          </a-select>
        </a-form-item>

        <a-form-item v-if="notificationScope === 'suites'" :label="t('system_pages.notification.target_suites')">
          <a-select
            v-model:value="selectedSuiteIds"
            mode="multiple"
            style="width: 100%"
            :options="suiteOptions"
            :placeholder="t('system_pages.notification.target_suites_placeholder')"
            option-filter-prop="label"
          />
        </a-form-item>

        <a-form-item v-if="notificationScope === 'plans'" :label="t('system_pages.notification.target_plans')">
          <a-select
            v-model:value="selectedPlanIds"
            mode="multiple"
            style="width: 100%"
            :options="planOptions"
            :placeholder="t('system_pages.notification.target_plans_placeholder')"
            option-filter-prop="label"
          />
        </a-form-item>

        <a-form-item :label="t('system_pages.notification.status_filters')">
          <a-checkbox-group v-model:value="statusFilters" :options="statusFilterOptions" />
          <div class="form-hint">{{ t('system_pages.notification.status_filters_hint') }}</div>
        </a-form-item>

        <a-divider orientation="left">{{ t('system_pages.notification.delivery') }}</a-divider>

        <a-form-item :label="t('system_pages.notification.retry_attempts')">
          <a-input-number v-model:value="retryAttempts" :min="0" :max="3" :step="1" style="width: 100%" />
          <div class="form-hint">{{ t('system_pages.notification.retry_attempts_hint') }}</div>
        </a-form-item>

        <a-form-item :label="t('system_pages.notification.retry_backoff_seconds')">
          <a-input-number v-model:value="retryBackoffSeconds" :min="0" :max="30" :step="0.5" style="width: 100%" />
          <div class="form-hint">{{ t('system_pages.notification.retry_backoff_hint') }}</div>
        </a-form-item>

        <template v-if="form.channel === 'email'">
          <a-form-item :label="t('system_pages.notification.recipients')">
            <a-textarea
              v-model:value="emailRecipients"
              :rows="3"
              placeholder="user1@example.com&#10;user2@example.com"
            />
          </a-form-item>
          <a-form-item :label="t('system_pages.notification.subject_prefix')">
            <a-input v-model:value="emailSubjectPrefix" placeholder="[ATP]" />
          </a-form-item>
        </template>

        <template v-if="form.channel === 'wechat'">
          <a-form-item label="Webhook URL">
            <a-input v-model:value="wechatUrl" placeholder="https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=..." />
          </a-form-item>
        </template>

        <template v-if="form.channel === 'dingtalk'">
          <a-form-item label="Webhook URL">
            <a-input v-model:value="dingtalkUrl" placeholder="https://oapi.dingtalk.com/robot/send?access_token=..." />
          </a-form-item>
          <a-form-item :label="t('system_pages.notification.dingtalk_secret')">
            <a-input v-model:value="dingtalkSecret" placeholder="SEC..." />
          </a-form-item>
        </template>

        <a-form-item :label="t('common.enabled')">
          <a-switch v-model:checked="form.is_enabled" />
        </a-form-item>
      </a-form>
    </a-modal>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, onMounted } from 'vue'
import { message } from 'ant-design-vue'
import { PlusOutlined } from '@ant-design/icons-vue'
import { useI18n } from 'vue-i18n'
import type { AxiosError } from 'axios'
import {
  notificationApi,
  planApi,
  projectApi,
  suiteApi,
  type NotificationDeliveryItem,
  type PlanItem,
  type ProjectItem,
  type SuiteItem,
} from '@/api'
// a-table #bodyCell 的 record 是 Record<string, any>；数据源类型在此断言收窄
const asNotification = (record: unknown) => record as NotificationRecord

type NotificationChannel = 'email' | 'wechat' | 'dingtalk'
type NotificationScope = 'all' | 'suites' | 'plans'
type NotificationStatusFilter = 'passed' | 'failed' | 'error'

type NotificationRecord = {
  id: number
  name: string
  channel: NotificationChannel
  config: Record<string, unknown>
  is_enabled: boolean
  updated_at?: string
}

type NotificationForm = {
  name: string
  channel: NotificationChannel
  is_enabled: boolean
}

const configs = ref<NotificationRecord[]>([])
const deliveries = ref<NotificationDeliveryItem[]>([])
const loading = ref(false)
const deliveryLoading = ref(false)
const projectId = ref<number | undefined>(undefined)
const projectOptions = ref<Array<{ label: string; value: number }>>([])

const formOpen = ref(false)
const isEdit = ref(false)
const saving = ref(false)
const editingId = ref<number | null>(null)
const testingId = ref<number | null>(null)

const form = ref<NotificationForm>({ name: '', channel: 'email', is_enabled: true })
const suites = ref<SuiteItem[]>([])
const plans = ref<PlanItem[]>([])

const emailRecipients = ref('')
const emailSubjectPrefix = ref('[ATP]')
const wechatUrl = ref('')
const dingtalkUrl = ref('')
const dingtalkSecret = ref('')
const notificationLanguage = ref<'zh-CN' | 'en-US'>('zh-CN')
const notificationScope = ref<NotificationScope>('all')
const selectedSuiteIds = ref<number[]>([])
const selectedPlanIds = ref<number[]>([])
const statusFilters = ref<NotificationStatusFilter[]>(['failed', 'error'])
const retryAttempts = ref(0)
const retryBackoffSeconds = ref(1)
const { t } = useI18n()

function getErrorMessage(error: unknown, fallback: string) {
  const axiosError = error as AxiosError<{ detail?: string; message?: string }>
  const detail = axiosError?.response?.data?.detail || axiosError?.response?.data?.message
  if (typeof detail === 'string' && detail) return detail
  if (typeof error === 'string' && error) return error
  if (error instanceof Error && error.message) return error.message
  return fallback
}

const columns = computed(() => [
  { title: t('system_pages.notification.columns.name'), dataIndex: 'name', key: 'name', ellipsis: true },
  { title: t('system_pages.notification.columns.channel'), key: 'channel', width: 130 },
  { title: t('system_pages.notification.columns.status'), key: 'is_enabled', width: 80 },
  { title: t('system_pages.notification.columns.updated_at'), dataIndex: 'updated_at', width: 170,
    customRender: ({ text }: { text?: string | null }) => text?.slice(0, 19).replace('T', ' ') ?? '-' },
  { title: t('system_pages.notification.columns.action'), key: 'action', width: 180, fixed: 'right' as const },
])

const deliveryColumns = computed(() => [
  {
    title: t('system_pages.notification.delivery_columns.channel_name'),
    dataIndex: 'notification_name',
    key: 'notificationName',
    ellipsis: true,
  },
  {
    title: t('system_pages.notification.columns.channel'),
    dataIndex: 'channel',
    key: 'deliveryChannel',
    width: 100,
    customRender: ({ text }: { text: string }) => channelLabel(text),
  },
  { title: t('system_pages.notification.delivery_columns.status'), key: 'deliveryStatus', width: 90 },
  { title: t('system_pages.notification.delivery_columns.attempts'), dataIndex: 'attempts', key: 'attempts', width: 80 },
  { title: t('system_pages.notification.delivery_columns.created_at'), key: 'deliveryCreatedAt', width: 170 },
  { title: t('system_pages.notification.delivery_columns.error'), key: 'deliveryError', ellipsis: true },
])

const suiteOptions = computed(() =>
  suites.value.map(item => ({ label: `${item.name} (#${item.id})`, value: item.id })),
)

const planOptions = computed(() =>
  plans.value.map(item => ({ label: `${item.name} (#${item.id})`, value: item.id })),
)

const statusFilterOptions = computed(() => [
  { label: t('system_pages.notification.statuses.passed'), value: 'passed' },
  { label: t('system_pages.notification.statuses.failed'), value: 'failed' },
  { label: t('system_pages.notification.statuses.error'), value: 'error' },
])

function channelLabel(c: string) {
  return {
    email: t('system_pages.notification.channels.email'),
    wechat: t('system_pages.notification.channels.wechat'),
    dingtalk: t('system_pages.notification.channels.dingtalk'),
  }[c] ?? c
}
function channelColor(c: string) {
  return { email: 'blue', wechat: 'green', dingtalk: 'geekblue' }[c] ?? 'default'
}

function deliveryStatusLabel(status: string) {
  return status === 'sent'
    ? t('system_pages.notification.delivery_status.sent')
    : t('system_pages.notification.delivery_status.failed')
}

function formatDate(value?: string | null) {
  return value?.slice(0, 19).replace('T', ' ') ?? '-'
}

onMounted(async () => {
  try {
    const projects = await projectApi.list()
    projectOptions.value = projects.map((p: ProjectItem) => ({ label: p.name, value: p.id }))
  } catch { /* ignore */ }
})

async function loadConfigs() {
  if (!projectId.value) { configs.value = []; deliveries.value = []; return }
  loading.value = true
  try {
    configs.value = await notificationApi.list({ project_id: projectId.value })
  } catch (error) {
    configs.value = []
    message.error(getErrorMessage(error, t('system_pages.notification.msg.load_failed')))
  }
  finally { loading.value = false }
}

async function loadDeliveries() {
  if (!projectId.value) { deliveries.value = []; return }
  deliveryLoading.value = true
  try {
    deliveries.value = await notificationApi.deliveries({ project_id: projectId.value, limit: 20 })
  } catch (error) {
    deliveries.value = []
    message.error(getErrorMessage(error, t('system_pages.notification.msg.delivery_load_failed')))
  }
  finally { deliveryLoading.value = false }
}

async function loadTargets() {
  if (!projectId.value) {
    suites.value = []
    plans.value = []
    return
  }
  try {
    const [suiteList, planList] = await Promise.all([
      suiteApi.list({ project_id: projectId.value }),
      planApi.list({ project_id: projectId.value }),
    ])
    suites.value = suiteList
    plans.value = planList
  } catch {
    suites.value = []
    plans.value = []
  }
}

async function handleProjectChange() {
  await Promise.all([loadConfigs(), loadTargets(), loadDeliveries()])
}

function resetChannelFields() {
  emailRecipients.value = ''
  emailSubjectPrefix.value = '[ATP]'
  wechatUrl.value = ''
  dingtalkUrl.value = ''
  dingtalkSecret.value = ''
  notificationLanguage.value = 'zh-CN'
  notificationScope.value = 'all'
  selectedSuiteIds.value = []
  selectedPlanIds.value = []
  statusFilters.value = ['failed', 'error']
  retryAttempts.value = 0
  retryBackoffSeconds.value = 1
}

function openCreate() {
  isEdit.value = false
  editingId.value = null
  form.value = { name: '', channel: 'email', is_enabled: true }
  resetChannelFields()
  formOpen.value = true
}

function openEdit(record: NotificationRecord) {
  isEdit.value = true
  editingId.value = record.id
  form.value = { name: record.name, channel: record.channel, is_enabled: record.is_enabled }
  resetChannelFields()
  const cfg = (record.config || {}) as {
    recipients?: string[]
    subject_prefix?: string
    webhook_url?: string
    secret?: string
    language?: 'zh-CN' | 'en-US'
    scope?: NotificationScope
    suite_ids?: number[]
    plan_ids?: number[]
    status_filters?: NotificationStatusFilter[]
    retry_attempts?: number
    retry_backoff_seconds?: number
  }
  notificationLanguage.value = cfg.language === 'en-US' ? 'en-US' : 'zh-CN'
  notificationScope.value = ['all', 'suites', 'plans'].includes(String(cfg.scope))
    ? cfg.scope as NotificationScope
    : 'all'
  selectedSuiteIds.value = Array.isArray(cfg.suite_ids) ? cfg.suite_ids.map(Number).filter(Number.isFinite) : []
  selectedPlanIds.value = Array.isArray(cfg.plan_ids) ? cfg.plan_ids.map(Number).filter(Number.isFinite) : []
  statusFilters.value = Array.isArray(cfg.status_filters)
    ? cfg.status_filters.filter((item): item is NotificationStatusFilter => ['passed', 'failed', 'error'].includes(item))
    : ['failed', 'error']
  retryAttempts.value = typeof cfg.retry_attempts === 'number' && Number.isInteger(cfg.retry_attempts)
    ? Math.max(0, Math.min(3, cfg.retry_attempts))
    : 0
  retryBackoffSeconds.value = typeof cfg.retry_backoff_seconds === 'number' && Number.isFinite(cfg.retry_backoff_seconds)
    ? Math.max(0, Math.min(30, cfg.retry_backoff_seconds))
    : 1
  if (record.channel === 'email') {
    emailRecipients.value = (cfg.recipients || []).join('\n')
    emailSubjectPrefix.value = cfg.subject_prefix || '[ATP]'
  } else if (record.channel === 'wechat') {
    wechatUrl.value = cfg.webhook_url || ''
  } else if (record.channel === 'dingtalk') {
    dingtalkUrl.value = cfg.webhook_url || ''
    dingtalkSecret.value = cfg.secret || ''
  }
  formOpen.value = true
}

function buildConfig(): Record<string, unknown> {
  const strategyConfig = {
    scope: notificationScope.value,
    suite_ids: notificationScope.value === 'suites' ? selectedSuiteIds.value : [],
    plan_ids: notificationScope.value === 'plans' ? selectedPlanIds.value : [],
    status_filters: statusFilters.value,
    retry_attempts: retryAttempts.value,
    retry_backoff_seconds: retryBackoffSeconds.value,
  }
  if (form.value.channel === 'email') {
    return {
      recipients: emailRecipients.value.split('\n').map(s => s.trim()).filter(Boolean),
      subject_prefix: emailSubjectPrefix.value || '[ATP]',
      language: notificationLanguage.value,
      ...strategyConfig,
    }
  } else if (form.value.channel === 'wechat') {
    return { webhook_url: wechatUrl.value, language: notificationLanguage.value, ...strategyConfig }
  } else if (form.value.channel === 'dingtalk') {
    const cfg: Record<string, unknown> = { webhook_url: dingtalkUrl.value, language: notificationLanguage.value, ...strategyConfig }
    if (dingtalkSecret.value) cfg.secret = dingtalkSecret.value
    return cfg
  }
  return {}
}

async function handleSave() {
  if (!projectId.value && !isEdit.value) { message.warning(t('system_pages.notification.msg.select_project')); return }
  if (!form.value.name) { message.warning(t('system_pages.notification.msg.name_required')); return }
  if (form.value.channel === 'email' && !emailRecipients.value.trim()) {
    message.warning(t('system_pages.notification.msg.recipients_required'))
    return
  }
  if (form.value.channel === 'wechat' && !wechatUrl.value.trim()) {
    message.warning(t('system_pages.notification.msg.wechat_url_required'))
    return
  }
  if (form.value.channel === 'dingtalk' && !dingtalkUrl.value.trim()) {
    message.warning(t('system_pages.notification.msg.dingtalk_url_required'))
    return
  }
  if (notificationScope.value === 'suites' && selectedSuiteIds.value.length === 0) {
    message.warning(t('system_pages.notification.msg.select_suite'))
    return
  }
  if (notificationScope.value === 'plans' && selectedPlanIds.value.length === 0) {
    message.warning(t('system_pages.notification.msg.select_plan'))
    return
  }
  if (statusFilters.value.length === 0) {
    message.warning(t('system_pages.notification.msg.select_status'))
    return
  }
  if (!Number.isInteger(retryAttempts.value) || retryAttempts.value < 0 || retryAttempts.value > 3) {
    message.warning(t('system_pages.notification.msg.retry_attempts_invalid'))
    return
  }
  if (!Number.isFinite(retryBackoffSeconds.value) || retryBackoffSeconds.value < 0 || retryBackoffSeconds.value > 30) {
    message.warning(t('system_pages.notification.msg.retry_backoff_invalid'))
    return
  }
  saving.value = true
  try {
    const payload = {
      name: form.value.name,
      channel: form.value.channel,
      config: buildConfig(),
      is_enabled: form.value.is_enabled,
    }
    if (isEdit.value) {
      await notificationApi.update(editingId.value!, payload)
    } else {
      await notificationApi.create({ ...payload, project_id: projectId.value })
    }
    message.success(isEdit.value ? t('system_pages.notification.msg.update_success') : t('system_pages.notification.msg.create_success'))
    formOpen.value = false
    loadConfigs()
  } catch (error) {
    message.error(getErrorMessage(error, t('system_pages.notification.msg.save_failed')))
  }
  finally { saving.value = false }
}

async function handleTest(record: NotificationRecord) {
  testingId.value = record.id
  try {
    await notificationApi.test(record.id)
    message.success(t('system_pages.notification.msg.test_success'))
  } catch (error) {
    message.error(getErrorMessage(error, t('system_pages.notification.msg.test_failed')))
  }
  finally {
    // 测试发送接口会记录成功/失败投递，立即刷新让用户能看到本次结果。
    await loadDeliveries()
    testingId.value = null
  }
}

async function handleDelete(id: number) {
  try {
    await notificationApi.delete(id)
    message.success(t('system_pages.notification.msg.delete_success'))
    loadConfigs()
  } catch (error) {
    message.error(getErrorMessage(error, t('system_pages.notification.msg.delete_failed')))
  }
}
</script>

<style scoped>
.form-hint {
  margin-top: 6px;
  color: #8c8c8c;
  font-size: 12px;
}

.delivery-panel {
  margin-top: 16px;
}

.delivery-error {
  color: #cf1322;
}
</style>
