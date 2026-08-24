<template>
  <div class="review-page">
    <header class="review-hero">
      <div class="hero-mark" aria-hidden="true">R</div>
      <div class="hero-copy">
        <p class="hero-kicker">{{ t('case_reviews.kicker') }}</p>
        <h1>{{ t('case_reviews.title') }}</h1>
        <p class="hero-subtitle">{{ t('case_reviews.subtitle') }}</p>
      </div>
      <div class="hero-actions">
        <a-button @click="goCases">{{ t('menu.cases') }}</a-button>
        <a-button :loading="loading" @click="loadQueue">{{ t('case_reviews.refresh') }}</a-button>
      </div>
    </header>

    <section class="pulse-grid" aria-label="review status summary">
      <button
        v-for="card in summaryCards"
        :key="card.key"
        type="button"
        class="pulse-card"
        :class="[`pulse-${card.key}`, { 'is-selected': reviewStatus === card.key }]"
        @click="selectStatus(card.key)"
      >
        <span class="pulse-label">{{ card.label }}</span>
        <strong>{{ card.value }}</strong>
        <span class="pulse-tail">{{ card.caption }}</span>
      </button>
    </section>

    <section class="filter-strip" aria-label="review filters">
      <a-select
        v-model:value="projectId"
        allow-clear
        show-search
        :filter-option="filterProject"
        :placeholder="t('case_reviews.all_projects')"
        :options="projectOptions"
        class="project-filter"
      />
      <a-input-search
        v-model:value="searchInput"
        allow-clear
        :placeholder="t('case_reviews.search_placeholder')"
        class="keyword-filter"
        @search="applySearch"
      />
      <a-select v-model:value="reviewStatus" :options="statusOptions" class="status-filter" />
      <a-button @click="applySearch">{{ t('common.search') }}</a-button>
    </section>

    <section class="queue-panel">
      <div class="queue-heading">
        <div>
          <p class="section-kicker">{{ t('case_reviews.queue.title') }}</p>
          <h2>{{ t('case_reviews.queue.title') }}</h2>
          <p>{{ t('case_reviews.queue.note') }}</p>
        </div>
        <div class="queue-count">
          <strong>{{ queue.total }}</strong>
          <span>{{ t('case_reviews.statuses.' + reviewStatus) }}</span>
        </div>
      </div>

      <div v-if="selectedRowKeys.length" class="batch-toolbar">
        <span>{{ t('case_reviews.selected', { count: selectedRowKeys.length }) }}</span>
        <a-space wrap>
          <a-button type="primary" @click="openBatch('approve')">{{ t('case_reviews.actions.approve') }}</a-button>
          <a-button danger @click="openBatch('reject')">{{ t('case_reviews.actions.reject') }}</a-button>
          <a-button type="link" @click="selectedRowKeys = []">{{ t('case_reviews.actions.cancel') }}</a-button>
        </a-space>
      </div>

      <a-table
        :data-source="queue.items"
        :columns="columns"
        :loading="loading"
        :pagination="{ current: page, pageSize: queue.page_size, total: queue.total, showSizeChanger: true }"
        :row-selection="rowSelection"
        row-key="id"
        size="middle"
        @change="handleTableChange"
      >
        <template #bodyCell="{ column, record }">
          <template v-if="column.key === 'case'">
            <button type="button" class="case-cell" @click="openDetail(record as CaseReviewQueueItem)">
              <span class="case-code">{{ record.case_code }}</span>
              <strong>{{ record.name }}</strong>
              <small>{{ record.summary || '-' }}</small>
            </button>
          </template>
          <template v-else-if="column.key === 'project'">
            <div class="project-cell">
              <strong>{{ record.project_name }}</strong>
              <span>{{ record.module_name }}</span>
            </div>
          </template>
          <template v-else-if="column.key === 'type'">
            <a-tag>{{ caseTypeLabel(record.case_type) }}</a-tag>
          </template>
          <template v-else-if="column.key === 'level'">
            <span class="level-chip">{{ caseLevelLabel(record.case_level) }}</span>
          </template>
          <template v-else-if="column.key === 'status'">
            <a-tag :color="statusColor(record.review_status)">{{ statusLabel(record.review_status) }}</a-tag>
          </template>
          <template v-else-if="column.key === 'submitted'">
            {{ formatTime(record.submitted_at || record.updated_at) }}
          </template>
          <template v-else-if="column.key === 'reviewer'">
            <div v-if="record.reviewer_name || record.reviewed_at" class="reviewer-cell">
              <strong>{{ record.reviewer_name || `#${record.reviewed_by}` }}</strong>
              <span>{{ formatTime(record.reviewed_at) }}</span>
            </div>
            <span v-else class="muted">—</span>
          </template>
          <template v-else-if="column.key === 'actions'">
            <a-space size="small" wrap>
              <a-button type="link" size="small" @click="openDetail(record as CaseReviewQueueItem)">{{ t('case_reviews.actions.detail') }}</a-button>
              <a-button type="link" size="small" @click="openHistory(record.id)">{{ t('case_reviews.actions.history') }}</a-button>
            </a-space>
          </template>
        </template>
      </a-table>
      <a-empty v-if="!loading && !queue.items.length" :description="t('case_reviews.queue.empty')" />
    </section>

    <a-drawer
      v-model:open="detailOpen"
      :title="t('case_reviews.detail.title')"
      :width="560"
      destroy-on-close
    >
      <a-spin :spinning="detailLoading">
        <template v-if="selectedCase">
          <div class="detail-identity">
            <div>
              <span class="case-code">{{ selectedCase.case_code }}</span>
              <h2>{{ selectedCase.name }}</h2>
              <p>{{ selectedCase.module_name }} · {{ caseTypeLabel(selectedCase.case_type) }}</p>
            </div>
            <a-tag :color="statusColor(selectedCase.review_status)">{{ statusLabel(selectedCase.review_status) }}</a-tag>
          </div>

          <div class="detail-actions">
            <a-button @click="goCase(selectedCase)">{{ t('case_reviews.actions.open_case') }}</a-button>
            <a-button @click="openHistory(selectedCase.id)">{{ t('case_reviews.actions.history') }}</a-button>
            <a-button v-if="selectedCase.review_status === 'pending'" type="primary" @click="openBatch('approve', selectedCase.id)">
              {{ t('case_reviews.actions.approve') }}
            </a-button>
          </div>

          <a-divider />
          <section class="detail-section">
            <p class="section-kicker">{{ t('case_reviews.detail.metadata') }}</p>
            <div class="metadata-grid">
              <div><span>{{ t('case_reviews.columns.project') }}</span><strong>{{ selectedCase.project_name }}</strong></div>
              <div><span>{{ t('case_reviews.columns.level') }}</span><strong>{{ caseLevelLabel(selectedCase.case_level) }}</strong></div>
              <div><span>{{ t('case_reviews.columns.type') }}</span><strong>{{ caseTypeLabel(selectedCase.case_type) }}</strong></div>
              <div><span>{{ t('case_reviews.detail.steps') }}</span><strong>{{ selectedCase.step_count }}</strong></div>
            </div>
          </section>

          <section class="detail-section">
            <p class="section-kicker">{{ t('case_reviews.detail.summary') }}</p>
            <p class="detail-summary">{{ caseDetail?.summary || selectedCase.summary || '-' }}</p>
          </section>

          <section class="detail-section">
            <p class="section-kicker">{{ t('case_reviews.detail.review_comment') }}</p>
            <div class="comment-note">{{ caseDetail?.review_comment || selectedCase.review_comment || t('case_reviews.detail.no_comment') }}</div>
          </section>

          <section class="detail-section">
            <p class="section-kicker">{{ t('case_reviews.history.title') }}</p>
            <a-timeline v-if="history.length">
              <a-timeline-item v-for="item in history" :key="`${item.source}-${item.id}`">
                <div class="history-entry">
                  <strong>{{ historyActionLabel(item) }}</strong>
                  <span>{{ formatTime(item.created_at) }} · {{ item.reviewer_name || '—' }}</span>
                  <p v-if="item.comment">{{ item.comment }}</p>
                </div>
              </a-timeline-item>
            </a-timeline>
            <a-empty v-else :description="t('case_reviews.history.empty')" />
          </section>
        </template>
        <a-empty v-else :description="t('case_reviews.detail.loading')" />
      </a-spin>
    </a-drawer>

    <CaseHistoryDrawer
      :open="historyOpen"
      :case-id="historyCaseId"
      @close="historyOpen = false"
      @rolled="loadQueue"
    />

    <a-modal v-model:open="batchOpen" :title="batchTitle" :footer="null" destroy-on-close>
      <div class="batch-modal-copy">
        <span class="batch-modal-mark">{{ selectedRowKeys.length }}</span>
        <p>{{ t('case_reviews.selected', { count: selectedRowKeys.length }) }}</p>
      </div>
      <a-form layout="vertical">
        <a-form-item :label="t('case_reviews.batch.comment')">
          <a-textarea
            v-model:value="batchComment"
            :maxlength="2000"
            :placeholder="t('case_reviews.batch.comment_placeholder')"
            :rows="5"
            show-count
          />
        </a-form-item>
      </a-form>
      <div class="modal-footer">
        <a-button @click="batchOpen = false">{{ t('case_reviews.actions.cancel') }}</a-button>
        <a-button :danger="batchAction === 'reject'" type="primary" :loading="batchLoading" @click="submitBatch">
          {{ t('case_reviews.batch.confirm') }}
        </a-button>
      </div>
    </a-modal>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { message } from 'ant-design-vue'
import { useI18n } from 'vue-i18n'
import { useRoute, useRouter } from 'vue-router'
import CaseHistoryDrawer from './CaseHistoryDrawer.vue'
import {
  caseApi,
  caseReviewApi,
  projectApi,
  type CaseDetailItem,
  type CaseReviewHistoryItem,
  type CaseReviewQueueItem,
  type CaseReviewQueueResult,
  type ProjectItem,
  type ReviewStatus,
} from '@/api'

type ReviewStatusFilter = 'all' | ReviewStatus
type ReviewAction = 'approve' | 'reject'

const { t } = useI18n()
const route = useRoute()
const router = useRouter()
const projects = ref<ProjectItem[]>([])
const projectId = ref(positiveInt(route.query.project_id))
const reviewStatus = ref<ReviewStatusFilter>(reviewStatusFromQuery(route.query.review_status))
const searchInput = ref(String(firstQueryValue(route.query.keyword) || ''))
const keyword = ref(searchInput.value)
const page = ref(1)
const loading = ref(false)
const detailLoading = ref(false)
const batchLoading = ref(false)
const detailOpen = ref(false)
const batchOpen = ref(false)
const historyOpen = ref(false)
const historyCaseId = ref<number | null>(null)
const batchAction = ref<ReviewAction | null>(null)
const batchComment = ref('')
const selectedRowKeys = ref<number[]>([])
const selectedCase = ref<CaseReviewQueueItem | null>(null)
const caseDetail = ref<CaseDetailItem | null>(null)
const history = ref<CaseReviewHistoryItem[]>([])
let requestSerial = 0

const emptyQueue = (): CaseReviewQueueResult => ({
  items: [],
  total: 0,
  page: 1,
  page_size: 50,
  counts: { all: 0, pending: 0, approved: 0, rejected: 0 },
})
const queue = reactive<CaseReviewQueueResult>(emptyQueue())

const projectOptions = computed(() => projects.value.map(project => ({ label: project.name, value: project.id })))
const statusOptions = computed(() => (['all', 'pending', 'approved', 'rejected'] as ReviewStatusFilter[]).map(status => ({
  label: t(`case_reviews.statuses.${status}`),
  value: status,
})))
const summaryCards = computed(() => [
  { key: 'pending' as ReviewStatusFilter, value: queue.counts.pending, label: t('case_reviews.summary.pending'), caption: t('case_reviews.statuses.pending') },
  { key: 'approved' as ReviewStatusFilter, value: queue.counts.approved, label: t('case_reviews.summary.approved'), caption: t('case_reviews.statuses.approved') },
  { key: 'rejected' as ReviewStatusFilter, value: queue.counts.rejected, label: t('case_reviews.summary.rejected'), caption: t('case_reviews.statuses.rejected') },
  { key: 'all' as ReviewStatusFilter, value: queue.counts.all, label: t('case_reviews.summary.all'), caption: t('case_reviews.statuses.all') },
])
const columns = computed(() => [
  { title: t('case_reviews.columns.case'), key: 'case', width: 260 },
  { title: t('case_reviews.columns.project'), key: 'project', width: 170 },
  { title: t('case_reviews.columns.type'), key: 'type', width: 90 },
  { title: t('case_reviews.columns.level'), key: 'level', width: 100 },
  { title: t('case_reviews.columns.status'), key: 'status', width: 110 },
  { title: t('case_reviews.columns.submitted'), key: 'submitted', width: 160 },
  { title: t('case_reviews.columns.reviewer'), key: 'reviewer', width: 150 },
  { title: t('case_reviews.columns.actions'), key: 'actions', width: 180 },
])
const rowSelection = computed(() => ({
  selectedRowKeys: selectedRowKeys.value,
  onChange: (keys: (string | number)[]) => { selectedRowKeys.value = keys.map(Number) },
}))
const batchTitle = computed(() => batchAction.value === 'reject' ? t('case_reviews.batch.reject_title') : t('case_reviews.batch.approve_title'))

function firstQueryValue(value: unknown) {
  return Array.isArray(value) ? value[0] : value
}

function positiveInt(value: unknown) {
  const parsed = Number(firstQueryValue(value))
  return Number.isInteger(parsed) && parsed > 0 ? parsed : undefined
}

function reviewStatusFromQuery(value: unknown): ReviewStatusFilter {
  const parsed = firstQueryValue(value)
  return parsed === 'all' || parsed === 'approved' || parsed === 'rejected' || parsed === 'pending' ? parsed : 'pending'
}

function filterProject(input: string, option: any) {
  return String(option.label || '').toLowerCase().includes(input.toLowerCase())
}

function syncQuery() {
  void router.replace({
    query: {
      ...route.query,
      project_id: projectId.value ? String(projectId.value) : undefined,
      review_status: reviewStatus.value === 'pending' ? undefined : reviewStatus.value,
      keyword: keyword.value || undefined,
    },
  })
}

function selectStatus(status: ReviewStatusFilter) {
  reviewStatus.value = status
}

function applySearch() {
  keyword.value = searchInput.value.trim()
  page.value = 1
  syncQuery()
  void loadQueue()
}

async function loadProjects() {
  try {
    projects.value = await projectApi.list()
  } catch {
    projects.value = []
  }
}

async function loadQueue() {
  const serial = ++requestSerial
  loading.value = true
  try {
    const result = await caseReviewApi.list({
      project_id: projectId.value,
      review_status: reviewStatus.value,
      keyword: keyword.value || undefined,
      page: page.value,
      page_size: queue.page_size,
    })
    if (serial !== requestSerial) return
    Object.assign(queue, result)
    const visibleIds = new Set(result.items.map(item => item.id))
    selectedRowKeys.value = selectedRowKeys.value.filter(id => visibleIds.has(id))
  } catch (error) {
    if (serial === requestSerial) {
      Object.assign(queue, emptyQueue())
      message.error(errorMessage(error, t('case_reviews.msg.load_failed')))
    }
  } finally {
    if (serial === requestSerial) loading.value = false
  }
}

function handleTableChange(pagination: { current?: number; pageSize?: number }) {
  page.value = pagination.current || 1
  if (pagination.pageSize && pagination.pageSize !== queue.page_size) queue.page_size = pagination.pageSize
  void loadQueue()
}

async function openDetail(record: CaseReviewQueueItem) {
  selectedCase.value = record
  caseDetail.value = null
  history.value = []
  detailOpen.value = true
  detailLoading.value = true
  try {
    const [detail, events] = await Promise.all([caseApi.get(record.id), caseReviewApi.history(record.id)])
    caseDetail.value = detail
    history.value = events
  } catch (error) {
    message.error(errorMessage(error, t('case_reviews.msg.detail_failed')))
  } finally {
    detailLoading.value = false
  }
}

function openHistory(caseId: number) {
  historyCaseId.value = caseId
  historyOpen.value = true
}

function openBatch(action: ReviewAction, caseId?: number) {
  if (caseId) selectedRowKeys.value = [caseId]
  if (!selectedRowKeys.value.length) return
  batchAction.value = action
  batchComment.value = ''
  batchOpen.value = true
}

async function submitBatch() {
  if (!batchAction.value || !selectedRowKeys.value.length) return
  batchLoading.value = true
  try {
    const result = await caseReviewApi.batch({
      case_ids: selectedRowKeys.value,
      action: batchAction.value,
      comment: batchComment.value.trim() || undefined,
    })
    message.success(t('case_reviews.msg.batch_success', { count: result.processed }))
    if (result.skipped_ids.length) message.warning(t('case_reviews.batch.skipped', { count: result.skipped_ids.length }))
    selectedRowKeys.value = []
    batchOpen.value = false
    await loadQueue()
    if (selectedCase.value && result.processed_ids.includes(selectedCase.value.id)) {
      selectedCase.value = { ...selectedCase.value, review_status: batchAction.value === 'approve' ? 'approved' : 'rejected' }
    }
  } catch (error) {
    message.error(errorMessage(error, t('case_reviews.msg.batch_failed')))
  } finally {
    batchLoading.value = false
  }
}

function goCases() {
  void router.push({ path: '/cases', query: projectId.value ? { project_id: String(projectId.value) } : undefined })
}

function goCase(record: CaseReviewQueueItem) {
  void router.push({ name: 'case-detail', params: { caseId: record.id } })
}

function caseTypeLabel(type: string) {
  return t(`case.types.${type}`, type)
}

function caseLevelLabel(level: string) {
  return t(`case.levels.${level}`, level)
}

function statusLabel(status: string) {
  return t(`case_reviews.statuses.${status}`, status)
}

function statusColor(status: string) {
  return ({ pending: 'processing', approved: 'success', rejected: 'error' } as Record<string, string>)[status] || 'default'
}

function historyActionLabel(item: CaseReviewHistoryItem) {
  const actionKey = item.action === 'submit' ? 'submit' : item.action === 'approve' ? 'approve' : item.action === 'reject' ? 'reject' : 'snapshot'
  return t(`case_reviews.history.${actionKey}`)
}

function formatTime(value?: string | null) {
  return value ? value.slice(0, 19).replace('T', ' ') : '—'
}

function errorMessage(error: unknown, fallback: string) {
  if (error instanceof Error) return error.message
  return fallback
}

watch([projectId, reviewStatus], () => {
  page.value = 1
  syncQuery()
  void loadQueue()
})

onMounted(async () => {
  await loadProjects()
  await loadQueue()
})
</script>

<style scoped>
.review-page {
  --review-ink: #172033;
  --review-muted: #778198;
  --review-line: #e4e8f1;
  --review-indigo: #4f46e5;
  --review-coral: #e05a47;
  min-height: calc(100vh - 132px);
  color: var(--review-ink);
}

.review-hero {
  position: relative;
  display: flex;
  align-items: center;
  gap: 18px;
  min-height: 172px;
  padding: 28px 30px;
  overflow: hidden;
  border-radius: 18px;
  background: #18213a;
  color: #fff;
  box-shadow: 0 18px 45px rgba(22, 34, 70, .14);
}
.review-hero::after {
  position: absolute;
  right: -48px;
  bottom: -80px;
  width: 300px;
  height: 230px;
  content: '';
  border: 1px solid rgba(255, 255, 255, .18);
  border-radius: 50%;
  box-shadow: 0 0 0 22px rgba(255, 255, 255, .04), 0 0 0 44px rgba(255, 255, 255, .035);
}
.hero-mark {
  display: grid;
  width: 62px;
  height: 62px;
  flex: 0 0 62px;
  place-items: center;
  border: 1px solid rgba(255, 255, 255, .42);
  border-radius: 16px 16px 5px 16px;
  color: #fff;
  background: linear-gradient(145deg, #635bff, #3d36b9);
  font-size: 30px;
  font-weight: 800;
  transform: rotate(-8deg);
}
.hero-copy { position: relative; z-index: 1; }
.hero-kicker, .section-kicker { margin: 0 0 7px; color: #a6adff; font-size: 11px; font-weight: 800; letter-spacing: .16em; }
.hero-copy h1 { margin: 0; color: #fff; font-size: clamp(28px, 3vw, 40px); letter-spacing: -.045em; }
.hero-subtitle { max-width: 680px; margin: 9px 0 0; color: #c9cee0; line-height: 1.65; }
.hero-actions { position: relative; z-index: 1; display: flex; flex-wrap: wrap; gap: 8px; margin-left: auto; }
.hero-actions :deep(.ant-btn) { border-color: rgba(255, 255, 255, .3); color: #fff; background: rgba(255, 255, 255, .08); }

.pulse-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; margin: 20px 0 14px; }
.pulse-card { position: relative; min-height: 124px; padding: 18px; overflow: hidden; border: 1px solid var(--review-line); border-radius: 14px; color: var(--review-ink); background: #fff; text-align: left; cursor: pointer; transition: border-color .2s ease, transform .2s ease, box-shadow .2s ease; }
.pulse-card::after { position: absolute; right: -20px; bottom: -42px; width: 112px; height: 112px; content: ''; border: 1px solid currentColor; border-radius: 50%; opacity: .11; }
.pulse-card:hover, .pulse-card.is-selected { border-color: currentColor; box-shadow: 0 11px 24px rgba(31, 43, 80, .08); transform: translateY(-2px); }
.pulse-label, .pulse-tail { display: block; color: var(--review-muted); font-size: 12px; }
.pulse-card strong { display: block; margin: 14px 0 4px; font-size: 32px; letter-spacing: -.06em; }
.pulse-pending { color: #b76e13; }
.pulse-approved { color: #148a68; }
.pulse-rejected { color: #cf5946; }
.pulse-all { color: var(--review-indigo); }

.filter-strip { display: flex; flex-wrap: wrap; align-items: center; gap: 9px; margin-bottom: 14px; padding: 12px; border: 1px solid var(--review-line); border-radius: 12px; background: #fbfcfe; }
.project-filter { width: 200px; }
.keyword-filter { width: min(360px, 100%); }
.status-filter { width: 150px; }

.queue-panel { padding: 22px; border: 1px solid var(--review-line); border-radius: 16px; background: #fff; box-shadow: 0 12px 32px rgba(32, 46, 86, .045); }
.queue-heading { display: flex; align-items: flex-start; justify-content: space-between; gap: 18px; margin-bottom: 18px; }
.queue-heading h2 { margin: 0; font-size: 20px; letter-spacing: -.025em; }
.queue-heading p:last-child { margin: 7px 0 0; color: var(--review-muted); font-size: 12px; }
.queue-count { min-width: 84px; padding-left: 16px; border-left: 1px solid var(--review-line); text-align: right; }
.queue-count strong { display: block; font-size: 28px; letter-spacing: -.06em; }
.queue-count span { color: var(--review-muted); font-size: 11px; }
.batch-toolbar { display: flex; align-items: center; justify-content: space-between; gap: 12px; margin: 0 -4px 14px; padding: 10px 12px; border-left: 3px solid var(--review-indigo); border-radius: 6px; background: #f4f4ff; color: var(--review-indigo); font-size: 12px; font-weight: 700; }
.case-cell, .project-cell, .reviewer-cell { display: flex; flex-direction: column; align-items: flex-start; }
.case-cell { padding: 0; border: 0; color: var(--review-ink); background: transparent; text-align: left; cursor: pointer; }
.case-cell:hover strong { color: var(--review-indigo); }
.case-code { color: var(--review-indigo); font-family: ui-monospace, SFMono-Regular, Consolas, monospace; font-size: 11px; }
.case-cell strong { margin-top: 3px; font-size: 13px; }
.case-cell small, .project-cell span, .reviewer-cell span { margin-top: 3px; overflow: hidden; color: var(--review-muted); font-size: 11px; text-overflow: ellipsis; white-space: nowrap; max-width: 230px; }
.project-cell strong { font-size: 12px; }
.level-chip { color: #536079; font-size: 12px; }
.muted { color: var(--review-muted); }
.case-cell:focus-visible, .pulse-card:focus-visible { outline: 3px solid rgba(79, 70, 229, .34); outline-offset: 3px; }

.detail-identity { display: flex; align-items: flex-start; justify-content: space-between; gap: 12px; }
.detail-identity h2 { margin: 5px 0 0; font-size: 22px; letter-spacing: -.04em; }
.detail-identity p { margin: 5px 0 0; color: var(--review-muted); font-size: 12px; }
.detail-actions { display: flex; flex-wrap: wrap; gap: 8px; margin: 18px 0; }
.detail-section { margin: 22px 0; }
.detail-section .section-kicker { color: var(--review-indigo); }
.metadata-grid { display: grid; grid-template-columns: repeat(2, 1fr); gap: 10px; }
.metadata-grid div { padding: 11px 12px; border: 1px solid var(--review-line); border-radius: 9px; background: #fbfcfe; }
.metadata-grid span, .metadata-grid strong { display: block; }
.metadata-grid span { color: var(--review-muted); font-size: 11px; }
.metadata-grid strong { margin-top: 4px; font-size: 13px; }
.detail-summary, .comment-note { margin: 0; padding: 12px; border-radius: 9px; color: #5c687d; background: #f7f8fc; font-size: 13px; line-height: 1.7; }
.comment-note { border-left: 3px solid #d6d9e7; }
.history-entry { display: flex; flex-direction: column; gap: 3px; }
.history-entry strong { font-size: 13px; }
.history-entry span { color: var(--review-muted); font-size: 11px; }
.history-entry p { margin: 3px 0 0; color: #5c687d; font-size: 12px; line-height: 1.6; }
.batch-modal-copy { display: flex; align-items: center; gap: 12px; margin-bottom: 20px; color: var(--review-muted); }
.batch-modal-copy p { margin: 0; }
.batch-modal-mark { display: grid; width: 42px; height: 42px; place-items: center; border-radius: 11px; color: #fff; background: var(--review-indigo); font-size: 20px; font-weight: 800; }
.modal-footer { display: flex; justify-content: flex-end; gap: 8px; margin-top: 18px; }

@media (max-width: 900px) {
  .pulse-grid { grid-template-columns: repeat(2, 1fr); }
  .review-hero { align-items: flex-start; flex-wrap: wrap; }
  .hero-actions { width: 100%; margin-left: 80px; }
}
@media (max-width: 620px) {
  .review-hero { padding: 22px 18px; }
  .hero-mark { width: 46px; height: 46px; flex-basis: 46px; font-size: 23px; }
  .hero-actions { margin-left: 0; }
  .pulse-grid { grid-template-columns: 1fr 1fr; gap: 8px; }
  .pulse-card { min-height: 106px; padding: 13px; }
  .pulse-card strong { margin-top: 10px; font-size: 27px; }
  .filter-strip > * { width: 100% !important; }
  .queue-panel { padding: 14px 10px; }
  .queue-heading { align-items: flex-start; flex-direction: column; }
  .queue-count { width: 100%; padding: 10px 0 0; border-top: 1px solid var(--review-line); border-left: 0; text-align: left; }
  .batch-toolbar { align-items: flex-start; flex-direction: column; }
}
@media (prefers-reduced-motion: reduce) {
  .pulse-card { transition: none; }
}
</style>
