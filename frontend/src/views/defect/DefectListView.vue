<template>
  <div class="defect-page">
    <header class="defect-hero">
      <div class="hero-copy">
        <div class="hero-kicker">{{ t('defect.kicker') }}</div>
        <h1>{{ t('defect.title') }}</h1>
        <p>{{ t('defect.subtitle') }}</p>
      </div>
      <div class="hero-actions">
        <a-select
          v-model:value="projectId"
          allow-clear
          show-search
          :filter-option="filterProject"
          :placeholder="t('defect.project')"
          :options="projectOptions"
          style="min-width: 190px"
          @change="onProjectChange"
        />
        <a-button @click="loadDefects">{{ t('defect.refresh') }}</a-button>
        <a-button type="primary" @click="openCreate()">{{ t('defect.new') }}</a-button>
      </div>
    </header>

    <a-alert class="defect-note" type="info" show-icon :message="t('defect.intro')" />

    <section class="defect-summary" aria-label="defect summary">
      <div class="summary-card summary-card-accent">
        <span class="summary-label">{{ t('defect.status.open') }}</span>
        <strong>{{ openCount }}</strong>
        <span class="summary-hint">{{ t('defect.status.in_progress') }} · {{ inProgressCount }}</span>
      </div>
      <div class="summary-card">
        <span class="summary-label">{{ t('defect.table.evidence') }}</span>
        <strong>{{ evidenceCount }}</strong>
        <span class="summary-hint">{{ t('defect.evidence.linked_runs', { count: evidenceCount }) }}</span>
      </div>
      <div class="summary-card">
        <span class="summary-label">{{ t('defect.table.occurrence') }}</span>
        <strong>{{ occurrenceCount }}</strong>
        <span class="summary-hint">{{ t('defect.status.resolved') }} · {{ resolvedCount }}</span>
      </div>
    </section>

    <a-card class="defect-panel" :bordered="false">
      <div class="filter-row">
        <span class="filter-caption">{{ t('defect.filters') }}</span>
        <a-select v-model:value="statusFilter" allow-clear :placeholder="t('defect.status_filter')" :options="statusOptions" @change="reloadFirstPage" />
        <a-select v-model:value="priorityFilter" allow-clear :placeholder="t('defect.priority_filter')" :options="priorityOptions" @change="reloadFirstPage" />
        <a-select v-model:value="severityFilter" allow-clear :placeholder="t('defect.severity_filter')" :options="severityOptions" @change="reloadFirstPage" />
      </div>

      <a-table
        :columns="columns"
        :data-source="defects"
        :loading="loading"
        :pagination="false"
        row-key="id"
        size="middle"
      >
        <template #bodyCell="{ column, record }">
          <template v-if="column.key === 'id'">
            <span class="defect-id">#{{ record.id }}</span>
          </template>
          <template v-else-if="column.key === 'title'">
            <button class="title-button" type="button" @click="openDetail(asDefect(record))">
              <span>{{ record.title }}</span>
              <small v-if="record.case_id">Case #{{ record.case_id }}</small>
            </button>
          </template>
          <template v-else-if="column.key === 'status'">
            <a-tag :color="statusColor(record.status)">{{ t(`defect.status.${record.status}`) }}</a-tag>
          </template>
          <template v-else-if="column.key === 'priority'">
            <span :class="['priority-mark', `priority-${record.priority.toLowerCase()}`]">{{ record.priority }}</span>
          </template>
          <template v-else-if="column.key === 'severity'">
            {{ t(`defect.severity.${record.severity}`) }}
          </template>
          <template v-else-if="column.key === 'evidence'">
            <a-badge :count="record.run_links.length" :show-zero="true" :number-style="{ backgroundColor: record.run_links.length ? '#315efb' : '#c5cad8' }" />
          </template>
          <template v-else-if="column.key === 'updated_at'">
            <span class="muted-text">{{ formatTime(record.updated_at) }}</span>
          </template>
          <template v-else-if="column.key === 'actions'">
            <a-button type="link" size="small" @click="openDetail(asDefect(record))">{{ t('common.view_detail') }}</a-button>
          </template>
        </template>
      </a-table>

      <a-empty v-if="!loading && !defects.length" :description="t('common.no_data')" class="empty-state" />
      <div class="table-footer">
        <span>{{ t('common.selected_count', { count: total }) }}</span>
        <a-pagination v-model:current="page" :page-size="pageSize" :total="total" size="small" show-less-items @change="loadDefects" />
      </div>
    </a-card>

    <a-modal
      v-model:open="createOpen"
      :title="t('defect.form.new_title')"
      :ok-text="t('defect.form.save')"
      :confirm-loading="saving"
      :ok-button-props="{ disabled: !canSubmitCreate }"
      width="620px"
      @ok="submitCreate"
      @cancel="closeCreate"
    >
      <a-alert v-if="contextRunId" class="context-alert" type="success" show-icon :message="contextRunLabel" :description="t('defect.form.run_context_hint')" />
      <a-form layout="vertical">
        <a-form-item :label="t('defect.form.title')" required>
          <a-input v-model:value="createForm.title" :placeholder="t('defect.form.title_placeholder')" />
        </a-form-item>
        <a-row :gutter="12">
          <a-col :span="12">
            <a-form-item :label="t('defect.form.priority')">
              <a-select v-model:value="createForm.priority" :options="priorityOptions" />
            </a-form-item>
          </a-col>
          <a-col :span="12">
            <a-form-item :label="t('defect.form.severity')">
              <a-select v-model:value="createForm.severity" :options="severityOptions" />
            </a-form-item>
          </a-col>
        </a-row>
        <a-form-item :label="t('defect.form.assignee')">
          <a-select v-model:value="createForm.assignee_id" allow-clear :placeholder="t('defect.form.unassigned')" :options="assigneeOptions" :loading="membersLoading" />
        </a-form-item>
        <a-form-item :label="t('defect.form.labels')">
          <a-input v-model:value="createForm.labels" :placeholder="t('defect.form.labels_placeholder')" />
        </a-form-item>
        <a-form-item :label="t('defect.form.description')">
          <a-textarea v-model:value="createForm.description" :rows="5" :placeholder="t('defect.form.description_placeholder')" />
        </a-form-item>
      </a-form>
    </a-modal>

    <a-drawer v-model:open="detailOpen" :title="t('defect.detail.title')" width="620px">
      <template v-if="selectedDefect">
        <div class="detail-heading">
          <span class="defect-id">#{{ selectedDefect.id }}</span>
          <h2>{{ selectedDefect.title }}</h2>
        </div>
        <a-descriptions :column="1" size="small" bordered>
          <a-descriptions-item :label="t('defect.table.status')">
            <a-select v-model:value="editForm.status" size="small" :options="statusOptions" style="width: 150px" />
          </a-descriptions-item>
          <a-descriptions-item :label="t('defect.form.priority')">
            <a-select v-model:value="editForm.priority" size="small" :options="priorityOptions" style="width: 150px" />
          </a-descriptions-item>
          <a-descriptions-item :label="t('defect.form.severity')">
            <a-select v-model:value="editForm.severity" size="small" :options="severityOptions" style="width: 150px" />
          </a-descriptions-item>
          <a-descriptions-item :label="t('defect.form.assignee')">
            <a-select v-model:value="editForm.assignee_id" allow-clear size="small" :placeholder="t('defect.form.unassigned')" :options="assigneeOptions" :loading="membersLoading" style="width: 220px" />
          </a-descriptions-item>
          <a-descriptions-item :label="t('defect.detail.created_at')">{{ formatTime(selectedDefect.created_at) }}</a-descriptions-item>
          <a-descriptions-item :label="t('defect.detail.updated_at')">{{ formatTime(selectedDefect.updated_at) }}</a-descriptions-item>
        </a-descriptions>
        <div class="detail-section">
          <div class="detail-section-title">{{ t('defect.detail.description') }}</div>
          <p class="detail-description">{{ selectedDefect.description || t('defect.detail.no_description') }}</p>
        </div>
        <div class="detail-section">
          <div class="detail-section-title">{{ t('defect.detail.run_links') }}</div>
          <a-empty v-if="!selectedDefect.run_links.length" :description="t('defect.detail.no_evidence')" />
          <div v-for="link in selectedDefect.run_links" v-else :key="link.id" class="evidence-card">
            <div class="evidence-card-head">
              <a-tag color="geekblue">{{ t(`defect.evidence.run_type.${link.run_type}`) }}</a-tag>
              <span>#{{ link.run_id }}</span>
              <a-button type="link" size="small" @click="openRun(link)">{{ t('defect.detail.open_run') }}</a-button>
            </div>
            <pre>{{ formatEvidence(link.evidence) }}</pre>
          </div>
        </div>
        <div class="detail-section external-section">
          <div class="detail-section-title external-title-row">
            <span>{{ t('defect.detail.external_links') }}</span>
            <span v-if="canManageExternal" class="external-actions">
              <a-button size="small" type="primary" :disabled="!hasEnabledExternalTracker" @click="openExternalModal('create')">
                {{ t('defect.external.create') }}
              </a-button>
              <a-button size="small" :disabled="!externalTrackers.length" @click="openExternalModal('link')">
                {{ t('defect.external.link') }}
              </a-button>
            </span>
          </div>
          <a-empty v-if="!selectedDefect.external_links?.length" :description="t('defect.external.empty')" />
          <div v-for="link in selectedDefect.external_links || []" v-else :key="link.id" class="external-card">
            <div class="external-card-head">
              <div>
                <a-tag :color="externalTrackerColor(link.tracker_type)">{{ externalTrackerLabel(link.tracker_type) }}</a-tag>
                <strong>{{ link.external_key }}</strong>
              </div>
              <a-tag :color="externalSyncColor(link.sync_state)">{{ externalSyncLabel(link.sync_state) }}</a-tag>
            </div>
            <a
              v-if="link.external_url"
              class="external-link"
              :href="link.external_url"
              target="_blank"
              rel="noopener noreferrer"
            >
              {{ link.external_title || link.external_url }}
            </a>
            <span v-else class="muted-text">{{ link.external_title || t('defect.external.no_url') }}</span>
            <div class="external-card-meta">
              <span>{{ t('defect.external.status') }}：{{ link.external_status || '—' }}</span>
              <span v-if="link.last_synced_at">{{ formatTime(link.last_synced_at) }}</span>
            </div>
            <div v-if="link.last_error" class="external-error">{{ link.last_error }}</div>
            <div v-if="canManageExternal" class="external-card-actions">
              <a-button size="small" :loading="syncingExternalId === link.id" @click="syncExternalLink(link)">
                {{ t('defect.external.sync') }}
              </a-button>
              <a-button size="small" type="link" danger @click="unlinkExternalLink(link)">
                {{ t('defect.external.unlink') }}
              </a-button>
            </div>
          </div>
        </div>
        <a-button type="primary" :loading="saving" @click="submitUpdate">{{ t('defect.form.update') }}</a-button>
      </template>
    </a-drawer>
    <a-modal
      v-model:open="externalModalOpen"
      :title="externalModalTitle"
      :confirm-loading="externalSaving"
      :ok-button-props="{ disabled: !canSubmitExternal }"
      @ok="submitExternal"
      @cancel="closeExternalModal"
    >
      <a-form layout="vertical">
        <a-form-item :label="t('defect.external.tracker')" required>
          <a-select v-model:value="externalForm.tracker_id" :options="externalTrackerOptions" />
        </a-form-item>
        <template v-if="externalMode === 'link'">
          <a-form-item :label="t('defect.external.key')" required>
            <a-input v-model:value="externalForm.external_key" :placeholder="t('defect.external.key_placeholder')" />
          </a-form-item>
          <a-form-item :label="t('defect.external.url')">
            <a-input v-model:value="externalForm.external_url" :placeholder="t('defect.external.url_placeholder')" />
          </a-form-item>
          <a-form-item :label="t('defect.external.title')">
            <a-input v-model:value="externalForm.external_title" />
          </a-form-item>
          <a-form-item :label="t('defect.external.status')">
            <a-input v-model:value="externalForm.external_status" />
          </a-form-item>
        </template>
        <p class="external-form-hint">
          {{ externalMode === 'create' ? t('defect.external.create_hint') : t('defect.external.link_hint') }}
        </p>
      </a-form>
    </a-modal>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { message, Modal } from 'ant-design-vue'
import { useI18n } from 'vue-i18n'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import {
  bugTrackerApi,
  defectApi,
  projectApi,
  projectMemberApi,
  type DefectItem,
  type DefectExternalLinkItem,
  type DefectPriority,
  type DefectRunLinkItem,
  type DefectRunType,
  type DefectSeverity,
  type DefectStatus,
  type BugTrackerItem,
  type BugTrackerType,
  type ProjectItem,
  type ProjectMemberItem,
} from '@/api'

const { t } = useI18n()
const route = useRoute()
const router = useRouter()
const auth = useAuthStore()

const projects = ref<ProjectItem[]>([])
const members = ref<ProjectMemberItem[]>([])
const defects = ref<DefectItem[]>([])
const selectedDefect = ref<DefectItem | null>(null)
const projectId = ref<number | undefined>(positiveInt(route.query.project_id))
const requestedDefectId = ref<number | undefined>(positiveInt(route.query.defect_id))
const statusFilter = ref<DefectStatus | undefined>(undefined)
const priorityFilter = ref<DefectPriority | undefined>(undefined)
const severityFilter = ref<DefectSeverity | undefined>(undefined)
const page = ref(1)
const pageSize = 20
const total = ref(0)
const loading = ref(false)
const membersLoading = ref(false)
const createOpen = ref(false)
const detailOpen = ref(false)
const saving = ref(false)
const externalTrackers = ref<BugTrackerItem[]>([])
const externalModalOpen = ref(false)
const externalSaving = ref(false)
const syncingExternalId = ref<number | null>(null)
const externalMode = ref<'create' | 'link'>('create')
const externalForm = reactive({
  tracker_id: undefined as number | undefined,
  external_key: '',
  external_url: '',
  external_title: '',
  external_status: '',
})
const contextRunType = ref<DefectRunType | undefined>(validRunType(route.query.run_type))
const contextRunId = ref<number | undefined>(positiveInt(route.query.run_id))
const linkedRunView = computed(() => route.query.view === 'linked')

const createForm = reactive({
  title: '',
  description: '',
  priority: 'P2' as DefectPriority,
  severity: 'major' as DefectSeverity,
  assignee_id: undefined as number | undefined,
  labels: '',
})
const editForm = reactive({
  status: 'open' as DefectStatus,
  priority: 'P2' as DefectPriority,
  severity: 'major' as DefectSeverity,
  assignee_id: undefined as number | undefined,
})

const projectOptions = computed(() => projects.value.map((item) => ({ label: item.name, value: item.id })))
const assigneeOptions = computed(() => members.value.map((item) => ({ label: `${item.username} · ${item.role}`, value: item.user_id })))
const statusOptions = computed(() => (['open', 'in_progress', 'resolved', 'reopened', 'closed'] as DefectStatus[]).map((value) => ({ label: t(`defect.status.${value}`), value })))
const priorityOptions = computed(() => (['P0', 'P1', 'P2', 'P3'] as DefectPriority[]).map((value) => ({ label: value, value })))
const severityOptions = computed(() => (['blocker', 'critical', 'major', 'minor', 'trivial'] as DefectSeverity[]).map((value) => ({ label: t(`defect.severity.${value}`), value })))
const columns = computed(() => [
  { title: t('defect.table.id'), key: 'id', width: 72 },
  { title: t('defect.table.title'), key: 'title', ellipsis: true },
  { title: t('defect.table.status'), key: 'status', width: 120 },
  { title: t('defect.table.priority'), key: 'priority', width: 90 },
  { title: t('defect.table.severity'), key: 'severity', width: 110 },
  { title: t('defect.table.occurrence'), dataIndex: 'occurrence_count', key: 'occurrence', width: 100 },
  { title: t('defect.table.evidence'), key: 'evidence', width: 90 },
  { title: t('defect.table.updated_at'), key: 'updated_at', width: 150 },
  { title: t('defect.table.actions'), key: 'actions', width: 110 },
])

const openCount = computed(() => defects.value.filter((item) => item.status === 'open').length)
const inProgressCount = computed(() => defects.value.filter((item) => item.status === 'in_progress').length)
const resolvedCount = computed(() => defects.value.filter((item) => item.status === 'resolved' || item.status === 'closed').length)
const evidenceCount = computed(() => defects.value.reduce((sum, item) => sum + item.run_links.length, 0))
const occurrenceCount = computed(() => defects.value.reduce((sum, item) => sum + item.occurrence_count, 0))
const canSubmitCreate = computed(() => Boolean(createForm.title.trim() && (contextRunId.value || projectId.value)))
const canManageExternal = computed(() => ['admin', 'engineer'].includes(auth.user?.role || ''))
const contextRunLabel = computed(() => contextRunType.value && contextRunId.value
  ? `${t(`defect.evidence.run_type.${contextRunType.value}`)} #${contextRunId.value}`
  : '')
const externalTrackerOptions = computed(() => externalTrackers.value.map((item) => ({
  label: `${item.name} · ${externalTrackerLabel(item.tracker_type)}${item.is_enabled ? '' : ` · ${t('defect.external.disabled')}`}`,
  value: item.id,
  disabled: externalMode.value === 'create' && !item.is_enabled,
})))
const hasEnabledExternalTracker = computed(() => externalTrackers.value.some((item) => item.is_enabled))
const externalModalTitle = computed(() => externalMode.value === 'create'
  ? t('defect.external.create_title')
  : t('defect.external.link_title'))
const canSubmitExternal = computed(() => Boolean(
  externalForm.tracker_id && (externalMode.value === 'create' || externalForm.external_key.trim()),
))

function positiveInt(value: unknown) {
  const parsed = Number(Array.isArray(value) ? value[0] : value)
  return Number.isInteger(parsed) && parsed > 0 ? parsed : undefined
}

function validRunType(value: unknown): DefectRunType | undefined {
  const raw = Array.isArray(value) ? value[0] : value
  return ['case', 'suite', 'plan', 'android', 'performance'].includes(raw as string) ? raw as DefectRunType : undefined
}

function filterProject(input: string, option: any) {
  return String(option.label || '').toLowerCase().includes(input.toLowerCase())
}

function asDefect(value: unknown) {
  return value as DefectItem
}

function formatTime(value?: string | null) {
  return value ? value.slice(0, 19).replace('T', ' ') : '-'
}

function formatEvidence(value: Record<string, unknown>) {
  return JSON.stringify(value, null, 2)
}

function statusColor(status: DefectStatus) {
  return ({ open: 'orange', in_progress: 'blue', resolved: 'green', reopened: 'purple', closed: 'default' } as Record<DefectStatus, string>)[status]
}

function externalTrackerLabel(type: BugTrackerType) {
  return ({ jira: 'Jira', zentao: '禅道', github: 'GitHub Issues', gitlab: 'GitLab Issues' } as Record<BugTrackerType, string>)[type]
}

function externalTrackerColor(type: BugTrackerType) {
  return ({ jira: 'blue', zentao: 'purple', github: 'default', gitlab: 'orange' } as Record<BugTrackerType, string>)[type]
}

function externalSyncLabel(state: DefectExternalLinkItem['sync_state']) {
  return t(`defect.external.sync_state.${state}`)
}

function externalSyncColor(state: DefectExternalLinkItem['sync_state']) {
  return ({ linked: 'processing', synced: 'success', error: 'error' } as Record<DefectExternalLinkItem['sync_state'], string>)[state]
}

async function loadProjects() {
  try {
    projects.value = await projectApi.list()
  } catch {
    projects.value = []
  }
}

async function loadMembers(targetProjectId = projectId.value) {
  if (!targetProjectId) {
    members.value = []
    return
  }
  membersLoading.value = true
  try {
    members.value = await projectMemberApi.list(targetProjectId)
  } catch {
    members.value = []
    message.error(t('defect.msg.assignee_load_failed'))
  } finally {
    membersLoading.value = false
  }
}

async function loadExternalTrackers(targetProjectId: number) {
  try {
    externalTrackers.value = await bugTrackerApi.list({ project_id: targetProjectId })
  } catch {
    externalTrackers.value = []
    message.error(t('defect.external.tracker_load_failed'))
  }
}

async function loadDefects() {
  loading.value = true
  try {
    const result = await defectApi.list({
      project_id: projectId.value,
      run_type: linkedRunView.value ? contextRunType.value : undefined,
      run_id: linkedRunView.value ? contextRunId.value : undefined,
      status: statusFilter.value,
      priority: priorityFilter.value,
      severity: severityFilter.value,
      page: page.value,
      page_size: pageSize,
    })
    defects.value = result.items.map((item) => ({ ...item, external_links: item.external_links || [] }))
    total.value = result.total
    const requested = requestedDefectId.value
    if (requested) {
      const listed = defects.value.find((item) => item.id === requested)
      if (listed) {
        openDetail(listed)
        requestedDefectId.value = undefined
      } else {
        try {
          const detail = await defectApi.get(requested)
          if (!projectId.value || detail.project_id === projectId.value) {
            openDetail(detail)
            requestedDefectId.value = undefined
          }
        } catch {
          // 目标缺陷不可访问时保留列表，避免影响正常使用。
        }
      }
    }
  } catch {
    message.error(t('defect.msg.load_failed'))
  } finally {
    loading.value = false
  }
}

function reloadFirstPage() {
  page.value = 1
  void loadDefects()
}

function onProjectChange(value: unknown) {
  const nextProjectId = typeof value === 'number' ? value : positiveInt(value)
  projectId.value = nextProjectId
  page.value = 1
  const query = nextProjectId ? { project_id: String(nextProjectId) } : {}
  void router.replace({ query })
  void loadMembers(nextProjectId)
  void loadDefects()
}

function resetCreateForm() {
  createForm.title = ''
  createForm.description = ''
  createForm.priority = 'P2'
  createForm.severity = 'major'
  createForm.assignee_id = undefined
  createForm.labels = ''
}

function openCreate(fromContext = false) {
  if (!fromContext) {
    contextRunType.value = undefined
    contextRunId.value = undefined
    clearRunContextQuery()
  }
  resetCreateForm()
  createOpen.value = true
  void loadMembers(projectId.value)
}

function clearRunContextQuery() {
  if (route.query.run_type === undefined && route.query.run_id === undefined) return
  const query = { ...route.query }
  delete query.run_type
  delete query.run_id
  void router.replace({ query })
}

function closeCreate() {
  createOpen.value = false
  if (contextRunId.value) {
    contextRunType.value = undefined
    contextRunId.value = undefined
    clearRunContextQuery()
  }
}

function resetExternalForm() {
  externalForm.tracker_id = (externalMode.value === 'create'
    ? externalTrackers.value.find((item) => item.is_enabled)
    : externalTrackers.value[0])?.id
  externalForm.external_key = ''
  externalForm.external_url = ''
  externalForm.external_title = ''
  externalForm.external_status = ''
}

function openExternalModal(mode: 'create' | 'link') {
  if (!selectedDefect.value || !externalTrackers.value.length) return
  externalMode.value = mode
  resetExternalForm()
  externalModalOpen.value = true
}

function closeExternalModal() {
  externalModalOpen.value = false
}

function updateSelectedExternalLink(link: DefectExternalLinkItem) {
  if (!selectedDefect.value) return
  const links = selectedDefect.value.external_links || []
  selectedDefect.value = {
    ...selectedDefect.value,
    external_links: [...links.filter((item) => item.id !== link.id), link],
  }
  const index = defects.value.findIndex((item) => item.id === selectedDefect.value?.id)
  if (index >= 0 && selectedDefect.value) defects.value[index] = selectedDefect.value
}

async function submitExternal() {
  if (!selectedDefect.value || !canSubmitExternal.value || !externalForm.tracker_id) return
  externalSaving.value = true
  try {
    const link = externalMode.value === 'create'
      ? await defectApi.createExternal(selectedDefect.value.id, { tracker_id: externalForm.tracker_id })
      : await defectApi.linkExternal(selectedDefect.value.id, {
        tracker_id: externalForm.tracker_id,
        external_key: externalForm.external_key.trim(),
        external_url: externalForm.external_url.trim() || undefined,
        external_title: externalForm.external_title.trim() || undefined,
        external_status: externalForm.external_status.trim() || undefined,
      })
    updateSelectedExternalLink(link)
    externalModalOpen.value = false
    message.success(t('defect.external.save_success'))
  } catch {
    message.error(t('defect.external.save_failed'))
  } finally {
    externalSaving.value = false
  }
}

async function syncExternalLink(link: DefectExternalLinkItem) {
  if (!selectedDefect.value) return
  syncingExternalId.value = link.id
  try {
    const result = await defectApi.syncExternal(selectedDefect.value.id, link.id, { apply_status: true })
    updateSelectedExternalLink(result.link)
    if (selectedDefect.value) {
      selectedDefect.value = { ...selectedDefect.value, status: result.defect_status }
      editForm.status = result.defect_status
      const index = defects.value.findIndex((item) => item.id === selectedDefect.value?.id)
      if (index >= 0) defects.value[index] = selectedDefect.value
    }
    message.success(t('defect.external.sync_success'))
  } catch {
    message.error(t('defect.external.sync_failed'))
  } finally {
    syncingExternalId.value = null
  }
}

function unlinkExternalLink(link: DefectExternalLinkItem) {
  if (!selectedDefect.value) return
  Modal.confirm({
    title: t('defect.external.unlink_confirm'),
    onOk: async () => {
      try {
        await defectApi.unlinkExternal(selectedDefect.value!.id, link.id)
        selectedDefect.value = {
          ...selectedDefect.value!,
          external_links: (selectedDefect.value!.external_links || []).filter((item) => item.id !== link.id),
        }
        message.success(t('defect.external.unlink_success'))
      } catch {
        message.error(t('defect.external.unlink_failed'))
      }
    },
  })
}

async function submitCreate() {
  if (!canSubmitCreate.value) {
    message.warning(contextRunId.value ? t('defect.form.title') : t('defect.msg.select_project'))
    return
  }
  saving.value = true
  try {
    const result = contextRunType.value && contextRunId.value
      ? await defectApi.createFromRun(contextRunType.value, contextRunId.value, {
        title: createForm.title.trim() || undefined,
        description: createForm.description.trim() || undefined,
        priority: createForm.priority,
        severity: createForm.severity,
        assignee_id: createForm.assignee_id,
      })
      : await defectApi.create({
        project_id: projectId.value as number,
        title: createForm.title.trim(),
        description: createForm.description.trim() || undefined,
        priority: createForm.priority,
        severity: createForm.severity,
        assignee_id: createForm.assignee_id,
        labels: createForm.labels.split(',').map((item) => item.trim()).filter(Boolean),
      })
    closeCreate()
    if (!result.created && result.duplicate_of) {
      message.warning(t('defect.msg.duplicate', { id: result.duplicate_of }))
    } else {
      message.success(t('defect.msg.save_success'))
    }
    await loadDefects()
  } catch {
    message.error(t('defect.msg.save_failed'))
  } finally {
    saving.value = false
  }
}

function openDetail(item: DefectItem) {
  selectedDefect.value = { ...item, external_links: item.external_links || [] }
  editForm.status = item.status
  editForm.priority = item.priority
  editForm.severity = item.severity
  editForm.assignee_id = item.assignee_id ?? undefined
  detailOpen.value = true
  void loadMembers(item.project_id)
  if (canManageExternal.value) void loadExternalTrackers(item.project_id)
}

async function submitUpdate() {
  if (!selectedDefect.value) return
  saving.value = true
  try {
    selectedDefect.value = await defectApi.update(selectedDefect.value.id, {
      status: editForm.status,
      priority: editForm.priority,
      severity: editForm.severity,
      assignee_id: editForm.assignee_id ?? null,
    })
    const index = defects.value.findIndex((item) => item.id === selectedDefect.value?.id)
    if (index >= 0 && selectedDefect.value) defects.value[index] = selectedDefect.value
    message.success(t('defect.msg.update_success'))
  } catch {
    message.error(t('defect.msg.save_failed'))
  } finally {
    saving.value = false
  }
}

function openRun(link: DefectRunLinkItem) {
  if (link.run_type === 'case') {
    void router.push({ name: 'run-detail', params: { runId: link.run_id } })
    return
  }
  void router.push({ path: '/runs', query: { defect_run_type: link.run_type, defect_run_id: String(link.run_id) } })
}

watch(() => route.query, (query) => {
  const nextRunType = validRunType(query.run_type)
  const nextRunId = positiveInt(query.run_id)
  if (nextRunType && nextRunId && (nextRunType !== contextRunType.value || nextRunId !== contextRunId.value)) {
    contextRunType.value = nextRunType
    contextRunId.value = nextRunId
    if (query.view === 'linked') void loadDefects()
    else openCreate(true)
  }
}, { deep: true })

onMounted(async () => {
  await loadProjects()
  await loadMembers()
  await loadDefects()
  if (contextRunType.value && contextRunId.value && !linkedRunView.value) openCreate(true)
})
</script>

<style scoped>
.defect-page {
  --defect-ink: #19233f;
  --defect-muted: #77809a;
  --defect-line: #e7eaf2;
  min-height: calc(100vh - 132px);
  color: var(--defect-ink);
}

.defect-hero {
  display: flex;
  justify-content: space-between;
  gap: 24px;
  align-items: flex-end;
  padding: 24px 2px 22px;
  border-bottom: 1px solid var(--defect-line);
}

.hero-kicker {
  margin-bottom: 8px;
  color: #315efb;
  font-size: 11px;
  font-weight: 800;
  letter-spacing: .16em;
}

.hero-copy h1 {
  margin: 0;
  font-size: clamp(26px, 3vw, 38px);
  letter-spacing: -.04em;
}

.hero-copy p {
  max-width: 650px;
  margin: 9px 0 0;
  color: var(--defect-muted);
  line-height: 1.7;
}

.hero-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  justify-content: flex-end;
}

.defect-note {
  margin: 18px 0;
  border: 0;
  background: #f4f7ff;
}

.defect-summary {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 12px;
  margin-bottom: 18px;
}

.summary-card {
  position: relative;
  min-height: 112px;
  padding: 17px 19px;
  overflow: hidden;
  border: 1px solid var(--defect-line);
  border-radius: 14px;
  background: linear-gradient(135deg, #fff, #fafbff);
}

.summary-card::after {
  position: absolute;
  right: -24px;
  bottom: -36px;
  width: 110px;
  height: 110px;
  content: '';
  border: 1px solid #edf0fa;
  border-radius: 50%;
}

.summary-card-accent {
  border-color: #d8e0ff;
  background: linear-gradient(135deg, #f4f6ff, #fff);
}

.summary-label,
.summary-hint {
  display: block;
  color: var(--defect-muted);
  font-size: 12px;
}

.summary-card strong {
  display: block;
  margin: 7px 0 4px;
  color: var(--defect-ink);
  font-size: 28px;
  line-height: 1;
}

.defect-panel {
  border: 1px solid var(--defect-line);
  box-shadow: 0 10px 32px rgba(27, 38, 72, .04);
}

.filter-row {
  display: flex;
  align-items: center;
  gap: 9px;
  flex-wrap: wrap;
  margin-bottom: 18px;
}

.filter-caption {
  margin-right: 5px;
  color: var(--defect-muted);
  font-size: 12px;
  font-weight: 700;
  letter-spacing: .04em;
}

.filter-row :deep(.ant-select) {
  min-width: 130px;
}

.defect-id {
  color: #315efb;
  font-family: ui-monospace, SFMono-Regular, Consolas, monospace;
  font-size: 12px;
  font-weight: 700;
}

.title-button {
  display: inline-flex;
  flex-direction: column;
  align-items: flex-start;
  padding: 0;
  color: var(--defect-ink);
  border: 0;
  background: transparent;
  text-align: left;
  cursor: pointer;
}

.title-button:hover {
  color: #315efb;
}

.title-button small {
  margin-top: 3px;
  color: var(--defect-muted);
  font-size: 11px;
}

.priority-mark {
  display: inline-flex;
  min-width: 30px;
  justify-content: center;
  padding: 2px 7px;
  border-radius: 5px;
  font-family: ui-monospace, SFMono-Regular, Consolas, monospace;
  font-size: 12px;
  font-weight: 700;
}

.priority-p0 { color: #a8071a; background: #fff1f0; }
.priority-p1 { color: #d4380d; background: #fff2e8; }
.priority-p2 { color: #315efb; background: #f0f5ff; }
.priority-p3 { color: #68718a; background: #f2f3f6; }

.muted-text { color: var(--defect-muted); font-size: 12px; }
.empty-state { padding: 36px 0; }

.table-footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
  padding-top: 18px;
  color: var(--defect-muted);
  font-size: 12px;
}

.context-alert { margin-bottom: 18px; }

.detail-heading {
  display: flex;
  gap: 10px;
  align-items: baseline;
  margin-bottom: 18px;
}

.detail-heading h2 { margin: 0; font-size: 21px; }

.detail-section { margin-top: 24px; }
.detail-section-title { margin-bottom: 9px; font-weight: 700; }
.detail-description { white-space: pre-wrap; color: var(--defect-muted); line-height: 1.7; }
.external-title-row { display: flex; align-items: center; justify-content: space-between; gap: 10px; }
.external-actions { display: flex; flex-wrap: wrap; gap: 6px; }
.external-card { margin-bottom: 10px; padding: 12px 13px; border: 1px solid #dfe5f3; border-radius: 10px; background: linear-gradient(135deg, #fbfcff, #f7f9ff); }
.external-card-head { display: flex; align-items: center; justify-content: space-between; gap: 10px; }
.external-card-head > div { display: flex; align-items: center; gap: 7px; min-width: 0; }
.external-card-head strong { overflow: hidden; color: var(--defect-ink); font-family: ui-monospace, SFMono-Regular, Consolas, monospace; text-overflow: ellipsis; white-space: nowrap; }
.external-link { display: block; margin-top: 8px; overflow: hidden; color: #315efb; font-size: 12px; text-overflow: ellipsis; white-space: nowrap; }
.external-card-meta { display: flex; flex-wrap: wrap; justify-content: space-between; gap: 8px; margin-top: 8px; color: var(--defect-muted); font-size: 11px; }
.external-error { margin-top: 8px; color: #c41d7f; font-size: 11px; line-height: 1.5; }
.external-card-actions { display: flex; justify-content: flex-end; gap: 6px; margin-top: 9px; }
.external-form-hint { margin: 14px 0 0; color: var(--defect-muted); font-size: 12px; line-height: 1.6; }

.evidence-card {
  margin-bottom: 10px;
  padding: 11px 13px;
  border: 1px solid var(--defect-line);
  border-radius: 10px;
  background: #fafbfe;
}

.evidence-card-head { display: flex; align-items: center; gap: 7px; }
.evidence-card-head .ant-btn { margin-left: auto; }
.evidence-card pre { max-height: 240px; margin: 10px 0 0; overflow: auto; color: #52607a; font-size: 11px; white-space: pre-wrap; }

@media (max-width: 820px) {
  .defect-hero { align-items: flex-start; flex-direction: column; }
  .hero-actions { justify-content: flex-start; }
  .defect-summary { grid-template-columns: 1fr; }
  .table-footer { align-items: flex-start; flex-direction: column; }
}

@media (prefers-reduced-motion: reduce) {
  .title-button { transition: none; }
}
</style>
