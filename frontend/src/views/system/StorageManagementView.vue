<template>
  <div style="display: flex; flex-direction: column; gap: 16px">
    <div style="display: flex; align-items: center; justify-content: space-between; gap: 12px; flex-wrap: wrap">
      <div>
        <h2 style="margin: 0">存储管理</h2>
        <div style="color: #999; margin-top: 4px">配置清理策略、预览过期对象，并按需执行清理</div>
      </div>
      <a-space wrap>
        <a-input-number
          v-model:value="retentionDays"
          :min="1"
          :max="3650"
          addon-before="保留天数"
          style="width: 180px"
        />
        <a-button :loading="statsLoading" @click="loadStats">刷新统计</a-button>
        <a-button type="primary" :loading="previewLoading" @click="loadPreview">生成预览</a-button>
      </a-space>
    </div>

    <a-card title="清理策略" :loading="policiesLoading">
      <template #extra>
        <a-button type="primary" size="small" @click="openCreatePolicy">新建策略</a-button>
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
              {{ record.enabled ? '启用' : '停用' }}
            </a-tag>
          </template>
          <template v-else-if="column.key === 'actions'">
            <a-space size="small">
              <a-button size="small" @click="openEditPolicy(record)">编辑</a-button>
              <a-popconfirm title="确定删除该策略？" @confirm="handleDeletePolicy(record)">
                <a-button size="small" danger>删除</a-button>
              </a-popconfirm>
            </a-space>
          </template>
        </template>
      </a-table>
    </a-card>

    <a-row :gutter="16">
      <a-col :xs="24" :md="8">
        <a-card :loading="statsLoading" title="桶概览">
          <a-descriptions :column="1" size="small">
            <a-descriptions-item label="Bucket">{{ stats?.bucket || '-' }}</a-descriptions-item>
            <a-descriptions-item label="对象总数">{{ stats?.total_object_count ?? 0 }}</a-descriptions-item>
            <a-descriptions-item label="总大小">{{ formatBytes(stats?.total_bytes ?? 0) }}</a-descriptions-item>
          </a-descriptions>
        </a-card>
      </a-col>
      <a-col :xs="24" :md="16">
        <a-card title="前缀统计" :loading="statsLoading">
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

    <a-card title="清理范围">
      <a-space wrap>
        <a-checkbox-group v-model:value="selectedPrefixes" :options="prefixOptions" />
      </a-space>
    </a-card>

    <a-row :gutter="16">
      <a-col :xs="24" :md="8">
        <a-card title="预览摘要" :loading="previewLoading">
          <a-descriptions :column="1" size="small">
            <a-descriptions-item label="扫描对象">{{ preview?.scanned_object_count ?? 0 }}</a-descriptions-item>
            <a-descriptions-item label="过期对象">{{ preview?.expired_object_count ?? 0 }}</a-descriptions-item>
            <a-descriptions-item label="可删除">{{ preview?.deletable_count ?? 0 }}</a-descriptions-item>
            <a-descriptions-item label="被引用阻塞">{{ preview?.blocked_count ?? 0 }}</a-descriptions-item>
            <a-descriptions-item label="孤儿引用">{{ preview?.orphan_reference_count ?? 0 }}</a-descriptions-item>
          </a-descriptions>
          <div style="margin-top: 16px">
            <a-space wrap>
              <a-checkbox v-model:checked="repairOrphans">修复孤儿引用</a-checkbox>
              <a-button
                danger
                type="primary"
                :disabled="!preview?.deletable_objects.length && !preview?.orphan_reference_count"
                :loading="executeLoading"
                @click="handleExecute"
              >
                执行清理
              </a-button>
            </a-space>
          </div>
        </a-card>
      </a-col>
      <a-col :xs="24" :md="16">
        <a-card title="可删除对象" :loading="previewLoading">
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

    <a-card title="阻塞对象" :loading="previewLoading">
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

    <a-card title="孤儿引用" :loading="previewLoading">
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
              {{ record.repairable ? '可修复' : '不可修复' }}
            </a-tag>
          </template>
        </template>
      </a-table>
    </a-card>

    <a-card v-if="result" title="最近执行结果">
      <a-descriptions :column="2" size="small">
        <a-descriptions-item label="请求对象数">{{ result.requested_count }}</a-descriptions-item>
        <a-descriptions-item label="已删除">{{ result.deleted_count }}</a-descriptions-item>
        <a-descriptions-item label="跳过引用对象">{{ result.skipped_referenced_count }}</a-descriptions-item>
        <a-descriptions-item label="缺失对象">{{ result.missing_count }}</a-descriptions-item>
        <a-descriptions-item label="已修复引用">{{ result.repaired_reference_count }}</a-descriptions-item>
      </a-descriptions>
    </a-card>

    <a-drawer
      v-model:open="policyDrawerVisible"
      :title="policyForm.id ? '编辑清理策略' : '新建清理策略'"
      width="420"
      @close="resetPolicyForm"
    >
      <a-form layout="vertical">
        <a-form-item label="名称" required>
          <a-input v-model:value="policyForm.name" placeholder="例如 screenshots" />
        </a-form-item>
        <a-form-item label="MinIO 前缀" required>
          <a-input v-model:value="policyForm.prefix" placeholder="例如 screenshots/" />
        </a-form-item>
        <a-form-item label="保留天数" required>
          <a-input-number v-model:value="policyForm.retention_days" :min="1" :max="3650" style="width: 100%" />
        </a-form-item>
        <a-form-item label="最大占用 (GB)">
          <a-input-number v-model:value="policyForm.max_size_gb" :min="0" :step="0.5" style="width: 100%" />
        </a-form-item>
        <a-form-item label="启用">
          <a-switch v-model:checked="policyForm.enabled" />
        </a-form-item>
        <a-form-item label="描述">
          <a-textarea v-model:value="policyForm.description" :rows="3" />
        </a-form-item>
      </a-form>
      <template #footer>
        <a-space>
          <a-button @click="policyDrawerVisible = false">取消</a-button>
          <a-button type="primary" :loading="policySaving" @click="submitPolicyForm">保存</a-button>
        </a-space>
      </template>
    </a-drawer>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { message, Modal } from 'ant-design-vue'
import {
  storageApi,
  type StorageCleanupExecuteItem,
  type StorageCleanupPreviewItem,
  type StorageStatsItem,
  type StoragePolicyItem,
  type StoragePolicyPayload,
} from '@/api'

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

const prefixColumns = [
  { title: '前缀', dataIndex: 'prefix', key: 'prefix' },
  { title: '对象数', dataIndex: 'object_count', key: 'object_count', width: 120 },
  { title: '总大小', dataIndex: 'total_bytes', key: 'total_bytes', width: 140 },
]

const objectColumns = [
  { title: '对象名', dataIndex: 'object_name', key: 'object_name', ellipsis: true },
  { title: '最后修改时间', dataIndex: 'last_modified', key: 'last_modified', width: 220 },
  { title: '引用数', dataIndex: 'referenced_by_count', key: 'referenced_by_count', width: 100 },
]

const referenceColumns = [
  { title: '引用类型', dataIndex: 'reference_type', key: 'reference_type', width: 140 },
  { title: '记录 ID', dataIndex: 'record_id', key: 'record_id', width: 100 },
  { title: '字段', dataIndex: 'field_name', key: 'field_name', width: 180 },
  { title: '对象名', dataIndex: 'object_name', key: 'object_name', ellipsis: true },
  { title: '修复能力', dataIndex: 'repairable', key: 'repairable', width: 120 },
]

const policyColumns = [
  { title: '名称', dataIndex: 'name', key: 'name', width: 140 },
  { title: '前缀', dataIndex: 'prefix', key: 'prefix', width: 160 },
  { title: '保留天数', dataIndex: 'retention_days', key: 'retention_days', width: 100 },
  { title: '上限 (GB)', dataIndex: 'max_size_gb', key: 'max_size_gb', width: 120 },
  { title: '状态', dataIndex: 'enabled', key: 'enabled', width: 100 },
  { title: '描述', dataIndex: 'description', key: 'description', ellipsis: true },
  { title: '操作', key: 'actions', width: 160 },
]

onMounted(async () => {
  await Promise.all([loadStats(), loadPolicies()])
})

async function loadStats() {
  statsLoading.value = true
  try {
    stats.value = await storageApi.stats()
  } catch (e: any) {
    message.error(e?.message || '加载存储统计失败')
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
    message.error(e?.message || '加载清理策略失败')
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
    message.error(e?.message || '加载清理预览失败')
  } finally {
    previewLoading.value = false
  }
}

function handleExecute() {
  const objectNames = preview.value?.deletable_objects.map((item) => item.object_name) || []
  const orphanCount = preview.value?.orphan_reference_count || 0
  Modal.confirm({
    title: '确认执行存储清理？',
    content: `将删除 ${objectNames.length} 个对象${repairOrphans.value ? `，并尝试修复 ${orphanCount} 个孤儿引用` : ''}。`,
    okText: '确认执行',
    cancelText: '取消',
    async onOk() {
      executeLoading.value = true
      try {
        result.value = await storageApi.executeCleanup({
          object_names: objectNames,
          repair_orphan_references: repairOrphans.value,
        })
        message.success('存储清理执行完成')
        await Promise.all([loadStats(), loadPreview()])
      } catch (e: any) {
        message.error(e?.message || '执行存储清理失败')
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
    message.warning('请填写名称与前缀')
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
      message.success('策略已更新')
    } else {
      await storageApi.createPolicy(payload)
      message.success('策略已创建')
    }
    policyDrawerVisible.value = false
    await loadPolicies()
  } catch (e: any) {
    message.error(e?.response?.data?.detail || e?.message || '保存策略失败')
  } finally {
    policySaving.value = false
  }
}

async function handleDeletePolicy(record: StoragePolicyItem) {
  try {
    await storageApi.deletePolicy(record.id)
    message.success('策略已删除')
    await loadPolicies()
  } catch (e: any) {
    message.error(e?.response?.data?.detail || e?.message || '删除策略失败')
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
