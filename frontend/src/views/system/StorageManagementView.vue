<template>
  <div class="page-shell system-page storage-page">
    <div class="page-hero">
      <div>
        <h2 class="page-title">{{ t('system_pages.storage.title') }}</h2>
        <div class="page-subtitle">{{ t('system_pages.storage.subtitle') }}</div>
      </div>
      <a-space wrap>
        <a-input-number
          v-model:value="retentionDays"
          :min="1"
          :max="3650"
          :addon-before="t('system_pages.storage.retention_days')"
          style="width: 180px"
        />
        <a-button :loading="statsLoading" @click="loadStats">{{ t('system_pages.storage.refresh_stats') }}</a-button>
        <a-button type="primary" :loading="previewLoading" @click="loadPreview">{{ t('system_pages.storage.generate_preview') }}</a-button>
      </a-space>
    </div>

    <section class="storage-alert-status" :class="{ triggered: storageAlert }" aria-live="polite">
      <div class="storage-alert-marker" aria-hidden="true" />
      <div class="storage-alert-copy">
        <div class="storage-alert-title">
          {{ storageAlert ? t('system_pages.storage.alert_triggered') : t('system_pages.storage.alert_clear') }}
        </div>
        <div v-if="storageAlert" class="storage-alert-summary">
          {{ t('system_pages.storage.alert_summary', { total: storageAlert.total_gb.toFixed(2), threshold: storageAlert.threshold_gb.toFixed(2) }) }}
          · {{ formatDate(storageAlert.triggered_at) }}
        </div>
        <div v-else class="storage-alert-summary">{{ t('system_pages.storage.alert_no_current') }}</div>
      </div>
      <a-button size="small" :loading="alertLoading" @click="loadAlert">{{ t('system_pages.storage.refresh_alert') }}</a-button>
    </section>

    <a-card class="page-panel" :title="t('system_pages.storage.policy_title')" :loading="policiesLoading">
      <template #extra>
        <a-button type="primary" size="small" @click="openCreatePolicy">{{ t('system_pages.storage.new_policy') }}</a-button>
      </template>
      <a-table
        :data-source="policies"
        :pagination="false"
        :columns="policyColumns"
        row-key="id"
        size="small"
      >
        <template #bodyCell="{ column, record }">
          <template v-if="column.key === 'enabled'">
            <a-tag :color="record.enabled ? 'green' : 'default'">
              {{ record.enabled ? t('common.enabled') : t('common.disabled') }}
            </a-tag>
          </template>
          <template v-else-if="column.key === 'actions'">
            <a-space size="small">
              <a-button size="small" @click="openEditPolicy(asPolicy(record))">{{ t('common.edit') }}</a-button>
              <a-popconfirm :title="t('system_pages.storage.confirm_delete_policy')" @confirm="handleDeletePolicy(asPolicy(record))">
                <a-button size="small" danger>{{ t('common.delete') }}</a-button>
              </a-popconfirm>
            </a-space>
          </template>
        </template>
      </a-table>
    </a-card>

    <a-row :gutter="16">
      <a-col :xs="24" :md="8">
        <a-card class="page-panel" :loading="statsLoading" :title="t('system_pages.storage.bucket_overview')">
          <a-descriptions :column="1" size="small">
            <a-descriptions-item label="Bucket">{{ stats?.bucket || '-' }}</a-descriptions-item>
            <a-descriptions-item :label="t('system_pages.storage.total_objects')">{{ stats?.total_object_count ?? 0 }}</a-descriptions-item>
            <a-descriptions-item :label="t('system_pages.storage.total_size')">{{ formatBytes(stats?.total_bytes ?? 0) }}</a-descriptions-item>
          </a-descriptions>
        </a-card>
      </a-col>
      <a-col :xs="24" :md="16">
        <a-card class="page-panel" :title="t('system_pages.storage.prefix_stats')" :loading="statsLoading">
          <a-table
            :data-source="stats?.prefixes || []"
            :pagination="false"
            :columns="prefixColumns"
            row-key="prefix"
            size="small"
          >
            <template #bodyCell="{ column, record }">
              <template v-if="column.key === 'total_bytes'">
                {{ formatBytes(record.total_bytes) }}
              </template>
            </template>
          </a-table>
        </a-card>
      </a-col>
    </a-row>

    <a-card class="page-panel storage-reconcile-panel" :loading="datasetLoading || projectsLoading">
      <template #title>
        <div class="storage-section-title">
          <span>{{ t('system_pages.storage.dataset_reconcile_title') }}</span>
          <a-tag color="blue">{{ t('system_pages.storage.dataset_reconcile_read_only') }}</a-tag>
        </div>
      </template>
      <template #extra>
        <span class="storage-section-hint">{{ t('system_pages.storage.dataset_reconcile_hint') }}</span>
      </template>
      <div class="storage-reconcile-toolbar">
        <a-select
          v-model:value="datasetProjectId"
          :options="projectOptions"
          :placeholder="t('system_pages.storage.select_project')"
          allow-clear
          style="min-width: 260px"
          @change="datasetReconcile = null"
        />
        <a-button type="primary" :disabled="!datasetProjectId" :loading="datasetLoading" @click="runDatasetReconcile()">
          {{ t('system_pages.storage.dataset_reconcile_scan') }}
        </a-button>
        <a-button
          v-if="datasetReconcile && datasetReconcile.orphan_count > 0"
          danger
          :loading="datasetPurgeLoading"
          :disabled="datasetReconcile.project_id !== datasetProjectId"
          @click="runDatasetReconcile(true)"
        >
          {{ t('system_pages.storage.dataset_reconcile_purge') }}
        </a-button>
      </div>

      <a-descriptions v-if="datasetReconcile" class="storage-reconcile-summary" :column="3" size="small">
        <a-descriptions-item :label="t('system_pages.storage.dataset_project')">{{ projectName(datasetReconcile.project_id) }}</a-descriptions-item>
        <a-descriptions-item :label="t('system_pages.storage.dataset_scanned')">{{ datasetReconcile.scanned_count }}</a-descriptions-item>
        <a-descriptions-item :label="t('system_pages.storage.dataset_referenced')">{{ datasetReconcile.referenced_count }}</a-descriptions-item>
        <a-descriptions-item :label="t('system_pages.storage.dataset_orphans')">
          <a-tag :color="datasetReconcile.orphan_count ? 'orange' : 'green'">{{ datasetReconcile.orphan_count }}</a-tag>
        </a-descriptions-item>
        <a-descriptions-item :label="t('system_pages.storage.dataset_deleted')">{{ datasetReconcile.deleted_count }}</a-descriptions-item>
        <a-descriptions-item :label="t('system_pages.storage.dataset_status')">
          {{ datasetReconcile.dry_run ? t('system_pages.storage.dataset_dry_run') : t('system_pages.storage.dataset_purged') }}
        </a-descriptions-item>
      </a-descriptions>
      <div v-if="datasetReconcile?.truncated" class="storage-reconcile-warning">
        {{ t('system_pages.storage.dataset_truncated') }}
      </div>
      <a-table
        v-if="datasetReconcile"
        class="storage-reconcile-table"
        :data-source="datasetObjectRows"
        :pagination="{ pageSize: 8 }"
        :columns="datasetObjectColumns"
        row-key="object_name"
        size="small"
      />
      <div v-if="datasetReconcile?.errors.length" class="storage-reconcile-errors">
        <div v-for="error in datasetReconcile.errors" :key="error">{{ error }}</div>
      </div>
    </a-card>

    <a-card class="page-panel" :title="t('system_pages.storage.cleanup_scope')">
      <a-space wrap>
        <a-checkbox-group v-model:value="selectedPrefixes" :options="prefixOptions" />
      </a-space>
    </a-card>

    <a-row :gutter="16">
      <a-col :xs="24" :md="8">
        <a-card class="page-panel" :title="t('system_pages.storage.preview_summary')" :loading="previewLoading">
          <a-descriptions :column="1" size="small">
            <a-descriptions-item :label="t('system_pages.storage.scanned_objects')">{{ preview?.scanned_object_count ?? 0 }}</a-descriptions-item>
            <a-descriptions-item :label="t('system_pages.storage.expired_objects')">{{ preview?.expired_object_count ?? 0 }}</a-descriptions-item>
            <a-descriptions-item :label="t('system_pages.storage.size_evicted')">{{ preview?.size_evicted_count ?? 0 }}</a-descriptions-item>
            <a-descriptions-item :label="t('system_pages.storage.deletable')">{{ preview?.deletable_count ?? 0 }}</a-descriptions-item>
            <a-descriptions-item :label="t('system_pages.storage.blocked')">{{ preview?.blocked_count ?? 0 }}</a-descriptions-item>
            <a-descriptions-item :label="t('system_pages.storage.orphan_refs')">{{ preview?.orphan_reference_count ?? 0 }}</a-descriptions-item>
          </a-descriptions>
          <div style="margin-top: 16px">
            <a-space wrap>
              <a-checkbox v-model:checked="repairOrphans">{{ t('system_pages.storage.repair_orphans') }}</a-checkbox>
              <a-button
                danger
                type="primary"
                :disabled="!preview?.deletable_objects.length && !preview?.orphan_reference_count"
                :loading="executeLoading"
                @click="handleExecute"
              >
                {{ t('system_pages.storage.execute_cleanup') }}
              </a-button>
            </a-space>
          </div>
        </a-card>
      </a-col>
      <a-col :xs="24" :md="16">
        <a-card class="page-panel" :title="t('system_pages.storage.deletable_objects')" :loading="previewLoading">
          <a-table
            :data-source="preview?.deletable_objects || []"
            :pagination="{ pageSize: 10 }"
            :columns="objectColumns"
            row-key="object_name"
            size="small"
          >
            <template #bodyCell="{ column, record }">
              <template v-if="column.key === 'last_modified'">
                {{ formatDate(record.last_modified) }}
              </template>
            </template>
          </a-table>
        </a-card>
      </a-col>
    </a-row>

    <a-card class="page-panel" :title="t('system_pages.storage.blocked_objects')" :loading="previewLoading">
      <a-table
        :data-source="preview?.blocked_objects || []"
        :pagination="{ pageSize: 10 }"
        :columns="objectColumns"
        row-key="object_name"
        size="small"
      >
        <template #bodyCell="{ column, record }">
          <template v-if="column.key === 'last_modified'">
            {{ formatDate(record.last_modified) }}
          </template>
        </template>
      </a-table>
    </a-card>

    <a-card class="page-panel" :title="t('system_pages.storage.orphan_references')" :loading="previewLoading">
      <a-table
        :data-source="preview?.orphan_references || []"
        :pagination="{ pageSize: 10 }"
        :columns="referenceColumns"
        row-key="object_name"
        size="small"
      >
        <template #bodyCell="{ column, record }">
          <template v-if="column.key === 'repairable'">
            <a-tag :color="record.repairable ? 'green' : 'default'">
              {{ record.repairable ? t('system_pages.storage.repairable') : t('system_pages.storage.not_repairable') }}
            </a-tag>
          </template>
        </template>
      </a-table>
    </a-card>

    <a-card v-if="result" class="page-panel" :title="t('system_pages.storage.latest_result')">
      <a-descriptions :column="2" size="small">
        <a-descriptions-item :label="t('system_pages.storage.requested_count')">{{ result.requested_count }}</a-descriptions-item>
        <a-descriptions-item :label="t('system_pages.storage.deleted_count')">{{ result.deleted_count }}</a-descriptions-item>
        <a-descriptions-item :label="t('system_pages.storage.skipped_referenced')">{{ result.skipped_referenced_count }}</a-descriptions-item>
        <a-descriptions-item :label="t('system_pages.storage.missing_count')">{{ result.missing_count }}</a-descriptions-item>
        <a-descriptions-item :label="t('system_pages.storage.repaired_count')">{{ result.repaired_reference_count }}</a-descriptions-item>
      </a-descriptions>
    </a-card>

    <a-drawer
      v-model:open="policyDrawerVisible"
      :title="policyForm.id ? t('system_pages.storage.edit_policy') : t('system_pages.storage.new_policy_full')"
      width="420"
      @close="resetPolicyForm"
    >
      <a-form layout="vertical">
        <a-form-item :label="t('common.name')" required>
          <a-input v-model:value="policyForm.name" :placeholder="t('system_pages.storage.name_placeholder')" />
        </a-form-item>
        <a-form-item :label="t('system_pages.storage.minio_prefix')" required>
          <a-input v-model:value="policyForm.prefix" :placeholder="t('system_pages.storage.prefix_placeholder')" />
        </a-form-item>
        <a-form-item :label="t('system_pages.storage.retention_days')" required>
          <a-input-number v-model:value="policyForm.retention_days" :min="1" :max="3650" style="width: 100%" />
        </a-form-item>
        <a-form-item :label="t('system_pages.storage.max_size_gb')">
          <a-input-number v-model:value="(policyForm.max_size_gb as number | undefined)" :min="0" :step="0.5" style="width: 100%" />
        </a-form-item>
        <a-form-item :label="t('common.enabled')">
          <a-switch v-model:checked="policyForm.enabled" />
        </a-form-item>
        <a-form-item :label="t('common.description')">
          <a-textarea v-model:value="policyForm.description" :rows="3" />
        </a-form-item>
      </a-form>
      <template #footer>
        <a-space>
          <a-button @click="policyDrawerVisible = false">{{ t('common.cancel') }}</a-button>
          <a-button type="primary" :loading="policySaving" @click="submitPolicyForm">{{ t('common.save') }}</a-button>
        </a-space>
      </template>
    </a-drawer>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { message, Modal } from 'ant-design-vue'
import { useI18n } from 'vue-i18n'
import {
  projectApi,
  storageApi,
  type StorageCleanupExecuteItem,
  type StorageCleanupPreviewItem,
  type StorageDatasetReconcileItem,
  type StorageAlertPayload,
  type ProjectItem,
  type StorageStatsItem,
  type StoragePolicyItem,
  type StoragePolicyPayload,
} from '@/api'

// a-table #bodyCell 的 record 是 Record<string, any>；数据源类型在此断言收窄
const asPolicy = (record: unknown) => record as StoragePolicyItem

const { t } = useI18n()

const defaultPrefixes = ['screenshots/', 'reports/', 'apks/', 'scripts/']

const stats = ref<StorageStatsItem | null>(null)
const preview = ref<StorageCleanupPreviewItem | null>(null)
const result = ref<StorageCleanupExecuteItem | null>(null)
const policies = ref<StoragePolicyItem[]>([])
const storageAlert = ref<StorageAlertPayload | null>(null)
const projects = ref<ProjectItem[]>([])
const datasetProjectId = ref<number | undefined>(undefined)
const datasetReconcile = ref<StorageDatasetReconcileItem | null>(null)

const statsLoading = ref(false)
const previewLoading = ref(false)
const executeLoading = ref(false)
const policiesLoading = ref(false)
const policySaving = ref(false)
const projectsLoading = ref(false)
const datasetLoading = ref(false)
const datasetPurgeLoading = ref(false)
const alertLoading = ref(false)

type ErrorLike = {
  message?: unknown
  response?: {
    data?: {
      detail?: unknown
    }
  }
}

function errorMessage(error: unknown, fallback: string) {
  if (typeof error === 'string') return error
  if (error instanceof Error) return error.message
  if (typeof error === 'object' && error !== null) {
    const typed = error as ErrorLike
    if (typeof typed.response?.data?.detail === 'string') return typed.response.data.detail
    if (typeof typed.message === 'string') return typed.message
  }
  return fallback
}

const retentionDays = ref(30)
const repairOrphans = ref(false)
const selectedPrefixes = ref<string[]>([...defaultPrefixes])

const policyDrawerVisible = ref(false)
const policyForm = reactive<{
  id: number | null
  name: string
  prefix: string
  retention_days: number
  max_size_gb: number | null
  enabled: boolean
  description: string
}>({
  id: null,
  name: '',
  prefix: '',
  retention_days: 30,
  max_size_gb: null,
  enabled: true,
  description: '',
})

const prefixOptions = computed(() => {
  if (policies.value.length) {
    return policies.value
      .filter((item) => item.enabled)
      .map((item) => ({ label: `${item.prefix} (${item.retention_days}d)`, value: item.prefix }))
  }
  return defaultPrefixes.map((value) => ({ label: value, value }))
})

const projectOptions = computed(() => projects.value.map((project) => ({ label: project.name, value: project.id })))

const prefixColumns = computed(() => [
  { title: t('system_pages.storage.prefix'), dataIndex: 'prefix', key: 'prefix' },
  { title: t('system_pages.storage.object_count'), dataIndex: 'object_count', key: 'object_count', width: 120 },
  { title: t('system_pages.storage.total_size'), dataIndex: 'total_bytes', key: 'total_bytes', width: 140 },
])

const objectColumns = computed(() => [
  { title: t('system_pages.storage.object_name'), dataIndex: 'object_name', key: 'object_name', ellipsis: true },
  { title: t('system_pages.storage.last_modified'), dataIndex: 'last_modified', key: 'last_modified', width: 220 },
  { title: t('system_pages.storage.reference_count'), dataIndex: 'referenced_by_count', key: 'referenced_by_count', width: 100 },
])

const referenceColumns = computed(() => [
  { title: t('system_pages.storage.reference_type'), dataIndex: 'reference_type', key: 'reference_type', width: 140 },
  { title: t('system_pages.storage.record_id'), dataIndex: 'record_id', key: 'record_id', width: 100 },
  { title: t('system_pages.storage.field'), dataIndex: 'field_name', key: 'field_name', width: 180 },
  { title: t('system_pages.storage.object_name'), dataIndex: 'object_name', key: 'object_name', ellipsis: true },
  { title: t('system_pages.storage.repairability'), dataIndex: 'repairable', key: 'repairable', width: 120 },
])

const datasetObjectColumns = computed(() => [
  { title: t('system_pages.storage.object_name'), dataIndex: 'object_name', key: 'object_name', ellipsis: true },
])

const datasetObjectRows = computed(() =>
  (datasetReconcile.value?.orphaned_objects || []).map((object_name) => ({ object_name })),
)

const policyColumns = computed(() => [
  { title: t('common.name'), dataIndex: 'name', key: 'name', width: 140 },
  { title: t('system_pages.storage.prefix'), dataIndex: 'prefix', key: 'prefix', width: 160 },
  { title: t('system_pages.storage.retention_days'), dataIndex: 'retention_days', key: 'retention_days', width: 100 },
  { title: t('system_pages.storage.max_size_gb_short'), dataIndex: 'max_size_gb', key: 'max_size_gb', width: 120 },
  { title: t('common.status'), dataIndex: 'enabled', key: 'enabled', width: 100 },
  { title: t('common.description'), dataIndex: 'description', key: 'description', ellipsis: true },
  { title: t('common.action'), key: 'actions', width: 160 },
])

onMounted(async () => {
  await Promise.all([loadStats(), loadPolicies(), loadProjects(), loadAlert()])
})

async function loadStats() {
  statsLoading.value = true
  try {
    stats.value = await storageApi.stats()
  } catch (e: unknown) {
    message.error(errorMessage(e, t('system_pages.storage.msg.load_stats_failed')))
  } finally {
    statsLoading.value = false
  }
}

async function loadPolicies() {
  policiesLoading.value = true
  try {
    policies.value = await storageApi.listPolicies()
    const enabledPrefixes = policies.value.filter((item) => item.enabled).map((item) => item.prefix)
    if (enabledPrefixes.length) {
      selectedPrefixes.value = enabledPrefixes
    }
  } catch (e: unknown) {
    message.error(errorMessage(e, t('system_pages.storage.msg.load_policies_failed')))
  } finally {
    policiesLoading.value = false
  }
}

async function loadAlert() {
  alertLoading.value = true
  try {
    storageAlert.value = (await storageApi.getAlert()).alert
  } catch (e: unknown) {
    message.error(errorMessage(e, t('system_pages.storage.msg.load_alert_failed')))
  } finally {
    alertLoading.value = false
  }
}

async function loadProjects() {
  projectsLoading.value = true
  try {
    projects.value = await projectApi.list()
    if (!datasetProjectId.value && projects.value.length) {
      datasetProjectId.value = projects.value[0].id
    }
  } catch (e: unknown) {
    message.error(errorMessage(e, t('system_pages.storage.msg.load_projects_failed')))
  } finally {
    projectsLoading.value = false
  }
}

function projectName(projectId: number) {
  return projects.value.find((project) => project.id === projectId)?.name || `#${projectId}`
}

function runDatasetReconcile(purge = false) {
  if (!datasetProjectId.value) {
    message.warning(t('system_pages.storage.msg.select_project'))
    return
  }
  if (purge && (!datasetReconcile.value || datasetReconcile.value.project_id !== datasetProjectId.value || datasetReconcile.value.orphan_count === 0)) {
    message.warning(t('system_pages.storage.msg.scan_before_purge'))
    return
  }

  const projectId = datasetProjectId.value
  const execute = async () => {
    if (purge) datasetPurgeLoading.value = true
    else datasetLoading.value = true
    try {
      datasetReconcile.value = await storageApi.reconcileDatasetStorage(projectId, purge)
      message.success(t(purge ? 'system_pages.storage.msg.dataset_purge_success' : 'system_pages.storage.msg.dataset_scan_success'))
    } catch (e: unknown) {
      message.error(errorMessage(e, t(purge ? 'system_pages.storage.msg.dataset_purge_failed' : 'system_pages.storage.msg.dataset_scan_failed')))
    } finally {
      if (purge) datasetPurgeLoading.value = false
      else datasetLoading.value = false
    }
  }

  if (!purge) {
    void execute()
    return
  }
  Modal.confirm({
    title: t('system_pages.storage.dataset_purge_confirm_title'),
    content: t('system_pages.storage.dataset_purge_confirm_content', { count: datasetReconcile.value?.orphan_count || 0 }),
    okText: t('system_pages.storage.dataset_reconcile_purge'),
    cancelText: t('common.cancel'),
    okButtonProps: { danger: true },
    onOk: execute,
  })
}

async function loadPreview() {
  previewLoading.value = true
  result.value = null
  try {
    preview.value = await storageApi.previewCleanup({
      prefixes: selectedPrefixes.value,
      retention_days: retentionDays.value,
    })
  } catch (e: unknown) {
    message.error(errorMessage(e, t('system_pages.storage.msg.load_preview_failed')))
  } finally {
    previewLoading.value = false
  }
}

function handleExecute() {
  const objectNames = preview.value?.deletable_objects.map((item) => item.object_name) || []
  const orphanCount = preview.value?.orphan_reference_count || 0
  Modal.confirm({
    title: t('system_pages.storage.confirm_execute_title'),
    content: t(
      repairOrphans.value ? 'system_pages.storage.confirm_execute_with_orphans' : 'system_pages.storage.confirm_execute_content',
      { count: objectNames.length, orphanCount },
    ),
    okText: t('system_pages.storage.confirm_execute'),
    cancelText: t('common.cancel'),
    async onOk() {
      executeLoading.value = true
      try {
        result.value = await storageApi.executeCleanup({
          object_names: objectNames,
          repair_orphan_references: repairOrphans.value,
        })
        message.success(t('system_pages.storage.msg.execute_success'))
        await Promise.all([loadStats(), loadPreview()])
      } catch (e: unknown) {
        message.error(errorMessage(e, t('system_pages.storage.msg.execute_failed')))
      } finally {
        executeLoading.value = false
      }
    },
  })
}

function resetPolicyForm() {
  policyForm.id = null
  policyForm.name = ''
  policyForm.prefix = ''
  policyForm.retention_days = 30
  policyForm.max_size_gb = null
  policyForm.enabled = true
  policyForm.description = ''
}

function openCreatePolicy() {
  resetPolicyForm()
  policyDrawerVisible.value = true
}

function openEditPolicy(record: StoragePolicyItem) {
  policyForm.id = record.id
  policyForm.name = record.name
  policyForm.prefix = record.prefix
  policyForm.retention_days = record.retention_days
  policyForm.max_size_gb = record.max_size_gb ?? null
  policyForm.enabled = record.enabled
  policyForm.description = record.description ?? ''
  policyDrawerVisible.value = true
}

async function submitPolicyForm() {
  if (!policyForm.name.trim() || !policyForm.prefix.trim()) {
    message.warning(t('system_pages.storage.msg.name_prefix_required'))
    return
  }
  const payload: StoragePolicyPayload = {
    name: policyForm.name.trim(),
    prefix: policyForm.prefix.trim(),
    retention_days: policyForm.retention_days,
    max_size_gb: policyForm.max_size_gb,
    enabled: policyForm.enabled,
    description: policyForm.description?.trim() || null,
  }
  policySaving.value = true
  try {
    if (policyForm.id) {
      await storageApi.updatePolicy(policyForm.id, payload)
      message.success(t('system_pages.storage.msg.policy_updated'))
    } else {
      await storageApi.createPolicy(payload)
      message.success(t('system_pages.storage.msg.policy_created'))
    }
    policyDrawerVisible.value = false
    await loadPolicies()
  } catch (e: unknown) {
    message.error(errorMessage(e, t('system_pages.storage.msg.save_policy_failed')))
  } finally {
    policySaving.value = false
  }
}

async function handleDeletePolicy(record: StoragePolicyItem) {
  try {
    await storageApi.deletePolicy(record.id)
    message.success(t('system_pages.storage.msg.policy_deleted'))
    await loadPolicies()
  } catch (e: unknown) {
    message.error(errorMessage(e, t('system_pages.storage.msg.delete_policy_failed')))
  }
}

function formatBytes(bytes: number) {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(2)} KB`
  if (bytes < 1024 * 1024 * 1024) return `${(bytes / 1024 / 1024).toFixed(2)} MB`
  return `${(bytes / 1024 / 1024 / 1024).toFixed(2)} GB`
}

function formatDate(value?: string | null) {
  if (!value) return '-'
  return new Date(value).toLocaleString()
}
</script>

<style scoped>
.storage-alert-status {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px 16px;
  background: var(--c-bg-elevated);
  border: 1px solid var(--c-border);
  border-radius: var(--radius-md);
  box-shadow: var(--shadow-sm);
}

.storage-alert-status.triggered {
  background: var(--c-danger-bg, #fff1f0);
  border-color: var(--c-danger-border, #ffa39e);
}

.storage-alert-marker {
  width: 9px;
  height: 9px;
  flex: 0 0 auto;
  border-radius: 50%;
  background: var(--c-success, #52c41a);
  box-shadow: 0 0 0 4px color-mix(in srgb, var(--c-success, #52c41a) 14%, transparent);
}

.storage-alert-status.triggered .storage-alert-marker {
  background: var(--c-danger, #ff4d4f);
  box-shadow: 0 0 0 4px color-mix(in srgb, var(--c-danger, #ff4d4f) 14%, transparent);
}

.storage-alert-copy {
  min-width: 0;
  flex: 1;
}

.storage-alert-title {
  color: var(--c-text);
  font-size: 13px;
  font-weight: 600;
}

.storage-alert-summary {
  margin-top: 2px;
  color: var(--c-text-secondary);
  font-size: 12px;
}

.storage-section-title {
  display: flex;
  align-items: center;
  gap: 10px;
}

.storage-section-hint {
  color: var(--c-text-secondary);
  font-size: 12px;
}

.storage-reconcile-toolbar {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 12px;
}

.storage-reconcile-summary {
  margin-top: 18px;
}

.storage-reconcile-table {
  margin-top: 12px;
}

.storage-reconcile-warning,
.storage-reconcile-errors {
  margin-top: 12px;
  padding: 10px 12px;
  border-radius: var(--radius-sm);
  font-size: 12px;
}

.storage-reconcile-warning {
  color: var(--c-warning-text, #8a5a00);
  background: var(--c-warning-bg, #fff7e6);
  border: 1px solid var(--c-warning-border, #ffd591);
}

.storage-reconcile-errors {
  color: var(--c-danger-text, #a61d24);
  background: var(--c-danger-bg, #fff1f0);
  border: 1px solid var(--c-danger-border, #ffa39e);
}

@media (max-width: 720px) {
  .storage-alert-status {
    align-items: flex-start;
  }

  .storage-section-hint {
    display: none;
  }

  .storage-reconcile-toolbar > :deep(.ant-select) {
    width: 100% !important;
  }
}
</style>
