<template>
  <a-drawer
    :open="open"
    :width="760"
    :title="t('recording_history.title')"
    destroy-on-close
    @close="handleClose"
  >
    <div class="recording-history-header">
      <p class="history-subtitle">{{ t('recording_history.subtitle') }}</p>
      <a-space wrap class="history-filters">
        <a-segmented v-model:value="statusFilter" :options="statusOptions" />
        <a-segmented v-if="!props.kind" v-model:value="kindFilter" :options="kindOptions" />
        <a-button size="small" :loading="loading" @click="loadRecords">
          <ReloadOutlined /> {{ t('common.refresh') }}
        </a-button>
      </a-space>
    </div>

    <a-alert
      v-if="props.mode === 'pick'"
      type="info"
      show-icon
      :message="t('recording_history.pick_hint')"
      style="margin-bottom: 12px"
    />

    <a-spin :spinning="loading">
      <a-empty
        v-if="!filteredRecords.length"
        :description="t('recording_history.empty_title')"
        style="margin: 36px 0"
      >
        <template #image />
        <p class="empty-hint">{{ t('recording_history.empty_hint') }}</p>
      </a-empty>

      <div v-else class="record-list">
        <div v-for="record in filteredRecords" :key="record.id" class="record-card">
          <div class="record-card-top">
            <div class="record-title-row">
              <strong class="record-title">{{ record.title }}</strong>
              <a-tag :color="record.kind === 'web' ? 'blue' : 'purple'">
                {{ t(`recording_history.kind_${record.kind}`) }}
              </a-tag>
              <a-tag>{{ sourceLabel(record.source) }}</a-tag>
              <a-tag :color="statusColor(record.status)">
                {{ t(`recording_history.status_${record.status}`) }}
              </a-tag>
            </div>
            <span class="record-time">{{ formatTime(record.updated_at) }}</span>
          </div>

          <div class="record-meta">
            <span>{{ t('recording_history.steps_summary', { steps: record.steps_count, assertions: record.assertion_count }) }}</span>
            <span v-if="record.browser">· {{ record.browser }}</span>
            <span v-if="record.target_url" class="record-url" :title="record.target_url">
              · {{ t('recording_history.target_url') }}: {{ record.target_url }}
            </span>
            <span v-if="record.device_serial">
              · {{ t('recording_history.device') }}: {{ record.device_serial }}
            </span>
            <a-button
              v-if="record.case_id"
              type="link"
              size="small"
              class="inline-link-btn"
              @click="emit('open-case', record.case_id)"
            >
              {{ t('recording_history.linked_case', { id: record.case_id }) }}
            </a-button>
          </div>

          <div
            v-if="record.summary?.error || record.summary?.artifact_error"
            class="record-warning"
          >
            {{ String(record.summary?.error || record.summary?.artifact_error) }}
          </div>

          <div v-if="hasArtifacts(record)" class="record-artifacts">
            <span class="artifact-label">{{ t('recording_history.evidence_section') }}:</span>
            <a
              v-if="safeArtifactUrl(record.artifacts.trace?.url)"
              :href="safeArtifactUrl(record.artifacts.trace?.url) ?? undefined"
              target="_blank"
              rel="noopener noreferrer"
              class="artifact-link"
            >
              {{ t('recording_history.artifact_trace') }}
            </a>
            <a
              v-if="safeArtifactUrl(record.artifacts.har?.url)"
              :href="safeArtifactUrl(record.artifacts.har?.url) ?? undefined"
              target="_blank"
              rel="noopener noreferrer"
              class="artifact-link"
            >
              {{ t('recording_history.artifact_har') }}
            </a>
            <a
              v-if="safeArtifactUrl(record.artifacts.report?.url)"
              :href="safeArtifactUrl(record.artifacts.report?.url) ?? undefined"
              target="_blank"
              rel="noopener noreferrer"
              class="artifact-link"
            >
              {{ t('recording_history.artifact_report') }}
            </a>
          </div>

          <div class="record-actions">
            <a-space size="small" wrap>
              <a-button
                type="primary"
                size="small"
                :disabled="!props.canModify || !record.steps_count"
                @click="handleRestore(record)"
              >
                {{
                  props.mode === 'pick'
                    ? t('recording_history.restore_draft')
                    : t('recording_history.restore_to_case')
                }}
              </a-button>
              <a-button
                v-if="record.steps_count > 0"
                size="small"
                @click="toggleExpand(record.id)"
              >
                {{
                  expandedRecordId === record.id
                    ? t('recording_history.hide_steps')
                    : t('recording_history.preview_steps', { count: record.steps_count })
                }}
              </a-button>
              <a-button
                v-if="record.steps_count > 0"
                size="small"
                @click="copySteps(record)"
              >
                <CopyOutlined /> {{ t('recording_history.copy_steps') }}
              </a-button>
            </a-space>

            <a-popconfirm
              v-if="props.canModify"
              :title="t('recording_history.delete_confirm')"
              @confirm="handleDelete(record)"
            >
              <a-button size="small" danger :loading="deletingId === record.id">
                <DeleteOutlined /> {{ t('recording_history.delete') }}
              </a-button>
            </a-popconfirm>
          </div>

          <div v-if="expandedRecordId === record.id" class="steps-preview">
            <div v-for="(step, idx) in record.steps" :key="`${record.id}-step-${idx}`" class="preview-step-row">
              <span class="preview-step-index">{{ idx + 1 }}</span>
              <a-tag :color="isAssertionAction(step.action) ? 'green' : 'blue'">{{ step.action }}</a-tag>
              <span class="preview-step-name">{{ step.name }}</span>
            </div>
          </div>
        </div>
      </div>
    </a-spin>
  </a-drawer>
</template>

<script setup lang="ts">
import { CopyOutlined, DeleteOutlined, ReloadOutlined } from '@ant-design/icons-vue'
import { message } from 'ant-design-vue'
import { computed, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'

import {
  recordingRecordApi,
  type RecordingKind,
  type RecordingRecordItem,
  type RecordingStatus,
} from '@/api'
import { safeArtifactUrl } from '@/utils/recordingDraft'

const props = withDefaults(
  defineProps<{
    open: boolean
    projectId?: number | null
    kind?: RecordingKind
    initialKind?: RecordingKind | 'all'
    mode?: 'manage' | 'pick'
    canModify?: boolean
  }>(),
  {
    projectId: null,
    kind: undefined,
    initialKind: 'all',
    mode: 'manage',
    canModify: true,
  },
)

const emit = defineEmits<{
  'update:open': [value: boolean]
  close: []
  restore: [record: RecordingRecordItem]
  'open-case': [caseId: number]
  deleted: [recordId: number]
  loaded: [records: RecordingRecordItem[]]
}>()

const { t } = useI18n()

const loading = ref(false)
const deletingId = ref<number | null>(null)
const records = ref<RecordingRecordItem[]>([])
const statusFilter = ref<'all' | RecordingStatus>('all')
const kindFilter = ref<'all' | RecordingKind>(props.kind || props.initialKind || 'all')
const expandedRecordId = ref<number | null>(null)

const statusOptions = computed(() => [
  { label: t('recording_history.filter_all'), value: 'all' },
  { label: t('recording_history.filter_draft'), value: 'draft' },
  { label: t('recording_history.filter_saved'), value: 'saved' },
])

const kindOptions = computed(() => [
  { label: t('recording_history.filter_all'), value: 'all' },
  { label: 'Web', value: 'web' },
  { label: 'App', value: 'android' },
])

const filteredRecords = computed(() =>
  records.value.filter((item) => {
    if (props.kind && item.kind !== props.kind) return false
    if (!props.kind && kindFilter.value !== 'all' && item.kind !== kindFilter.value) return false
    if (statusFilter.value !== 'all' && item.status !== statusFilter.value) return false
    return true
  }),
)

function statusColor(status: RecordingStatus): string {
  if (status === 'saved') return 'green'
  if (status === 'draft') return 'orange'
  if (status === 'error') return 'red'
  return 'default'
}

function sourceLabel(source: string): string {
  const key = `recording_history.source_${source}`
  const translated = t(key)
  return translated === key ? source : translated
}

function isAssertionAction(action: string): boolean {
  return String(action || '').startsWith('assert_')
}

function hasArtifacts(record: RecordingRecordItem): boolean {
  return Boolean(
    safeArtifactUrl(record.artifacts?.trace?.url)
    || safeArtifactUrl(record.artifacts?.har?.url)
    || safeArtifactUrl(record.artifacts?.report?.url),
  )
}

function formatTime(value: string): string {
  if (!value) return ''
  const dt = new Date(value)
  if (Number.isNaN(dt.getTime())) return value
  return dt.toLocaleString()
}

function toggleExpand(recordId: number): void {
  expandedRecordId.value = expandedRecordId.value === recordId ? null : recordId
}

async function loadRecords(): Promise<void> {
  if (!props.projectId) {
    records.value = []
    return
  }
  loading.value = true
  try {
    const items = await recordingRecordApi.list({
      project_id: props.projectId,
      ...(props.kind ? { kind: props.kind } : {}),
      limit: 50,
    })
    records.value = Array.isArray(items) ? items : []
    emit('loaded', records.value)
  } catch (err: unknown) {
    message.error(err instanceof Error ? err.message : t('recording_history.load_failed'))
  } finally {
    loading.value = false
  }
}

function handleRestore(record: RecordingRecordItem): void {
  emit('restore', record)
}

async function copySteps(record: RecordingRecordItem): Promise<void> {
  const text = JSON.stringify(record.steps || [], null, 2)
  if (typeof navigator !== 'undefined' && navigator.clipboard?.writeText) {
    await navigator.clipboard.writeText(text)
    message.success(t('recording_history.copied'))
  }
}

async function handleDelete(record: RecordingRecordItem): Promise<void> {
  deletingId.value = record.id
  try {
    await recordingRecordApi.delete(record.id)
    records.value = records.value.filter((item) => item.id !== record.id)
    if (expandedRecordId.value === record.id) {
      expandedRecordId.value = null
    }
    emit('deleted', record.id)
    emit('loaded', records.value)
    message.success(t('recording_history.deleted'))
  } catch (err: unknown) {
    message.error(err instanceof Error ? err.message : t('recording_history.delete_failed'))
  } finally {
    deletingId.value = null
  }
}

function handleClose(): void {
  emit('update:open', false)
  emit('close')
}

watch(
  () => [props.open, props.projectId, props.kind],
  ([isOpen]) => {
    if (!isOpen) return
    kindFilter.value = props.kind || props.initialKind || 'all'
    expandedRecordId.value = null
    void loadRecords()
  },
  { immediate: true },
)

defineExpose({
  loadRecords,
  filteredRecords,
})
</script>

<style scoped>
.recording-history-header {
  display: flex;
  flex-direction: column;
  gap: 10px;
  margin-bottom: 14px;
}

.history-subtitle {
  margin: 0;
  color: var(--atp-text-secondary, #64748b);
  font-size: 13px;
}

.history-filters {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.empty-hint {
  margin: 0;
  color: var(--atp-text-secondary, #64748b);
  font-size: 12px;
}

.record-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.record-card {
  border: 1px solid var(--atp-border, #e2e8f0);
  border-radius: 10px;
  padding: 12px 14px;
  background: var(--atp-surface, #ffffff);
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.record-card-top {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 10px;
}

.record-title-row {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 6px;
}

.record-title {
  font-size: 14px;
  line-height: 1.4;
}

.record-time {
  font-size: 12px;
  color: var(--atp-text-secondary, #64748b);
  white-space: nowrap;
}

.record-meta {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 6px;
  font-size: 12px;
  color: var(--atp-text-secondary, #475569);
}

.record-url {
  max-width: 340px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.inline-link-btn {
  padding: 0 4px;
  height: auto;
}

.record-warning {
  font-size: 12px;
  color: #b91c1c;
  background: #fef2f2;
  border-radius: 6px;
  padding: 6px 10px;
}

.record-artifacts {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 10px;
  font-size: 12px;
  padding: 6px 10px;
  border-radius: 6px;
  background: rgba(15, 118, 110, 0.06);
}

.artifact-label {
  color: var(--atp-text-secondary, #475569);
  font-weight: 500;
}

.artifact-link {
  color: #0f766e;
  font-weight: 500;
}

.record-actions {
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 2px;
}

.steps-preview {
  margin-top: 6px;
  padding: 8px 10px;
  border-radius: 8px;
  background: rgba(15, 23, 42, 0.03);
  max-height: 220px;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.preview-step-row {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 12px;
}

.preview-step-index {
  width: 20px;
  color: #64748b;
  text-align: right;
  font-variant-numeric: tabular-nums;
}

.preview-step-name {
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
</style>
