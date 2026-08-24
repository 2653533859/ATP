<template>
  <div class="configuration-page">
    <header class="configuration-hero">
      <div>
        <p class="eyebrow">{{ t('configuration_center.eyebrow') }}</p>
        <h1>{{ t('configuration_center.title') }}</h1>
        <p class="hero-copy">{{ t('configuration_center.subtitle') }}</p>
      </div>
      <div class="hero-actions">
        <label class="project-filter">
          <span>{{ t('configuration_center.project_filter') }}</span>
          <select :value="selectedProjectId ?? ''" @change="changeProject">
            <option value="">{{ t('configuration_center.all_projects') }}</option>
            <option v-for="project in projects" :key="project.id" :value="project.id">
              {{ project.name }}
            </option>
          </select>
        </label>
        <button class="button button-light" type="button" :disabled="loading" @click="loadOverview">
          {{ t('configuration_center.refresh') }}
        </button>
      </div>
    </header>

    <div v-if="loadError" class="state-banner state-error" role="alert">
      <span class="state-mark">!</span>
      <span>{{ loadError }}</span>
      <button type="button" class="text-button" @click="loadOverview">{{ t('configuration_center.retry') }}</button>
    </div>

    <section class="metric-strip" aria-label="configuration summary">
      <div class="metric-cell">
        <span class="metric-label">{{ t('configuration_center.metrics.domains') }}</span>
        <strong>{{ availableSections.length }}</strong>
        <small>{{ t('configuration_center.metrics.domains_hint') }}</small>
      </div>
      <div class="metric-cell">
        <span class="metric-label">{{ t('configuration_center.metrics.resources') }}</span>
        <strong>{{ resourceCount }}</strong>
        <small>{{ t('configuration_center.metrics.resources_hint') }}</small>
      </div>
      <div class="metric-cell">
        <span class="metric-label">{{ t('configuration_center.metrics.history') }}</span>
        <strong>{{ revisions.length }}</strong>
        <small>{{ t('configuration_center.metrics.history_hint') }}</small>
      </div>
      <div class="metric-cell metric-accent">
        <span class="metric-label">{{ t('configuration_center.metrics.focus') }}</span>
        <strong>{{ selectedResource?.name || t('configuration_center.metrics.none') }}</strong>
        <small>{{ selectedResource ? statusLabel(selectedResource.status) : t('configuration_center.metrics.select_hint') }}</small>
      </div>
    </section>

    <div v-if="loading && !overview" class="loading-state" aria-live="polite">
      <span class="loading-orbit" aria-hidden="true"></span>
      {{ t('configuration_center.loading') }}
    </div>

    <section v-else class="configuration-layout">
      <aside class="domain-rail" aria-label="configuration domains">
        <div class="rail-heading">
          <span class="section-kicker">{{ t('configuration_center.domain_kicker') }}</span>
          <span class="rail-count">{{ availableSections.length }}</span>
        </div>
        <button
          v-for="(section, index) in sections"
          :key="section.key"
          type="button"
          class="domain-item"
          :class="{ active: section.key === selectedDomainKey, unavailable: !section.available }"
          :disabled="!section.available"
          @click="selectedDomainKey = section.key"
        >
          <span class="domain-index">{{ String(index + 1).padStart(2, '0') }}</span>
          <span class="domain-copy">
            <strong>{{ section.title }}</strong>
            <small>{{ section.description }}</small>
          </span>
          <span class="domain-count">{{ section.available ? section.count : '—' }}</span>
        </button>
        <div class="rail-note">
          <span class="note-dot"></span>
          {{ t('configuration_center.sensitive_note') }}
        </div>
      </aside>

      <main class="resource-pane">
        <div class="pane-heading">
          <div>
            <p class="section-kicker">{{ t('configuration_center.resource_kicker') }}</p>
            <h2>{{ selectedSection?.title || t('configuration_center.resource_title') }}</h2>
            <p>{{ selectedSection?.description || t('configuration_center.resource_hint') }}</p>
          </div>
          <span v-if="selectedSection" class="scope-badge">
            {{ selectedSection.project_scoped ? t('configuration_center.project_scoped') : t('configuration_center.global_scope') }}
          </span>
        </div>

        <div v-if="selectedSection && !selectedSection.available" class="empty-panel">
          <span class="empty-icon">⌁</span>
          <strong>{{ t('configuration_center.unavailable_title') }}</strong>
          <p>{{ t('configuration_center.unavailable_description') }}</p>
        </div>
        <div v-else-if="!resources.length" class="empty-panel">
          <span class="empty-icon">∅</span>
          <strong>{{ t('configuration_center.empty_title') }}</strong>
          <p>{{ t('configuration_center.empty_description') }}</p>
          <button v-if="selectedSection?.route" type="button" class="button button-secondary" @click="openSource(selectedSection.route)">
            {{ t('configuration_center.open_source') }}
          </button>
        </div>
        <div v-else class="resource-list">
          <button
            v-for="resource in resources"
            :key="resourceKey(resource)"
            type="button"
            class="resource-card"
            :class="{ selected: resourceKey(resource) === selectedResourceKey }"
            @click="selectResource(resource)"
          >
            <span class="resource-state" :class="statusClass(resource.status)"></span>
            <span class="resource-main">
              <span class="resource-title-row">
                <strong>{{ resource.name }}</strong>
                <span class="status-chip" :class="statusClass(resource.status)">{{ statusLabel(resource.status) }}</span>
              </span>
              <span class="resource-meta">
                <span>{{ domainLabel(resource.domain) }}</span>
                <span v-if="resource.project_id">{{ projectName(resource.project_id) }}</span>
                <span v-if="resource.updated_at">{{ formatDate(resource.updated_at) }}</span>
              </span>
              <span class="summary-row">
                <span v-for="item in summaryItems(resource)" :key="item.key" class="summary-pill">
                  <small>{{ item.label }}</small>{{ item.value }}
                </span>
              </span>
            </span>
            <span class="resource-arrow" aria-hidden="true">→</span>
          </button>
        </div>
      </main>

      <aside class="detail-pane" aria-live="polite">
        <div v-if="!selectedResource" class="detail-empty">
          <span class="detail-number">03</span>
          <h2>{{ t('configuration_center.detail_empty_title') }}</h2>
          <p>{{ t('configuration_center.detail_empty_description') }}</p>
        </div>
        <template v-else>
          <div class="detail-heading">
            <div>
              <p class="section-kicker">{{ t('configuration_center.detail_kicker') }}</p>
              <h2>{{ selectedResource.name }}</h2>
            </div>
            <button type="button" class="icon-button" :aria-label="t('configuration_center.open_source')" @click="openSource(selectedResource.route, selectedResource)">↗</button>
          </div>
          <div class="detail-summary">
            <div><span>{{ t('configuration_center.detail_status') }}</span><strong :class="statusClass(selectedResource.status)">{{ statusLabel(selectedResource.status) }}</strong></div>
            <div><span>{{ t('configuration_center.detail_updated') }}</span><strong>{{ selectedResource.updated_at ? formatDate(selectedResource.updated_at) : t('configuration_center.not_available') }}</strong></div>
            <div><span>{{ t('configuration_center.detail_history') }}</span><strong>{{ revisions.length }}</strong></div>
          </div>

          <div v-if="selectedResource.can_manage && selectedResource.resource_id && isRevisionDomain(selectedResource.domain)" class="snapshot-box">
            <label for="revision-reason">{{ t('configuration_center.snapshot_label') }}</label>
            <div class="snapshot-action">
              <input id="revision-reason" v-model="revisionReason" type="text" :placeholder="t('configuration_center.snapshot_placeholder')" maxlength="512" />
              <button type="button" class="button button-teal" :disabled="snapshotLoading" @click="createSnapshot">
                {{ snapshotLoading ? t('configuration_center.saving') : t('configuration_center.snapshot') }}
              </button>
            </div>
          </div>

          <div class="timeline-heading">
            <span class="section-kicker">{{ t('configuration_center.timeline_kicker') }}</span>
            <span v-if="revisionsLoading" class="mini-loading">{{ t('configuration_center.loading') }}</span>
          </div>
          <div v-if="!revisionsLoading && !revisions.length" class="history-empty">
            <strong>{{ t('configuration_center.no_history_title') }}</strong>
            <p>{{ t('configuration_center.no_history_description') }}</p>
          </div>
          <ol v-else class="revision-timeline">
            <li v-for="revision in revisions" :key="revision.id" class="revision-item" :class="{ selected: revision.id === selectedRevisionId }">
              <button type="button" class="revision-button" @click="selectRevision(revision)">
                <span class="timeline-dot"></span>
                <span class="revision-copy">
                  <strong>v{{ revision.id }} · {{ revision.reason || t('configuration_center.default_reason') }}</strong>
                  <small>{{ formatDate(revision.created_at) }} · {{ t('configuration_center.revision_by', { id: revision.created_by || '—' }) }}</small>
                </span>
                <span class="revision-arrow">›</span>
              </button>
            </li>
          </ol>

          <div v-if="diffLoading" class="diff-loading">{{ t('configuration_center.diff_loading') }}</div>
          <section v-else-if="diff" class="diff-card">
            <div class="diff-header">
              <div>
                <p class="section-kicker">{{ t('configuration_center.diff_kicker') }}</p>
                <h3>{{ t('configuration_center.diff_title') }}</h3>
              </div>
              <span class="diff-state" :class="diff.changed ? 'changed' : 'same'">
                {{ diff.changed ? t('configuration_center.changed') : t('configuration_center.unchanged') }}
              </span>
            </div>
            <p v-if="diff.message" class="diff-message">{{ diff.message }}</p>
            <div class="diff-stats">
              <span>{{ t('configuration_center.changed_fields', { count: diff.changed_field_count }) }}</span>
              <span v-if="diff.sensitive_changed_field_count">{{ t('configuration_center.sensitive_fields', { count: diff.sensitive_changed_field_count }) }}</span>
              <span>{{ diff.current_status === 'available' ? t('configuration_center.current_available') : t('configuration_center.current_missing') }}</span>
            </div>
            <div v-if="diff.impacts.length" class="impact-list">
              <div v-for="impact in diff.impacts" :key="impact.code" class="impact-item" :class="`impact-${impact.severity}`">
                <strong>{{ impact.title }}</strong>
                <p>{{ impact.description }}</p>
              </div>
            </div>
            <div v-if="diff.changes.length" class="change-list">
              <div v-for="change in diff.changes" :key="`${change.path}-${change.change_type}`" class="change-item">
                <code>{{ change.path }}</code>
                <span v-if="change.sensitive" class="redacted-value">{{ t('configuration_center.redacted') }}</span>
                <span v-else>{{ displayValue(change.before) }} → {{ displayValue(change.after) }}</span>
              </div>
            </div>
            <p v-else class="no-change-copy">{{ t('configuration_center.no_change_detail') }}</p>
            <button v-if="selectedRevision && selectedResource.can_manage" type="button" class="button button-danger" @click="openRollback">
              {{ t('configuration_center.rollback') }}
            </button>
          </section>
        </template>
      </aside>
    </section>

    <div v-if="rollbackOpen" class="modal-backdrop" role="presentation" @click.self="rollbackOpen = false">
      <section class="rollback-modal" role="dialog" aria-modal="true" :aria-labelledby="'rollback-title'">
        <div class="modal-warning">!</div>
        <p class="section-kicker">{{ t('configuration_center.rollback_kicker') }}</p>
        <h2 id="rollback-title">{{ t('configuration_center.rollback_title') }}</h2>
        <p>{{ t('configuration_center.rollback_description', { name: selectedResource?.name || '' }) }}</p>
        <div class="rollback-source">
          <span>{{ t('configuration_center.rollback_source') }}</span>
          <strong>v{{ selectedRevision?.id }} · {{ selectedRevision ? formatDate(selectedRevision.created_at) : '' }}</strong>
        </div>
        <label class="confirmation-field">
          <span>{{ t('configuration_center.rollback_confirmation') }}</span>
          <input v-model="rollbackToken" type="text" autocomplete="off" :placeholder="t('configuration_center.rollback_placeholder')" @keyup.esc="rollbackOpen = false" />
        </label>
        <div class="modal-actions">
          <button type="button" class="button button-secondary" @click="rollbackOpen = false">{{ t('configuration_center.cancel') }}</button>
          <button type="button" class="button button-danger" :disabled="rollbackToken !== 'ROLLBACK' || rollbackLoading" @click="confirmRollback">
            {{ rollbackLoading ? t('configuration_center.rolling_back') : t('configuration_center.confirm_rollback') }}
          </button>
        </div>
      </section>
    </div>
  </div>
</template>

<script setup lang="ts">
import { message } from 'ant-design-vue'
import { computed, onMounted, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRouter } from 'vue-router'

import {
  configurationCenterApi,
  projectApi,
  type ConfigurationEntryItem,
  type ConfigurationRevisionDiff,
  type ConfigurationRevisionItem,
  type ConfigurationSnapshotDomain,
  type ConfigurationCenterOverview,
  type ConfigurationSectionItem,
  type ProjectItem,
} from '@/api'

const { t } = useI18n()
const router = useRouter()
const projects = ref<ProjectItem[]>([])
const selectedProjectId = ref<number | null>(null)
const overview = ref<ConfigurationCenterOverview | null>(null)
const loading = ref(false)
const loadError = ref('')
const selectedDomainKey = ref('')
const selectedResourceKey = ref('')
const revisions = ref<ConfigurationRevisionItem[]>([])
const selectedRevisionId = ref<number | null>(null)
const diff = ref<ConfigurationRevisionDiff | null>(null)
const revisionsLoading = ref(false)
const diffLoading = ref(false)
const snapshotLoading = ref(false)
const revisionReason = ref('')
const rollbackOpen = ref(false)
const rollbackToken = ref('')
const rollbackLoading = ref(false)
let revisionsRequestSequence = 0
let diffRequestSequence = 0

const supportedRevisionDomains = new Set<ConfigurationSnapshotDomain>([
  'environment', 'global_variable', 'ai_llm', 'storage_policy', 'notification', 'performance_node',
])

const sections = computed(() => overview.value?.sections || [])
const availableSections = computed(() => sections.value.filter((section) => section.available))
const selectedSection = computed<ConfigurationSectionItem | null>(() =>
  sections.value.find((section) => section.key === selectedDomainKey.value) || availableSections.value[0] || null,
)
const resources = computed(() => selectedSection.value?.entries || [])
const selectedResource = computed<ConfigurationEntryItem | null>(() =>
  resources.value.find((resource) => resourceKey(resource) === selectedResourceKey.value) || resources.value[0] || null,
)
const resourceCount = computed(() => availableSections.value.reduce((sum, section) => sum + section.count, 0))
const selectedRevision = computed(() => revisions.value.find((revision) => revision.id === selectedRevisionId.value) || null)

function errorMessage(error: unknown, fallback: string) {
  if (typeof error === 'string' && error.trim()) return error
  if (error && typeof error === 'object' && 'message' in error) {
    const detail = (error as { message?: unknown }).message
    if (typeof detail === 'string' && detail.trim()) return detail
  }
  return fallback
}

function resourceKey(resource: ConfigurationEntryItem) {
  return `${resource.domain}:${resource.resource_id ?? 'global'}:${resource.project_id ?? 'all'}`
}

function projectName(projectId: number) {
  return projects.value.find((project) => project.id === projectId)?.name || `#${projectId}`
}

function domainLabel(domain: string) {
  const key = `configuration_center.domains.${domain}`
  const label = t(key)
  return label === key ? domain : label
}

function statusLabel(status: string) {
  const key = `configuration_center.status.${status}`
  const label = t(key)
  return label === key ? status : label
}

function statusClass(status: string) {
  if (['enabled', 'active', 'online', 'ok', 'healthy'].includes(status)) return 'status-good'
  if (['warning', 'degraded', 'pending'].includes(status)) return 'status-warning'
  if (['disabled', 'offline', 'missing', 'error'].includes(status)) return 'status-bad'
  return 'status-neutral'
}

function formatDate(value: string) {
  return new Intl.DateTimeFormat(undefined, { month: 'short', day: '2-digit', hour: '2-digit', minute: '2-digit' }).format(new Date(value))
}

function displayValue(value: unknown) {
  if (value === null || value === undefined || value === '') return '—'
  if (typeof value === 'object') return JSON.stringify(value)
  return String(value)
}

function summaryItems(resource: ConfigurationEntryItem) {
  const labels: Record<string, string> = {
    provider: t('configuration_center.summary.provider'),
    model_name: t('configuration_center.summary.model'),
    prefix: t('configuration_center.summary.prefix'),
    retention_days: t('configuration_center.summary.retention'),
    queue_name: t('configuration_center.summary.queue'),
    node_id: t('configuration_center.summary.node'),
    enabled: t('configuration_center.summary.enabled'),
    has_api_key: t('configuration_center.summary.has_api_key'),
    variable_count: t('configuration_center.summary.variable_count'),
    channel: t('configuration_center.summary.channel'),
  }
  return Object.entries(resource.summary).slice(0, 3).map(([key, value]) => ({
    key,
    label: labels[key] || key,
    value: Array.isArray(value) ? value.join(', ') : displayValue(value),
  }))
}

function isRevisionDomain(domain: string): domain is ConfigurationSnapshotDomain {
  return supportedRevisionDomains.has(domain as ConfigurationSnapshotDomain)
}

function selectFirstResource() {
  const nextSection = selectedSection.value
  selectedResourceKey.value = nextSection?.entries[0] ? resourceKey(nextSection.entries[0]) : ''
  selectedRevisionId.value = null
  diff.value = null
  if (selectedResource.value) void loadRevisions(selectedResource.value)
  else {
    revisionsRequestSequence += 1
    revisionsLoading.value = false
    revisions.value = []
  }
}

function selectResource(resource: ConfigurationEntryItem) {
  selectedResourceKey.value = resourceKey(resource)
  selectedRevisionId.value = null
  diff.value = null
  void loadRevisions(resource)
}

async function loadProjects() {
  try {
    projects.value = await projectApi.list()
  } catch (error) {
    message.error(errorMessage(error, t('configuration_center.projects_load_failed')))
  }
}

async function loadOverview() {
  loading.value = true
  loadError.value = ''
  try {
    overview.value = await configurationCenterApi.overview(selectedProjectId.value)
    const selectedStillExists = sections.value.some((section) => section.key === selectedDomainKey.value && section.available)
    if (!selectedStillExists) selectedDomainKey.value = availableSections.value[0]?.key || ''
    selectFirstResource()
  } catch (error) {
    loadError.value = errorMessage(error, t('configuration_center.load_failed'))
  } finally {
    loading.value = false
  }
}

async function loadRevisions(resource: ConfigurationEntryItem) {
  const requestSequence = ++revisionsRequestSequence
  const requestedResourceKey = resourceKey(resource)
  revisions.value = []
  if (!resource.resource_id || !isRevisionDomain(resource.domain)) {
    revisionsLoading.value = false
    return
  }
  revisionsLoading.value = true
  try {
    const nextRevisions = await configurationCenterApi.revisions({
      domain: resource.domain,
      resource_id: resource.resource_id,
      project_id: resource.project_id,
      limit: 50,
    })
    if (requestSequence !== revisionsRequestSequence || requestedResourceKey !== selectedResourceKey.value) return
    revisions.value = nextRevisions
  } catch (error) {
    if (requestSequence !== revisionsRequestSequence || requestedResourceKey !== selectedResourceKey.value) return
    message.error(errorMessage(error, t('configuration_center.history_failed')))
  } finally {
    if (requestSequence === revisionsRequestSequence) revisionsLoading.value = false
  }
}

async function selectRevision(revision: ConfigurationRevisionItem) {
  const requestSequence = ++diffRequestSequence
  selectedRevisionId.value = revision.id
  diffLoading.value = true
  diff.value = null
  try {
    const nextDiff = await configurationCenterApi.diff(revision.id)
    if (requestSequence !== diffRequestSequence || revision.id !== selectedRevisionId.value) return
    diff.value = nextDiff
  } catch (error) {
    if (requestSequence !== diffRequestSequence || revision.id !== selectedRevisionId.value) return
    message.error(errorMessage(error, t('configuration_center.diff_failed')))
  } finally {
    if (requestSequence === diffRequestSequence) diffLoading.value = false
  }
}

async function createSnapshot() {
  const resource = selectedResource.value
  if (!resource?.resource_id || !isRevisionDomain(resource.domain)) return
  snapshotLoading.value = true
  try {
    const revision = await configurationCenterApi.createRevision({
      domain: resource.domain,
      resource_id: resource.resource_id,
      reason: revisionReason.value.trim() || undefined,
    })
    message.success(t('configuration_center.snapshot_success'))
    revisionReason.value = ''
    await loadRevisions(resource)
    await selectRevision(revision)
  } catch (error) {
    message.error(errorMessage(error, t('configuration_center.snapshot_failed')))
  } finally {
    snapshotLoading.value = false
  }
}

function openSource(route: string, resource?: ConfigurationEntryItem) {
  const projectId = resource?.project_id
  void router.push(projectId ? { path: route, query: { project_id: String(projectId) } } : route)
}

function openRollback() {
  if (!selectedRevision.value) return
  rollbackToken.value = ''
  rollbackOpen.value = true
}

async function confirmRollback() {
  if (rollbackToken.value !== 'ROLLBACK' || !selectedRevision.value) return
  rollbackLoading.value = true
  try {
    const result = await configurationCenterApi.rollback(selectedRevision.value.id)
    message.success(result.message || t('configuration_center.rollback_success'))
    rollbackOpen.value = false
    rollbackToken.value = ''
    await loadOverview()
    const resource = sections.value.flatMap((section) => section.entries).find((item) => item.domain === result.domain && item.resource_id === result.resource_id)
    if (resource) {
      selectResource(resource)
      const restored = revisions.value.find((revision) => revision.id === result.revision.id)
      if (restored) await selectRevision(restored)
    }
  } catch (error) {
    message.error(errorMessage(error, t('configuration_center.rollback_failed')))
  } finally {
    rollbackLoading.value = false
  }
}

function changeProject(event: Event) {
  const value = (event.target as HTMLSelectElement).value
  selectedProjectId.value = value ? Number(value) : null
  void loadOverview()
}

watch(selectedDomainKey, () => selectFirstResource())

onMounted(async () => {
  await loadProjects()
  await loadOverview()
})
</script>

<style scoped>
:global(body) { background: #eef4f2; }
.configuration-page { --ink: #142e35; --muted: #728287; --line: #d8e5e2; --paper: #f8fbfa; --teal: #118889; --teal-dark: #0d5054; --amber: #c9812d; --red: #bd554d; color: var(--ink); min-height: calc(100vh - 80px); padding: 28px 30px 50px; background: radial-gradient(circle at 86% 0%, rgba(17, 136, 137, .12), transparent 32%), #eef4f2; }
.configuration-hero { display: flex; justify-content: space-between; align-items: flex-end; gap: 24px; max-width: 1600px; margin: 0 auto 18px; }
.eyebrow, .section-kicker { margin: 0; color: var(--teal); font-size: 11px; font-weight: 800; letter-spacing: .16em; text-transform: uppercase; }
h1, h2, h3, p { margin-top: 0; }
h1 { margin-bottom: 8px; font-size: clamp(30px, 4vw, 48px); letter-spacing: -.045em; line-height: 1; }
.hero-copy { max-width: 650px; margin-bottom: 0; color: var(--muted); font-size: 14px; line-height: 1.65; }
.hero-actions { display: flex; align-items: flex-end; gap: 10px; }
.project-filter { display: grid; gap: 6px; color: var(--muted); font-size: 11px; font-weight: 700; }
select, input { min-height: 38px; border: 1px solid var(--line); border-radius: 8px; background: #fff; color: var(--ink); padding: 0 12px; font: inherit; outline: none; }
select:focus, input:focus, button:focus-visible { border-color: var(--teal); box-shadow: 0 0 0 3px rgba(17, 136, 137, .16); outline: none; }
.button { min-height: 38px; border: 1px solid transparent; border-radius: 8px; padding: 0 15px; cursor: pointer; font: inherit; font-size: 13px; font-weight: 800; transition: transform .18s ease, background .18s ease, border-color .18s ease; }
.button:hover:not(:disabled) { transform: translateY(-1px); }
.button:disabled { cursor: not-allowed; opacity: .52; }
.button-light { border-color: rgba(255,255,255,.42); background: var(--teal-dark); color: #fff; }
.button-secondary { border-color: var(--line); background: #fff; color: var(--ink); }
.button-teal { background: var(--teal); color: #fff; }
.button-danger { background: var(--red); color: #fff; }
.text-button, .icon-button { border: 0; background: transparent; color: var(--teal-dark); cursor: pointer; font: inherit; font-weight: 800; }
.state-banner { display: flex; align-items: center; gap: 10px; max-width: 1600px; margin: 0 auto 16px; border: 1px solid #efc7c2; border-radius: 10px; background: #fff8f7; padding: 11px 14px; color: var(--red); font-size: 13px; }
.state-mark, .modal-warning { display: grid; place-items: center; width: 22px; height: 22px; border-radius: 50%; background: var(--red); color: #fff; font-weight: 900; }
.state-banner .text-button { margin-left: auto; color: var(--red); }
.metric-strip { display: grid; grid-template-columns: repeat(4, 1fr); max-width: 1600px; margin: 0 auto 18px; overflow: hidden; border: 1px solid var(--line); border-radius: 12px; background: rgba(255,255,255,.74); }
.metric-cell { min-height: 98px; border-right: 1px solid var(--line); padding: 16px 18px; }
.metric-cell:last-child { border-right: 0; }
.metric-label { display: block; margin-bottom: 7px; color: var(--muted); font-size: 11px; font-weight: 800; letter-spacing: .08em; text-transform: uppercase; }
.metric-cell strong { display: block; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; font-size: 24px; letter-spacing: -.03em; }
.metric-cell small { color: var(--muted); font-size: 11px; }
.metric-accent strong { color: var(--teal); font-size: 18px; }
.loading-state { display: grid; place-items: center; gap: 13px; min-height: 360px; color: var(--muted); }
.loading-orbit { width: 27px; height: 27px; border: 3px solid #cde0dd; border-top-color: var(--teal); border-radius: 50%; animation: spin 1s linear infinite; }
@keyframes spin { to { transform: rotate(360deg); } }
.configuration-layout { display: grid; grid-template-columns: minmax(210px, .7fr) minmax(360px, 1.25fr) minmax(360px, 1fr); max-width: 1600px; min-height: 600px; margin: 0 auto; overflow: hidden; border: 1px solid var(--line); border-radius: 14px; background: rgba(248,251,250,.9); box-shadow: 0 18px 48px rgba(20, 46, 53, .07); }
.domain-rail, .resource-pane, .detail-pane { min-width: 0; padding: 22px; }
.domain-rail { border-right: 1px solid var(--line); background: #f1f7f5; }
.rail-heading, .timeline-heading, .resource-title-row, .detail-heading, .diff-header, .modal-actions { display: flex; align-items: center; justify-content: space-between; gap: 12px; }
.rail-count, .scope-badge { border-radius: 999px; background: #dcece8; padding: 4px 8px; color: var(--teal-dark); font-size: 11px; font-weight: 800; }
.domain-item { display: grid; grid-template-columns: 25px 1fr auto; align-items: start; gap: 10px; width: 100%; margin-top: 9px; border: 1px solid transparent; border-radius: 10px; background: transparent; padding: 12px 8px; color: inherit; cursor: pointer; text-align: left; }
.domain-item:hover:not(:disabled) { background: rgba(255,255,255,.72); }
.domain-item.active { border-color: #acd2cc; background: #fff; box-shadow: 0 6px 16px rgba(20, 46, 53, .06); }
.domain-item:disabled { cursor: not-allowed; opacity: .45; }
.domain-index { color: var(--teal); font-family: ui-monospace, SFMono-Regular, Consolas, monospace; font-size: 11px; }
.domain-copy { display: grid; gap: 4px; }
.domain-copy strong { font-size: 13px; }
.domain-copy small { color: var(--muted); font-size: 11px; line-height: 1.35; }
.domain-count { color: var(--muted); font-family: ui-monospace, SFMono-Regular, Consolas, monospace; font-size: 12px; }
.rail-note { display: flex; gap: 8px; margin-top: 28px; border-top: 1px solid var(--line); padding-top: 14px; color: var(--muted); font-size: 11px; line-height: 1.5; }
.note-dot { flex: 0 0 auto; width: 7px; height: 7px; margin-top: 4px; border-radius: 50%; background: var(--amber); }
.resource-pane { border-right: 1px solid var(--line); background: rgba(255,255,255,.42); }
.pane-heading { display: flex; justify-content: space-between; align-items: flex-start; gap: 12px; margin-bottom: 17px; }
.pane-heading h2, .detail-heading h2, .detail-empty h2 { margin: 4px 0 5px; font-size: 21px; letter-spacing: -.03em; }
.pane-heading p:not(.section-kicker) { margin-bottom: 0; color: var(--muted); font-size: 12px; line-height: 1.45; }
.resource-list { display: grid; gap: 9px; }
.resource-card { display: grid; grid-template-columns: 8px 1fr auto; gap: 12px; align-items: center; width: 100%; border: 1px solid var(--line); border-radius: 10px; background: rgba(255,255,255,.8); padding: 13px 12px; color: inherit; cursor: pointer; text-align: left; transition: border-color .18s ease, box-shadow .18s ease, transform .18s ease; }
.resource-card:hover { border-color: #94c9c1; transform: translateX(2px); }
.resource-card.selected { border-color: var(--teal); box-shadow: 0 9px 20px rgba(17, 136, 137, .11); }
.resource-state { align-self: stretch; width: 5px; border-radius: 999px; background: #a5b7b8; }
.resource-state.status-good { background: var(--teal); }
.resource-state.status-warning { background: var(--amber); }
.resource-state.status-bad { background: var(--red); }
.resource-main { min-width: 0; }
.resource-title-row strong { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; font-size: 13px; }
.status-chip, .diff-state { flex: 0 0 auto; border-radius: 999px; padding: 3px 7px; font-size: 10px; font-weight: 800; }
.status-good { color: var(--teal); }
.status-chip.status-good, .diff-state.same { background: #def1ea; }
.status-warning { color: var(--amber); }
.status-chip.status-warning { background: #fff0d7; }
.status-bad { color: var(--red); }
.status-chip.status-bad, .diff-state.changed { background: #fce4e0; }
.status-neutral { color: var(--muted); }
.status-chip.status-neutral { background: #e8efee; }
.resource-meta, .summary-row { display: flex; flex-wrap: wrap; gap: 8px; color: var(--muted); font-size: 10px; }
.resource-meta { margin-top: 6px; }
.resource-meta span + span::before { content: '·'; margin-right: 8px; }
.summary-row { margin-top: 9px; }
.summary-pill { border: 1px solid #e2ecea; border-radius: 5px; background: #f8fbfa; padding: 3px 5px; }
.summary-pill small { margin-right: 4px; color: var(--muted); }
.resource-arrow { color: #8ca7a6; font-size: 20px; }
.empty-panel, .detail-empty, .history-empty { display: grid; place-items: center; min-height: 280px; padding: 28px; text-align: center; }
.empty-icon { color: #92b7b1; font-size: 48px; font-weight: 200; }
.empty-panel strong, .detail-empty h2, .history-empty strong { margin-top: 9px; }
.empty-panel p, .detail-empty p, .history-empty p { max-width: 280px; margin: 6px 0 18px; color: var(--muted); font-size: 12px; line-height: 1.55; }
.detail-pane { background: #fbfcfa; }
.detail-heading { align-items: flex-start; }
.icon-button { width: 33px; height: 33px; border: 1px solid var(--line); border-radius: 8px; background: #fff; color: var(--teal); font-size: 17px; }
.detail-summary { display: grid; grid-template-columns: repeat(3, 1fr); gap: 8px; margin: 16px 0; border-top: 1px solid var(--line); border-bottom: 1px solid var(--line); padding: 12px 0; }
.detail-summary div { display: grid; gap: 4px; min-width: 0; }
.detail-summary span { color: var(--muted); font-size: 10px; }
.detail-summary strong { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; font-size: 12px; }
.snapshot-box { border: 1px solid #c5dfd9; border-radius: 9px; background: #edf8f5; padding: 11px; }
.snapshot-box label, .confirmation-field span { display: block; margin-bottom: 7px; color: var(--teal-dark); font-size: 11px; font-weight: 800; }
.snapshot-action { display: flex; gap: 7px; }
.snapshot-action input { flex: 1; min-width: 0; }
.snapshot-action .button { padding: 0 10px; }
.timeline-heading { margin: 22px 0 9px; }
.mini-loading, .diff-loading { color: var(--muted); font-size: 11px; }
.revision-timeline { position: relative; margin: 0; padding: 0; list-style: none; }
.revision-timeline::before { position: absolute; top: 10px; bottom: 10px; left: 5px; width: 1px; background: #c9dfda; content: ''; }
.revision-item { position: relative; }
.revision-button { display: grid; grid-template-columns: 11px 1fr auto; align-items: center; gap: 10px; width: 100%; border: 0; border-radius: 7px; background: transparent; padding: 9px 5px 9px 0; color: inherit; cursor: pointer; text-align: left; }
.revision-button:hover, .revision-item.selected .revision-button { background: #eef7f4; }
.timeline-dot { z-index: 1; width: 11px; height: 11px; border: 3px solid #fbfcfa; border-radius: 50%; background: var(--teal); box-shadow: 0 0 0 1px #9ac7bf; }
.revision-copy { display: grid; gap: 4px; min-width: 0; }
.revision-copy strong { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; font-size: 12px; }
.revision-copy small { color: var(--muted); font-size: 10px; }
.revision-arrow { color: #8ca7a6; font-size: 18px; }
.diff-card { margin-top: 14px; border: 1px solid var(--line); border-radius: 10px; background: #fff; padding: 13px; }
.diff-header h3 { margin: 4px 0 0; font-size: 15px; }
.diff-state { color: var(--teal-dark); }
.diff-message, .no-change-copy { margin: 11px 0 0; color: var(--muted); font-size: 11px; line-height: 1.5; }
.diff-stats { display: flex; flex-wrap: wrap; gap: 6px; margin: 12px 0; }
.diff-stats span { border-radius: 5px; background: #f0f5f3; padding: 4px 6px; color: var(--muted); font-size: 10px; }
.impact-list, .change-list { display: grid; gap: 6px; margin-bottom: 12px; }
.impact-item { border-left: 3px solid var(--amber); background: #fff8ec; padding: 7px 9px; }
.impact-item.impact-high { border-left-color: var(--red); background: #fff3f1; }
.impact-item.impact-low { border-left-color: var(--teal); background: #eff9f6; }
.impact-item strong { font-size: 11px; }
.impact-item p { margin: 3px 0 0; color: var(--muted); font-size: 10px; line-height: 1.45; }
.change-item { display: grid; gap: 4px; border-bottom: 1px solid #edf2f0; padding: 6px 0; color: var(--muted); font-size: 10px; }
.change-item code { color: var(--teal-dark); font-size: 10px; }
.redacted-value { color: var(--amber); font-weight: 800; }
.diff-card .button-danger { width: 100%; margin-top: 4px; }
.modal-backdrop { position: fixed; z-index: 30; inset: 0; display: grid; place-items: center; background: rgba(20, 46, 53, .46); padding: 20px; }
.rollback-modal { width: min(450px, 100%); border: 1px solid #e7c3be; border-radius: 14px; background: #fff; padding: 25px; box-shadow: 0 24px 70px rgba(20, 46, 53, .24); }
.rollback-modal h2 { margin: 7px 0; font-size: 25px; letter-spacing: -.04em; }
.rollback-modal > p:not(.section-kicker) { color: var(--muted); font-size: 13px; line-height: 1.6; }
.rollback-source { display: flex; justify-content: space-between; gap: 10px; margin: 18px 0; border-radius: 8px; background: #f6f1ed; padding: 10px; color: var(--muted); font-size: 11px; }
.rollback-source strong { color: var(--ink); }
.confirmation-field input { width: 100%; box-sizing: border-box; }
.modal-actions { justify-content: flex-end; margin-top: 22px; }
@media (prefers-reduced-motion: reduce) { *, *::before, *::after { animation-duration: .01ms !important; transition-duration: .01ms !important; } }
@media (max-width: 1180px) { .configuration-layout { grid-template-columns: 190px minmax(330px, 1fr); } .detail-pane { grid-column: 1 / -1; border-top: 1px solid var(--line); border-right: 0; } }
@media (max-width: 760px) { .configuration-page { padding: 20px 14px 35px; } .configuration-hero { display: grid; align-items: stretch; } .hero-actions { align-items: stretch; } .project-filter { flex: 1; } .hero-actions .button { align-self: end; } .metric-strip { grid-template-columns: repeat(2, 1fr); } .metric-cell:nth-child(2) { border-right: 0; } .metric-cell:nth-child(-n+2) { border-bottom: 1px solid var(--line); } .configuration-layout { display: block; } .domain-rail, .resource-pane { border-right: 0; border-bottom: 1px solid var(--line); } .domain-item { display: inline-grid; width: calc(50% - 6px); margin-right: 6px; vertical-align: top; } .rail-note { margin-top: 13px; } .detail-pane { min-height: 400px; } .snapshot-action { display: grid; } }
@media (max-width: 460px) { .hero-actions { display: grid; } .hero-actions .button { width: 100%; } .metric-cell { padding: 13px; } .metric-cell strong { font-size: 20px; } .domain-item { width: 100%; margin-right: 0; } .detail-summary { grid-template-columns: 1fr 1fr; } .detail-summary div:last-child { grid-column: 1 / -1; } }
</style>
