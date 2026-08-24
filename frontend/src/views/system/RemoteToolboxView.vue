<template>
  <div class="page-shell toolbox-page">
    <header class="toolbox-hero">
      <div class="toolbox-hero-glow" aria-hidden="true" />
      <div class="toolbox-hero-content">
        <div class="toolbox-eyebrow">{{ t('remote_toolbox.eyebrow') }}</div>
        <h1>{{ t('remote_toolbox.title') }}</h1>
        <p>{{ t('remote_toolbox.subtitle') }}</p>
      </div>
      <div class="toolbox-hero-actions">
        <a-button class="toolbox-export" :disabled="!overview" @click="exportOverview">
          {{ t('remote_toolbox.export') }}
        </a-button>
        <a-button class="toolbox-refresh" :loading="loading" @click="loadOverview">
          <ReloadOutlined :spin="loading" />
          {{ t('remote_toolbox.refresh') }}
        </a-button>
      </div>
    </header>

    <div class="toolbox-safe-note">
      <ToolOutlined />
      <span>{{ t('remote_toolbox.safe_note') }}</span>
      <span v-if="overview" class="toolbox-checked-at">{{ t('remote_toolbox.checked_at', { time: formatDate(overview.checked_at) }) }}</span>
    </div>

    <section class="toolbox-overall" :class="`is-${overview?.status || 'degraded'}`" aria-live="polite">
      <div class="overall-mark" :class="`is-${overview?.status || 'degraded'}`">
        <component :is="statusIcon(overview?.status === 'ok' ? 'ok' : overview?.status === 'error' ? 'error' : 'warning')" />
      </div>
      <div class="overall-copy">
        <span class="overall-label">{{ t('remote_toolbox.overall') }}</span>
        <strong>{{ t(`remote_toolbox.overall_${overview?.status || 'degraded'}`) }}</strong>
      </div>
      <div class="overall-counts">
        <span v-for="item in statusCounts" :key="item.key" :class="`count-${item.key}`">
          <b>{{ item.value }}</b> {{ t(`remote_toolbox.status.${item.key}`) }}
        </span>
      </div>
    </section>

    <section v-for="group in checkGroups" :key="group.key" class="toolbox-section">
      <div class="toolbox-section-heading">
        <div>
          <span class="section-kicker">0{{ group.index }}</span>
          <h2>{{ t(`remote_toolbox.${group.key}`) }}</h2>
        </div>
        <p>{{ t(`remote_toolbox.${group.key}_hint`) }}</p>
      </div>

      <div class="toolbox-check-grid">
        <article v-for="check in group.checks" :key="check.key" class="toolbox-check-card" :class="`status-${check.status}`">
          <div class="check-card-topline">
            <div class="check-symbol" :class="`status-${check.status}`">
              <component :is="statusIcon(check.status)" />
            </div>
            <div class="check-heading">
              <div class="check-title-row">
                <h3>{{ t(`remote_toolbox.check.${check.key}`) }}</h3>
                <span class="check-status">{{ t(`remote_toolbox.status.${check.status}`) }}</span>
              </div>
              <p>{{ t(`remote_toolbox.code.${check.code}`) }}</p>
            </div>
            <span class="check-latency">{{ t('remote_toolbox.latency', { value: check.latency_ms.toFixed(1) }) }}</span>
          </div>

          <div v-if="check.resources.length" class="resource-list">
            <div v-for="resource in check.resources" :key="resource.id" class="resource-row">
              <span class="resource-dot" :class="`status-${resource.status}`" aria-hidden="true" />
              <div class="resource-copy">
                <strong>{{ resource.name }}</strong>
                <span>{{ resource.summary }}</span>
              </div>
              <div v-if="metadataItems(resource.metadata).length" class="resource-meta">
                <span v-for="entry in metadataItems(resource.metadata)" :key="entry.key">
                  {{ t(entry.label) }}: {{ entry.value }}
                </span>
              </div>
            </div>
          </div>
          <div v-else class="resource-empty">{{ t('remote_toolbox.no_resources') }}</div>

          <button v-if="routeFor(check.key)" type="button" class="check-action" @click="openRoute(routeFor(check.key)!.path)">
            {{ t('remote_toolbox.action') }}
            <span>{{ t(routeFor(check.key)!.label) }}</span>
            <ArrowRightOutlined />
          </button>
        </article>
      </div>
    </section>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRouter } from 'vue-router'
import {
  ArrowRightOutlined,
  CheckCircleOutlined,
  CloseCircleOutlined,
  ReloadOutlined,
  ToolOutlined,
  WarningOutlined,
} from '@ant-design/icons-vue'
import { message } from 'ant-design-vue'
import {
  remoteToolboxApi,
  type RemoteToolboxCheckStatus,
  type RemoteToolboxOverview,
} from '@/api'

const { t, locale } = useI18n()
const router = useRouter()
const loading = ref(false)
const overview = ref<RemoteToolboxOverview | null>(null)

const checkGroups = computed(() => [
  {
    index: 1,
    key: 'infrastructure',
    checks: (overview.value?.checks || []).filter((item) => item.category === 'infrastructure'),
  },
  {
    index: 2,
    key: 'execution',
    checks: (overview.value?.checks || []).filter((item) => item.category === 'execution'),
  },
])

const statusCounts = computed(() => {
  const checks = overview.value?.checks || []
  return [
    { key: 'ok', value: checks.filter((item) => item.status === 'ok').length },
    { key: 'warning', value: checks.filter((item) => item.status === 'warning').length },
    { key: 'error', value: checks.filter((item) => item.status === 'error').length },
  ]
})

const routes: Record<string, { path: string; label: string }> = {
  postgres: { path: '/system/startup-config', label: 'remote_toolbox.action_startup' },
  redis: { path: '/system/startup-config', label: 'remote_toolbox.action_startup' },
  minio: { path: '/system/startup-config', label: 'remote_toolbox.action_startup' },
  android_worker: { path: '/devices', label: 'remote_toolbox.action_devices' },
  adb: { path: '/devices', label: 'remote_toolbox.action_devices' },
  web_worker: { path: '/ui-workbench', label: 'remote_toolbox.action_web' },
  performance_node: { path: '/system/performance', label: 'remote_toolbox.action_performance' },
}

function statusIcon(status: RemoteToolboxCheckStatus) {
  if (status === 'ok') return CheckCircleOutlined
  if (status === 'error') return CloseCircleOutlined
  return WarningOutlined
}

function routeFor(key: string) {
  return routes[key]
}

function openRoute(path: string) {
  void router.push(path)
}

function formatDate(value: string) {
  return new Date(value).toLocaleString(locale.value === 'zh-CN' ? 'zh-CN' : 'en-US', {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  })
}

function metadataItems(metadata: Record<string, unknown>) {
  const labels: Record<string, string> = {
    queues: 'remote_toolbox.metadata.queues',
    capabilities: 'remote_toolbox.metadata.capabilities',
    queue_name: 'remote_toolbox.metadata.queue_name',
    active_sessions: 'remote_toolbox.metadata.active_sessions',
    capacity: 'remote_toolbox.metadata.capacity',
    last_heartbeat_at: 'remote_toolbox.metadata.last_heartbeat_at',
  }
  return Object.entries(metadata)
    .filter(([, value]) => value !== null && value !== undefined && value !== '')
    .map(([key, value]) => ({
      key,
      label: labels[key] || key,
      value: Array.isArray(value) ? value.join(', ') : String(value),
    }))
}

async function loadOverview() {
  loading.value = true
  try {
    overview.value = await remoteToolboxApi.overview()
  } catch {
    message.error(t('remote_toolbox.load_failed'))
  } finally {
    loading.value = false
  }
}

function exportOverview() {
  if (!overview.value) return
  const blob = new Blob([JSON.stringify(overview.value, null, 2)], { type: 'application/json;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const anchor = document.createElement('a')
  anchor.href = url
  anchor.download = `atp-remote-toolbox-${new Date().toISOString().replace(/:/g, '-')}.json`
  anchor.click()
  URL.revokeObjectURL(url)
  message.success(t('remote_toolbox.export_success'))
}

onMounted(loadOverview)
</script>

<style scoped>
.toolbox-page {
  --toolbox-ink: #112b3c;
  --toolbox-muted: #6b7e8c;
  --toolbox-line: #dbe7eb;
  --toolbox-aqua: #1c9a9a;
  --toolbox-navy: #123747;
  padding-bottom: 40px;
}

.toolbox-hero {
  position: relative;
  display: flex;
  justify-content: space-between;
  gap: 24px;
  overflow: hidden;
  padding: 32px 36px;
  color: #f3fbfb;
  border-radius: 20px;
  background: linear-gradient(120deg, #103341 0%, #124b57 56%, #176a6b 100%);
  box-shadow: 0 18px 38px rgb(12 58 70 / 16%);
}

.toolbox-hero::after {
  position: absolute;
  right: 8%;
  bottom: -90px;
  width: 260px;
  height: 180px;
  border: 1px solid rgb(152 241 224 / 28%);
  border-radius: 50%;
  content: '';
  transform: rotate(-18deg);
}

.toolbox-hero-glow {
  position: absolute;
  top: -140px;
  right: 22%;
  width: 300px;
  height: 300px;
  background: rgb(78 222 196 / 13%);
  border-radius: 50%;
  filter: blur(2px);
}

.toolbox-hero-content,
.toolbox-hero-actions {
  position: relative;
  z-index: 1;
}

.toolbox-hero-actions {
  display: flex;
  align-items: flex-start;
  gap: 9px;
}

.toolbox-eyebrow,
.section-kicker {
  color: #82e0d0;
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.16em;
  text-transform: uppercase;
}

.toolbox-hero h1 {
  margin: 8px 0 10px;
  color: #fff;
  font-size: clamp(26px, 3vw, 40px);
  font-weight: 650;
  letter-spacing: -0.04em;
}

.toolbox-hero p {
  max-width: 680px;
  margin: 0;
  color: #c2dedf;
  line-height: 1.7;
}

.toolbox-refresh {
  align-self: flex-start;
  color: var(--toolbox-navy);
  border: 0;
  background: #b9f1e3;
  box-shadow: none;
}

.toolbox-refresh:hover,
.toolbox-refresh:focus-visible {
  color: var(--toolbox-navy);
  background: #d8fff4;
}

.toolbox-export {
  color: #d8efee;
  border-color: rgb(216 239 238 / 38%);
  background: rgb(255 255 255 / 8%);
  box-shadow: none;
}

.toolbox-export:hover,
.toolbox-export:focus-visible {
  color: #fff;
  border-color: rgb(216 239 238 / 72%);
  background: rgb(255 255 255 / 15%);
}

.toolbox-safe-note {
  display: flex;
  align-items: center;
  gap: 9px;
  margin: 16px 2px 22px;
  color: var(--toolbox-muted);
  font-size: 12px;
}

.toolbox-safe-note > :first-child {
  color: var(--toolbox-aqua);
}

.toolbox-checked-at {
  margin-left: auto;
  color: #8da0aa;
}

.toolbox-overall {
  display: flex;
  align-items: center;
  gap: 14px;
  margin-bottom: 34px;
  padding: 18px 22px;
  border: 1px solid var(--toolbox-line);
  border-radius: 15px;
  background: #fff;
}

.toolbox-overall.is-ok {
  border-color: #bce7dc;
  background: linear-gradient(90deg, #f4fffc, #fff);
}

.toolbox-overall.is-error {
  border-color: #f0caca;
  background: #fffafa;
}

.overall-mark,
.check-symbol {
  display: grid;
  flex: 0 0 auto;
  place-items: center;
  border-radius: 50%;
}

.overall-mark {
  width: 42px;
  height: 42px;
  font-size: 22px;
}

.overall-mark.is-ok,
.check-symbol.status-ok {
  color: #128878;
  background: #dff7f0;
}

.overall-mark.is-warning,
.check-symbol.status-warning {
  color: #bb7608;
  background: #fff0d5;
}

.overall-mark.is-error,
.check-symbol.status-error {
  color: #c34242;
  background: #ffe3e3;
}

.overall-copy {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.overall-label {
  color: var(--toolbox-muted);
  font-size: 12px;
}

.overall-copy strong {
  color: var(--toolbox-ink);
  font-size: 17px;
}

.overall-counts {
  display: flex;
  gap: 18px;
  margin-left: auto;
  color: var(--toolbox-muted);
  font-size: 12px;
}

.overall-counts b {
  margin-right: 3px;
  color: var(--toolbox-ink);
  font-size: 18px;
}

.overall-counts .count-ok b { color: #128878; }
.overall-counts .count-warning b { color: #bb7608; }
.overall-counts .count-error b { color: #c34242; }

.toolbox-section {
  margin-top: 30px;
}

.toolbox-section-heading {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 20px;
  margin-bottom: 15px;
  padding-bottom: 12px;
  border-bottom: 1px solid var(--toolbox-line);
}

.toolbox-section-heading > div {
  display: flex;
  align-items: baseline;
  gap: 11px;
}

.toolbox-section-heading h2 {
  margin: 0;
  color: var(--toolbox-ink);
  font-size: 19px;
  font-weight: 650;
  letter-spacing: -0.02em;
}

.toolbox-section-heading p {
  margin: 0;
  color: var(--toolbox-muted);
  font-size: 12px;
}

.toolbox-check-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 14px;
}

.toolbox-check-card {
  min-width: 0;
  padding: 20px;
  border: 1px solid var(--toolbox-line);
  border-top: 3px solid #aadbd4;
  border-radius: 13px;
  background: #fff;
  transition: transform 180ms ease, box-shadow 180ms ease;
}

.toolbox-check-card:hover {
  box-shadow: 0 10px 25px rgb(12 58 70 / 8%);
  transform: translateY(-2px);
}

.toolbox-check-card.status-warning { border-top-color: #edbd68; }
.toolbox-check-card.status-error { border-top-color: #e38d8d; }

.check-card-topline {
  display: flex;
  align-items: flex-start;
  gap: 12px;
}

.check-symbol {
  width: 32px;
  height: 32px;
  font-size: 16px;
}

.check-heading {
  min-width: 0;
  flex: 1;
}

.check-title-row {
  display: flex;
  align-items: center;
  gap: 8px;
}

.check-title-row h3 {
  overflow: hidden;
  margin: 0;
  color: var(--toolbox-ink);
  font-size: 15px;
  font-weight: 650;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.check-status {
  flex: 0 0 auto;
  padding: 2px 7px;
  color: #128878;
  border-radius: 10px;
  background: #e8f9f4;
  font-size: 11px;
}

.status-warning .check-status { color: #a66600; background: #fff4de; }
.status-error .check-status { color: #b23838; background: #ffeded; }

.check-heading p {
  margin: 5px 0 0;
  color: var(--toolbox-muted);
  font-size: 12px;
  line-height: 1.5;
}

.check-latency {
  flex: 0 0 auto;
  color: #8ba0a9;
  font-size: 11px;
}

.resource-list {
  display: flex;
  flex-direction: column;
  gap: 9px;
  margin-top: 18px;
  padding-top: 13px;
  border-top: 1px solid #edf2f3;
}

.resource-row {
  display: flex;
  align-items: center;
  min-width: 0;
  gap: 8px;
}

.resource-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: #25a78f;
}

.resource-dot.status-warning { background: #dc971f; }
.resource-dot.status-error { background: #cf5353; }

.resource-copy {
  display: flex;
  min-width: 0;
  flex-direction: column;
  gap: 2px;
}

.resource-copy strong {
  overflow: hidden;
  color: var(--toolbox-ink);
  font-size: 12px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.resource-copy span,
.resource-meta {
  color: var(--toolbox-muted);
  font-size: 11px;
}

.resource-meta {
  display: flex;
  flex-wrap: wrap;
  justify-content: flex-end;
  gap: 4px 9px;
  margin-left: auto;
  text-align: right;
}

.resource-empty {
  margin-top: 18px;
  padding-top: 13px;
  color: #98aab2;
  border-top: 1px solid #edf2f3;
  font-size: 12px;
}

.check-action {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  margin-top: 17px;
  padding: 0;
  color: var(--toolbox-aqua);
  border: 0;
  background: transparent;
  cursor: pointer;
  font-size: 12px;
}

.check-action span {
  color: var(--toolbox-ink);
  font-weight: 600;
}

.check-action:hover,
.check-action:focus-visible {
  color: #0d6e6f;
  outline: 2px solid #9ce1d6;
  outline-offset: 4px;
}

@media (max-width: 800px) {
  .toolbox-hero {
    flex-direction: column;
    padding: 25px;
  }

  .toolbox-hero-actions { align-items: flex-start; flex-wrap: wrap; }
  .toolbox-check-grid { grid-template-columns: 1fr; }
  .toolbox-section-heading { align-items: flex-start; flex-direction: column; gap: 6px; }
}

@media (max-width: 560px) {
  .toolbox-page { padding: 12px; }
  .toolbox-safe-note { align-items: flex-start; flex-wrap: wrap; }
  .toolbox-checked-at { width: 100%; margin-left: 22px; }
  .toolbox-overall { align-items: flex-start; flex-wrap: wrap; }
  .overall-counts { width: 100%; margin: 2px 0 0 56px; }
  .check-card-topline { flex-wrap: wrap; }
  .check-latency { width: 100%; margin-left: 44px; }
  .resource-meta { margin-left: 14px; }
}

@media (prefers-reduced-motion: reduce) {
  .toolbox-check-card { transition: none; }
}
</style>
