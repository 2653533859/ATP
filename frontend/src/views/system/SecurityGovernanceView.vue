<template>
  <div class="page-shell system-page security-governance-page">
    <div class="page-hero">
      <div>
        <h2 class="page-title">{{ t('system_pages.security.title') }}</h2>
        <p class="page-subtitle">{{ t('system_pages.security.subtitle') }}</p>
      </div>
    </div>

    <a-tabs v-model:active-key="activeTab">
      <a-tab-pane key="api_keys" :tab="t('system_pages.security.tabs.api_keys')">
        <div class="page-toolbar">
          <a-space>
            <a-select
              v-model:value="projectId"
              allow-clear
              :options="projectOptions"
              :placeholder="t('system_pages.security.all_projects')"
              style="width: 220px"
              @change="loadAuditReport"
            />
            <a-button :loading="keysLoading" @click="loadAuditReport">
              <ReloadOutlined /> {{ t('common.refresh') }}
            </a-button>
          </a-space>
          <a-button type="primary" @click="openCreateKey">
            <PlusOutlined /> {{ t('system_pages.security.create_key') }}
          </a-button>
        </div>

        <a-card class="table-panel" :bordered="false">
          <a-table
            :columns="keyColumns"
            :data-source="apiKeys"
            :loading="keysLoading"
            row-key="key_id"
            size="middle"
            :pagination="{ pageSize: 15 }"
            :locale="{ emptyText: t('system_pages.security.empty_keys') }"
          >
            <template #bodyCell="{ column, record }">
              <template v-if="column.key === 'key_prefix'">
                <code>{{ record.key_prefix }}</code>
              </template>
              <template v-else-if="column.key === 'role'">
                <a-tag color="blue">{{ record.role }}</a-tag>
              </template>
              <template v-else-if="column.key === 'status'">
                <a-tag :color="keyStatusColor(asKey(record))">{{ keyStatusLabel(asKey(record)) }}</a-tag>
              </template>
              <template v-else-if="column.key === 'ip_allowlist'">
                <span>{{ (record.ip_allowlist || []).length ? record.ip_allowlist.join(', ') : t('system_pages.security.no_ip_limit') }}</span>
              </template>
              <template v-else-if="column.key === 'last_used_at'">
                {{ record.last_used_at ? formatTime(record.last_used_at) : '-' }}
              </template>
              <template v-else-if="column.key === 'expires_at'">
                {{ record.expires_at ? formatTime(record.expires_at) : t('system_pages.security.never_expires') }}
              </template>
              <template v-else-if="column.key === 'action'">
                <a-popconfirm
                  v-if="record.is_active"
                  :title="t('system_pages.security.revoke_confirm')"
                  @confirm="handleRevokeKey(record.key_id)"
                >
                  <a-button type="link" size="small" danger :loading="revokingKeyId === record.key_id">
                    {{ t('system_pages.security.revoke') }}
                  </a-button>
                </a-popconfirm>
                <span v-else class="muted-text">-</span>
              </template>
            </template>
          </a-table>
        </a-card>
      </a-tab-pane>

      <a-tab-pane key="disaster_recovery" :tab="t('system_pages.security.tabs.disaster_recovery')">
        <a-card class="page-panel" :bordered="false">
          <div class="dr-toolbar">
            <a-input
              v-model:value="snapshotTag"
              :placeholder="t('system_pages.security.snapshot_tag_placeholder')"
              style="width: 240px"
            />
            <a-button type="primary" :loading="snapshotLoading" @click="handleCreateSnapshot">
              {{ t('system_pages.security.create_snapshot') }}
            </a-button>
            <a-button :loading="drillLoading" @click="handlePerformDrill">
              {{ t('system_pages.security.perform_drill') }}
            </a-button>
          </div>

          <a-row :gutter="[16, 16]">
            <a-col :xs="24" :md="12">
              <a-card size="small" :title="t('system_pages.security.snapshot_result_title')">
                <a-empty v-if="!snapshotResult" :description="t('system_pages.security.no_snapshot_yet')" />
                <template v-else>
                  <a-descriptions :column="1" size="small" bordered>
                    <a-descriptions-item :label="t('system_pages.security.snapshot_id')">
                      <code>{{ snapshotResult.snapshot_id }}</code>
                    </a-descriptions-item>
                    <a-descriptions-item :label="t('system_pages.security.platform_version')">
                      {{ snapshotResult.platform_version }}
                    </a-descriptions-item>
                    <a-descriptions-item :label="t('system_pages.security.mode_db')">
                      {{ snapshotResult.mode }} / {{ snapshotResult.database_type }}
                    </a-descriptions-item>
                    <a-descriptions-item :label="t('system_pages.security.table_counts')">
                      <pre class="json-block">{{ JSON.stringify(snapshotResult.table_counts, null, 2) }}</pre>
                    </a-descriptions-item>
                  </a-descriptions>
                </template>
              </a-card>
            </a-col>
            <a-col :xs="24" :md="12">
              <a-card size="small" :title="t('system_pages.security.drill_result_title')">
                <a-empty v-if="!drillResult" :description="t('system_pages.security.no_drill_yet')" />
                <template v-else>
                  <a-descriptions :column="1" size="small" bordered>
                    <a-descriptions-item :label="t('common.status')">
                      <a-tag :color="drillResult.status === 'passed' ? 'green' : 'red'">
                        {{ drillResult.status }}
                      </a-tag>
                    </a-descriptions-item>
                    <a-descriptions-item :label="t('system_pages.security.integrity_passed')">
                      <a-tag :color="drillResult.integrity_passed ? 'green' : 'red'">
                        {{ drillResult.integrity_passed ? t('common.yes') : t('common.no') }}
                      </a-tag>
                    </a-descriptions-item>
                    <a-descriptions-item :label="t('system_pages.security.drill_duration')">
                      {{ drillResult.duration_ms }} ms
                    </a-descriptions-item>
                    <a-descriptions-item :label="t('system_pages.security.table_reconciliation')">
                      <pre class="json-block">{{ JSON.stringify(drillResult.table_reconciliation || {}, null, 2) }}</pre>
                    </a-descriptions-item>
                  </a-descriptions>
                </template>
              </a-card>
            </a-col>
          </a-row>
        </a-card>
      </a-tab-pane>

      <a-tab-pane key="pii_mask" :tab="t('system_pages.security.tabs.pii_mask')">
        <a-card class="page-panel" :bordered="false">
          <a-form layout="vertical">
            <a-form-item :label="t('system_pages.security.pii_keywords')">
              <a-input
                v-model:value="piiKeywords"
                :placeholder="t('system_pages.security.pii_keywords_placeholder')"
              />
            </a-form-item>
            <a-row :gutter="16">
              <a-col :xs="24" :md="12">
                <a-form-item :label="t('system_pages.security.pii_input')">
                  <a-textarea
                    v-model:value="piiPayload"
                    :rows="8"
                    :placeholder="t('system_pages.security.pii_input_placeholder')"
                  />
                </a-form-item>
              </a-col>
              <a-col :xs="24" :md="12">
                <a-form-item :label="t('system_pages.security.pii_output')">
                  <a-textarea :value="piiRedactedText" :rows="8" readonly />
                </a-form-item>
              </a-col>
            </a-row>
            <a-button type="primary" :loading="piiMasking" @click="handleMaskPii">
              {{ t('system_pages.security.run_pii_mask') }}
            </a-button>
          </a-form>
        </a-card>
      </a-tab-pane>
    </a-tabs>

    <a-modal
      v-model:open="createModalOpen"
      :title="t('system_pages.security.create_key')"
      :confirm-loading="creatingKey"
      @ok="handleCreateKey"
    >
      <a-form layout="vertical">
        <a-form-item :label="t('common.name')" required>
          <a-input v-model:value="keyForm.name" :placeholder="t('system_pages.security.key_name_placeholder')" />
        </a-form-item>
        <a-row :gutter="12">
          <a-col :span="12">
            <a-form-item :label="t('system_pages.security.role')">
              <a-select v-model:value="keyForm.role" :options="roleOptions" />
            </a-form-item>
          </a-col>
          <a-col :span="12">
            <a-form-item :label="t('system_pages.security.expires_in_days')">
              <a-input-number v-model:value="keyForm.expires_in_days" :min="1" :max="3650" style="width: 100%" />
            </a-form-item>
          </a-col>
        </a-row>
        <a-form-item :label="t('system_pages.security.bind_project')">
          <a-select v-model:value="keyForm.project_id" allow-clear :options="projectOptions" :placeholder="t('system_pages.security.all_projects')" />
        </a-form-item>
        <a-form-item :label="t('system_pages.security.ip_allowlist')">
          <a-textarea v-model:value="keyForm.ip_allowlist" :rows="3" :placeholder="t('system_pages.security.ip_allowlist_placeholder')" />
        </a-form-item>
      </a-form>
    </a-modal>

    <a-modal
      v-model:open="rawKeyModalOpen"
      :title="t('system_pages.security.raw_key_title')"
      :footer="null"
    >
      <a-alert type="warning" show-icon :message="t('system_pages.security.raw_key_warning')" style="margin-bottom: 12px" />
      <div class="raw-key-box">
        <code>{{ createdRawKey }}</code>
        <a-button size="small" type="primary" @click="copyRawKey">{{ t('common.copy') }}</a-button>
      </div>
    </a-modal>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { message } from 'ant-design-vue'
import { PlusOutlined, ReloadOutlined } from '@ant-design/icons-vue'
import { useI18n } from 'vue-i18n'
import { formatLocalDateTime } from '@/utils/dateTime'
import { extractApiError } from '@/utils/apiError'
import {
  projectApi,
  securityApi,
  type ProjectItem,
  type SecurityApiKeyAuditItem,
  type SecurityDrDrillReport,
  type SecurityDrSnapshotManifest,
} from '@/api'

const { t } = useI18n()
const asKey = (record: unknown) => record as SecurityApiKeyAuditItem

const activeTab = ref('api_keys')
const projects = ref<ProjectItem[]>([])
const projectId = ref<number | undefined>(undefined)
const apiKeys = ref<SecurityApiKeyAuditItem[]>([])
const keysLoading = ref(false)
const revokingKeyId = ref<number | null>(null)
const createModalOpen = ref(false)
const creatingKey = ref(false)
const rawKeyModalOpen = ref(false)
const createdRawKey = ref('')

const keyForm = reactive({
  name: '',
  role: 'engineer',
  project_id: undefined as number | undefined,
  expires_in_days: 90 as number | undefined,
  ip_allowlist: '',
})

const snapshotTag = ref('manual')
const snapshotLoading = ref(false)
const snapshotResult = ref<SecurityDrSnapshotManifest | null>(null)
const drillLoading = ref(false)
const drillResult = ref<SecurityDrDrillReport | null>(null)

const piiPayload = ref('')
const piiKeywords = ref('')
const piiRedactedText = ref('')
const piiMasking = ref(false)

const projectOptions = computed(() => projects.value.map((p) => ({ label: p.name, value: p.id })))
const roleOptions = [
  { label: 'viewer', value: 'viewer' },
  { label: 'tester', value: 'tester' },
  { label: 'engineer', value: 'engineer' },
  { label: 'admin', value: 'admin' },
]

const keyColumns = computed(() => [
  { title: t('common.name'), dataIndex: 'name', key: 'name', ellipsis: true },
  { title: t('system_pages.security.key_prefix'), key: 'key_prefix', width: 145 },
  { title: t('system_pages.security.role'), key: 'role', width: 100 },
  { title: t('common.status'), key: 'status', width: 100 },
  { title: t('system_pages.security.ip_allowlist'), key: 'ip_allowlist', ellipsis: true },
  { title: t('system_pages.security.total_calls'), dataIndex: 'total_calls', key: 'total_calls', width: 90 },
  { title: t('system_pages.security.last_used_at'), key: 'last_used_at', width: 155 },
  { title: t('system_pages.security.expires_at'), key: 'expires_at', width: 155 },
  { title: t('common.actions'), key: 'action', width: 95 },
])

function formatTime(value?: string | null) {
  return formatLocalDateTime(value)
}

function keyStatusColor(item: SecurityApiKeyAuditItem) {
  if (!item.is_active) return 'default'
  if (item.is_expired) return 'red'
  return 'green'
}

function keyStatusLabel(item: SecurityApiKeyAuditItem) {
  if (!item.is_active) return t('system_pages.security.status_revoked')
  if (item.is_expired) return t('system_pages.security.status_expired')
  return t('system_pages.security.status_active')
}

async function loadProjects() {
  try {
    projects.value = await projectApi.list()
  } catch {
    projects.value = []
  }
}

async function loadAuditReport() {
  keysLoading.value = true
  try {
    apiKeys.value = await securityApi.getApiKeyAuditReport(projectId.value)
  } catch (error: unknown) {
    message.error(extractApiError(error, t('system_pages.security.msg.load_keys_failed')))
  } finally {
    keysLoading.value = false
  }
}

function openCreateKey() {
  keyForm.name = ''
  keyForm.role = 'engineer'
  keyForm.project_id = projectId.value
  keyForm.expires_in_days = 90
  keyForm.ip_allowlist = ''
  createModalOpen.value = true
}

async function handleCreateKey() {
  const name = keyForm.name.trim()
  if (!name) {
    message.warning(t('system_pages.security.msg.name_required'))
    return
  }
  creatingKey.value = true
  try {
    const allowlist = keyForm.ip_allowlist
      .split(/[\n,]/)
      .map((item) => item.trim())
      .filter(Boolean)
    const created = await securityApi.createApiKey({
      name,
      role: keyForm.role,
      project_id: keyForm.project_id ?? null,
      expires_in_days: keyForm.expires_in_days ?? null,
      ip_allowlist: allowlist,
    })
    createModalOpen.value = false
    createdRawKey.value = created.raw_key
    rawKeyModalOpen.value = true
    message.success(t('system_pages.security.msg.create_key_success'))
    await loadAuditReport()
  } catch (error: unknown) {
    message.error(extractApiError(error, t('system_pages.security.msg.create_key_failed')))
  } finally {
    creatingKey.value = false
  }
}

async function handleRevokeKey(keyId: number) {
  revokingKeyId.value = keyId
  try {
    await securityApi.revokeApiKey(keyId)
    message.success(t('system_pages.security.msg.revoke_success'))
    await loadAuditReport()
  } catch (error: unknown) {
    message.error(extractApiError(error, t('system_pages.security.msg.revoke_failed')))
  } finally {
    revokingKeyId.value = null
  }
}

async function copyRawKey() {
  try {
    await navigator.clipboard.writeText(createdRawKey.value)
    message.success(t('common.copied'))
  } catch {
    message.info(createdRawKey.value)
  }
}

async function handleCreateSnapshot() {
  snapshotLoading.value = true
  try {
    snapshotResult.value = await securityApi.createDrSnapshot(snapshotTag.value.trim() || 'manual')
    message.success(t('system_pages.security.msg.snapshot_success'))
  } catch (error: unknown) {
    message.error(extractApiError(error, t('system_pages.security.msg.snapshot_failed')))
  } finally {
    snapshotLoading.value = false
  }
}

async function handlePerformDrill() {
  drillLoading.value = true
  try {
    drillResult.value = await securityApi.performDrDrill()
    message.success(t('system_pages.security.msg.drill_success'))
  } catch (error: unknown) {
    message.error(extractApiError(error, t('system_pages.security.msg.drill_failed')))
  } finally {
    drillLoading.value = false
  }
}

async function handleMaskPii() {
  if (!piiPayload.value.trim()) {
    message.warning(t('system_pages.security.msg.pii_input_required'))
    return
  }
  piiMasking.value = true
  try {
    let payload: unknown = piiPayload.value
    try {
      payload = JSON.parse(piiPayload.value)
    } catch {
      payload = piiPayload.value
    }
    const customKeywords = piiKeywords.value
      .split(',')
      .map((item) => item.trim())
      .filter(Boolean)
    const res = await securityApi.maskPii({ payload, custom_keywords: customKeywords })
    piiRedactedText.value =
      typeof res.redacted === 'string' ? res.redacted : JSON.stringify(res.redacted, null, 2)
  } catch (error: unknown) {
    message.error(extractApiError(error, t('system_pages.security.msg.pii_failed')))
  } finally {
    piiMasking.value = false
  }
}

onMounted(async () => {
  await Promise.all([loadProjects(), loadAuditReport()])
})
</script>

<style scoped>
.dr-toolbar {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  margin-bottom: 16px;
}
.json-block {
  margin: 0;
  max-height: 220px;
  overflow: auto;
  font-size: 12px;
  white-space: pre-wrap;
}
.raw-key-box {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  padding: 10px 12px;
  border: 1px solid var(--c-border);
  border-radius: 8px;
  background: var(--c-bg-subtle);
}
.raw-key-box code {
  word-break: break-all;
}
.muted-text {
  color: var(--c-text-tertiary);
}
</style>
