<template>
  <aside class="evidence-column">
    <section class="evidence-card quality-card">
      <div class="card-heading">
        <div>
          <span class="section-kicker">{{ t('hermes.quality_kicker') }}</span>
          <h2>{{ t('hermes.quality_title') }}</h2>
        </div>
        <CheckCircleOutlined />
      </div>
      <div class="quality-score"><strong>{{ qualityScore }}</strong><span>/100</span></div>
      <div class="quality-bar"><span :style="{ width: `${qualityScore}%` }" /></div>
      <div class="quality-grid">
        <div><span>{{ t('hermes.quality_pass_rate') }}</span><b>{{ passRate }}%</b></div>
        <div><span>{{ t('hermes.quality_runs') }}</span><b>{{ totalRuns }}</b></div>
        <div><span>{{ t('hermes.quality_coverage') }}</span><b>{{ coverageRate }}%</b></div>
        <div><span>{{ t('hermes.quality_defects') }}</span><b>{{ openDefects }}</b></div>
      </div>
      <button type="button" class="text-action" @click="emit('ask-quality')">
        {{ t('hermes.ask_quality') }} <ArrowRightOutlined />
      </button>
    </section>

    <section class="evidence-card failure-card">
      <div class="card-heading">
        <div>
          <span class="section-kicker">{{ t('hermes.failure_kicker') }}</span>
          <h2>{{ t('hermes.failure_title') }}</h2>
        </div>
        <ExclamationCircleOutlined />
      </div>
      <p class="card-description">{{ t('hermes.failure_description') }}</p>
      <div v-if="failedTasks.length" class="failure-list">
        <div
          v-for="task in failedTasks.slice(0, 5)"
          :key="task.id"
          class="failure-row"
          :class="{ selected: selectedTaskId === task.id }"
        >
          <button type="button" class="failure-main" @click="emit('select-task', task.id)">
            <span class="failure-mark" />
            <span class="failure-info">
              <strong>{{ task.name }}</strong>
              <small>{{ task.task_type }} · {{ formatTime(task.created_at) }}</small>
            </span>
          </button>
          <button type="button" class="diagnose-action" :disabled="diagnosing" @click="emit('explain-failure', task)">
            {{ t('hermes.explain') }}
          </button>
        </div>
      </div>
      <a-empty v-else :description="t('hermes.no_failures')" />
      <div class="failure-footer">
        <a-button type="link" @click="emit('open-task-center')">{{ t('hermes.open_task_center') }}</a-button>
        <a-button type="link" @click="emit('open-runs')">{{ t('hermes.open_runs') }}</a-button>
      </div>
    </section>
  </aside>
</template>

<script setup lang="ts">
import { useI18n } from 'vue-i18n'
import { ArrowRightOutlined, CheckCircleOutlined, ExclamationCircleOutlined } from '@ant-design/icons-vue'
import type { WorkbenchTaskItem } from '@/api'

defineProps<{
  qualityScore: number
  passRate: number
  totalRuns: number
  coverageRate: number
  openDefects: number
  failedTasks: WorkbenchTaskItem[]
  selectedTaskId: string | null
  diagnosing: boolean
}>()

const emit = defineEmits<{
  'ask-quality': []
  'select-task': [taskId: string]
  'explain-failure': [task: WorkbenchTaskItem]
  'open-task-center': []
  'open-runs': []
}>()
const { t } = useI18n()

function formatTime(value?: string | null) {
  return value ? value.slice(0, 19).replace('T', ' ') : t('hermes.not_available')
}
</script>

<style scoped>
.evidence-column { display: flex; flex-direction: column; gap: 18px; }

.evidence-card {
  padding: 20px;
  border: 1px solid var(--c-border);
  border-radius: var(--radius-lg);
  background: var(--c-bg-elevated);
  box-shadow: var(--shadow-sm);
}

.section-kicker { color: var(--c-ai); }
.card-heading { display: flex; align-items: center; justify-content: space-between; gap: 16px; }

h2 {
  margin: 4px 0 0;
  color: var(--c-text);
  font-size: 18px;
  font-weight: 700;
  letter-spacing: -.02em;
}

.card-heading :deep(.anticon) { color: var(--c-ai); font-size: 20px; }
.failure-card .card-heading :deep(.anticon) { color: var(--c-error); }
.quality-score { display: flex; align-items: baseline; gap: 4px; margin-top: 16px; }
.quality-score strong { color: var(--c-text); font-size: 38px; font-weight: 700; font-family: 'JetBrains Mono', monospace; letter-spacing: -.04em; }
.quality-score span { color: var(--c-text-tertiary); font-size: 13px; }
.quality-bar { height: 6px; margin: 8px 0 16px; overflow: hidden; border-radius: 99px; background: var(--c-bg-muted); }
.quality-bar span { display: block; height: 100%; border-radius: inherit; background: linear-gradient(90deg, #8b5cf6, #10b981); transition: width .35s ease; }
.quality-grid { display: grid; grid-template-columns: repeat(2, 1fr); gap: 12px; padding-top: 12px; border-top: 1px solid var(--c-border); }
.quality-grid div { display: flex; flex-direction: column; gap: 2px; }
.quality-grid span { color: var(--c-text-tertiary); font-size: 11px; }
.quality-grid b { color: var(--c-text); font-size: 16px; font-family: 'JetBrains Mono', monospace; }
.text-action, .diagnose-action, .failure-main { border: 0; cursor: pointer; background: transparent; }
.text-action { display: inline-flex; gap: 5px; align-items: center; padding: 0; color: var(--c-primary); font-size: 12px; font-weight: 600; }
.text-action:hover { color: var(--c-primary); }
.quality-card .text-action { margin-top: 16px; }
.card-description { margin: 10px 0 14px; color: var(--c-text-secondary); font-size: 12px; line-height: 1.5; }
.failure-list { display: flex; flex-direction: column; gap: 8px; }
.failure-row { display: flex; align-items: center; gap: 6px; padding: 8px 10px; border: 1px solid var(--c-border); border-radius: var(--radius-md); background: var(--c-bg-subtle); transition: all .15s ease; }
.failure-row.selected { border-color: var(--c-ai); background: var(--c-ai-soft); }
.failure-main { display: flex; flex: 1; gap: 8px; align-items: center; min-width: 0; padding: 0; color: var(--c-text); text-align: left; }
.failure-mark { width: 7px; height: 7px; border-radius: 50%; background: var(--c-error); }
.failure-info { display: flex; flex-direction: column; min-width: 0; gap: 2px; }
.failure-info strong, .failure-info small { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.failure-info strong { color: var(--c-text); font-size: 12px; }
.failure-info small { color: var(--c-text-tertiary); font-size: 10px; font-family: 'JetBrains Mono', monospace; }
.diagnose-action { flex-shrink: 0; padding: 3px 6px; color: var(--c-ai); font-size: 11px; font-weight: 600; }
.diagnose-action:hover:not(:disabled) { color: var(--c-text); }
.failure-footer { display: flex; justify-content: space-between; margin-top: 10px; border-top: 1px solid var(--c-border); }
.failure-footer :deep(.ant-btn) { padding-right: 0; padding-left: 0; font-size: 12px; }
button:focus-visible { outline: 2px solid var(--c-ai); outline-offset: 2px; }

@media (prefers-reduced-motion: reduce) {
  .quality-bar span { transition: none; }
}

@media (max-width: 920px) {
  .evidence-column { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); align-items: start; }
}

@media (max-width: 680px) {
  .evidence-column { grid-template-columns: 1fr; }
}
</style>
