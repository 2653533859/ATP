<template>
  <div style="display: flex; flex-direction: column; gap: 16px">
    <div style="display: flex; align-items: center; justify-content: space-between; gap: 12px; flex-wrap: wrap">
      <div>
        <h2 style="margin: 0">{{ t('system_pages.storage.title') }}</h2>
        <div style="color: #999; margin-top: 4px">{{ t('system_pages.storage.subtitle') }}</div>
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

    <a-card :title="t('system_pages.storage.policy_title')" :loading="policiesLoading">
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
              <a-button size="small" @click="openEditPolicy(record)">{{ t('common.edit') }}</a-button>
              <a-popconfirm :title="t('system_pages.storage.confirm_delete_policy')" @confirm="handleDeletePolicy(record)">
                <a-button size="small" danger>{{ t('common.delete') }}</a-button>
              </a-popconfirm>
            </a-space>
          </template>
        </template>
      </a-table>
    </a-card>

    <a-row :gutter="16">
      <a-col :xs="24" :md="8">
        <a-card :loading="statsLoading" :title="t('system_pages.storage.bucket_overview')">
          <a-descriptions :column="1" size="small">
            <a-descriptions-item label="Bucket">{{ stats?.bucket || '-' }}</a-descriptions-item>
            <a-descriptions-item :label="t('system_pages.storage.total_objects')">{{ stats?.total_object_count ?? 0 }}</a-descriptions-item>
            <a-descriptions-item :label="t('system_pages.storage.total_size')">{{ formatBytes(stats?.total_bytes ?? 0) }}</a-descriptions-item>
          </a-descriptions>
        </a-card>
      </a-col>
      <a-col :xs="24" :md="16">
        <a-card :title="t('system_pages.storage.prefix_stats')" :loading="statsLoading">
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

    <a-card :title="t('system_pages.storage.cleanup_scope')">
      <a-space wrap>
        <a-checkbox-group v-model:value="selectedPrefixes" :options="prefixOptions" />
      </a-space>
    </a-card>

    <a-row :gutter="16">
      <a-col :xs="24" :md="8">
        <a-card :title="t('system_pages.storage.preview_summary')" :loading="previewLoading">
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
        <a-card :title="t('system_pages.storage.deletable_objects')" :loading="previewLoading">
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

    <a-card :title="t('system_pages.storage.blocked_objects')" :loading="previewLoading">
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

    <a-card :title="t('system_pages.storage.orphan_references')" :loading="previewLoading">
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

    <a-card v-if="result" :title="t('system_pages.storage.latest_result')">
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
          <a-input-number v-model:value="policyForm.max_size_gb" :min="0" :step="0.5" style="width: 100%" />
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
  storageApi,
  type StorageCleanupExecuteItem,
  type StorageCleanupPreviewItem,
  type StorageStatsItem,
  type StoragePolicyItem,
  type StoragePolicyPayload,
} from '@/api'

const { t } = useI18n()

const defaultPrefixes = ['screenshots/', 'reports/', 'apks/', 'scripts/']

const stats = ref<StorageStatsItem | null>(null)
const preview = ref<StorageCleanupPreviewItem | null>(null)
const result = ref<StorageCleanupExecuteItem | null>(null)
const policies = ref<StoragePolicyItem[]>([])

const statsLoading = ref(false)
const previewLoading = ref(false)
const executeLoading = ref(false)
const policiesLoading = ref(false)
const policySaving = ref(false)

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
  await Promise.all([loadStats(), loadPolicies()])
})

async function loadStats() {
  statsLoading.value = true
  try {
    stats.value = await storageApi.stats()
  } catch (e: any) {
    message.error(e?.message || t('system_pages.storage.msg.load_stats_failed'))
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
  } catch (e: any) {
    message.error(e?.message || t('system_pages.storage.msg.load_policies_failed'))
  } finally {
    policiesLoading.value = false
  }
}

async function loadPreview() {
  previewLoading.value = true
  result.value = null
  try {
    preview.value = await storageApi.previewCleanup({
      prefixes: selectedPrefixes.value,
      retention_days: retentionDays.value,
    })
  } catch (e: any) {
    message.error(e?.message || t('system_pages.storage.msg.load_preview_failed'))
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
      } catch (e: any) {
        message.error(e?.message || t('system_pages.storage.msg.execute_failed'))
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
  } catch (e: any) {
    message.error(e?.response?.data?.detail || e?.message || t('system_pages.storage.msg.save_policy_failed'))
  } finally {
    policySaving.value = false
  }
}

async function handleDeletePolicy(record: StoragePolicyItem) {
  try {
    await storageApi.deletePolicy(record.id)
    message.success(t('system_pages.storage.msg.policy_deleted'))
    await loadPolicies()
  } catch (e: any) {
    message.error(e?.response?.data?.detail || e?.message || t('system_pages.storage.msg.delete_policy_failed'))
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
