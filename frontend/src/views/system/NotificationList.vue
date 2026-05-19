<template>
  <div class="notification-page">
    <div class="toolbar">
      <a-space>
        <a-select
          v-model:value="projectId"
          :placeholder="t('mobile_special.select_project')"
          style="width: 200px"
          allow-clear
          :options="projectOptions"
          @change="loadConfigs"
        />
      </a-space>
      <a-button type="primary" :disabled="!projectId" @click="openCreate">
        <PlusOutlined /> {{ t('system_pages.notification.add') }}
      </a-button>
    </div>

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
            <a-button type="link" size="small" @click="openEdit(record)">{{ t('common.edit') }}</a-button>
            <a-button type="link" size="small" :loading="testingId === record.id" @click="handleTest(record)">{{ t('system_pages.notification.test') }}</a-button>
            <a-popconfirm :title="t('common.confirm_delete')" @confirm="handleDelete(record.id)">
              <a-button type="link" size="small" danger>{{ t('common.delete') }}</a-button>
            </a-popconfirm>
          </a-space>
        </template>
      </template>
    </a-table>

    <!-- 新建/编辑 Modal -->
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

        <!-- 邮件配置 -->
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

        <!-- 企业微信配置 -->
        <template v-if="form.channel === 'wechat'">
          <a-form-item label="Webhook URL">
            <a-input v-model:value="wechatUrl" placeholder="https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=..." />
          </a-form-item>
        </template>

        <!-- 钉钉配置 -->
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
import { notificationApi, projectApi } from '@/api'

type NotificationChannel = 'email' | 'wechat' | 'dingtalk'

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
const loading = ref(false)
const projectId = ref<number | undefined>(undefined)
const projectOptions = ref<Array<{ label: string; value: number }>>([])

const formOpen = ref(false)
const isEdit = ref(false)
const saving = ref(false)
const editingId = ref<number | null>(null)
const testingId = ref<number | null>(null)

const form = ref<NotificationForm>({ name: '', channel: 'email', is_enabled: true })

// 渠道特定字段
const emailRecipients = ref('')
const emailSubjectPrefix = ref('[ATP]')
const wechatUrl = ref('')
const dingtalkUrl = ref('')
const dingtalkSecret = ref('')
const { t } = useI18n()

const columns = computed(() => [
  { title: t('system_pages.notification.columns.name'), dataIndex: 'name', key: 'name', ellipsis: true },
  { title: t('system_pages.notification.columns.channel'), key: 'channel', width: 130 },
  { title: t('system_pages.notification.columns.status'), key: 'is_enabled', width: 80 },
  { title: t('system_pages.notification.columns.updated_at'), dataIndex: 'updated_at', width: 170,
    customRender: ({ text }: any) => text?.slice(0, 19).replace('T', ' ') },
  { title: t('system_pages.notification.columns.action'), key: 'action', width: 180, fixed: 'right' as const },
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

onMounted(async () => {
  try {
    const projects = await projectApi.list()
    projectOptions.value = projects.map((p: any) => ({ label: p.name, value: p.id }))
  } catch { /* ignore */ }
})

async function loadConfigs() {
  if (!projectId.value) { configs.value = []; return }
  loading.value = true
  try {
    configs.value = await notificationApi.list({ project_id: projectId.value })
  } catch { message.error(t('system_pages.notification.msg.load_failed')) }
  finally { loading.value = false }
}

function resetChannelFields() {
  emailRecipients.value = ''
  emailSubjectPrefix.value = '[ATP]'
  wechatUrl.value = ''
  dingtalkUrl.value = ''
  dingtalkSecret.value = ''
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
  }
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
  if (form.value.channel === 'email') {
    return {
      recipients: emailRecipients.value.split('\n').map(s => s.trim()).filter(Boolean),
      subject_prefix: emailSubjectPrefix.value || '[ATP]',
    }
  } else if (form.value.channel === 'wechat') {
    return { webhook_url: wechatUrl.value }
  } else if (form.value.channel === 'dingtalk') {
    const cfg: Record<string, string> = { webhook_url: dingtalkUrl.value }
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
  } catch { message.error(t('system_pages.notification.msg.save_failed')) }
  finally { saving.value = false }
}

async function handleTest(record: NotificationRecord) {
  testingId.value = record.id
  try {
    await notificationApi.test(record.id)
    message.success(t('system_pages.notification.msg.test_success'))
  } catch { message.error(t('system_pages.notification.msg.test_failed')) }
  finally { testingId.value = null }
}

async function handleDelete(id: number) {
  try {
    await notificationApi.delete(id)
    message.success(t('system_pages.notification.msg.delete_success'))
    loadConfigs()
  } catch { message.error(t('system_pages.notification.msg.delete_failed')) }
}
</script>

<style scoped>
.notification-page {
  display: flex;
  flex-direction: column;
  gap: 16px;
}
.toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
</style>
