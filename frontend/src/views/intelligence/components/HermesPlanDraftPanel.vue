<template>
  <section v-if="draft" class="plan-draft-card">
    <div class="plan-draft-heading">
      <div>
        <span class="section-kicker">{{ t('hermes.plan_kicker') }}</span>
        <h2>{{ t('hermes.plan_title') }}</h2>
        <p>{{ t('hermes.plan_description') }}</p>
        <div class="draft-status-line">
          <span class="draft-status-dot" :class="{ confirmed }" />
          <strong>{{ confirmed ? t('hermes.plan_status_confirmed') : t('hermes.plan_status_review') }}</strong>
          <span>·</span>
          <span>{{ t('hermes.plan_change_count', { count: changedCount }) }}</span>
        </div>
      </div>
      <a-space>
        <a-button :loading="saving" @click="emit('save')">{{ t('hermes.confirm_save_draft') }}</a-button>
        <a-button type="primary" @click="emit('confirm')">
          <ArrowRightOutlined /> {{ confirmed ? t('hermes.open_plans') : t('hermes.confirm_plan_draft') }}
        </a-button>
      </a-space>
    </div>
    <div class="plan-form-grid">
      <label>
        <span>{{ t('hermes.plan_name') }}</span>
        <input v-model="draft.name" maxlength="256" />
      </label>
      <label>
        <span>{{ t('hermes.plan_objective') }}</span>
        <textarea v-model="draft.objective" maxlength="2000" rows="3" />
      </label>
    </div>
    <div class="plan-points">
      <div class="points-heading">
        <span>{{ t('hermes.plan_points') }}</span>
        <button type="button" class="text-action" @click="emit('add-point')">
          <PlusOutlined /> {{ t('hermes.add_point') }}
        </button>
      </div>
      <div v-for="(_, index) in draft.testPoints" :key="`point-${index}`" class="point-row">
        <span>{{ String(index + 1).padStart(2, '0') }}</span>
        <input v-model="draft.testPoints[index]" maxlength="512" />
        <button type="button" class="icon-action" :aria-label="t('hermes.remove_point')" @click="emit('remove-point', index)">
          <CloseOutlined />
        </button>
      </div>
    </div>
    <div class="draft-impact-grid">
      <div><span>{{ t('hermes.plan_impact_modules') }}</span><strong>{{ selectedModuleCount }}</strong></div>
      <div><span>{{ t('hermes.plan_impact_cases') }}</span><strong>{{ selectedCaseCount }}</strong></div>
      <div><span>{{ t('hermes.plan_impact_regression') }}</span><strong>{{ selectedRegressionCount }}</strong></div>
      <div><span>{{ t('hermes.plan_impact_failures') }}</span><strong>{{ failedTaskCount }}</strong></div>
    </div>
    <div class="draft-structure-grid">
      <section class="draft-block">
        <div class="draft-block-heading">
          <span>{{ t('hermes.plan_scope_modules') }}</span>
          <small>{{ t('hermes.plan_scope_hint') }}</small>
        </div>
        <div v-for="module in draft.scopeModules" :key="module.id" class="draft-check-row">
          <input v-model="module.selected" type="checkbox" />
          <button type="button" class="draft-item-link" @click="emit('open-path', module.path)">
            {{ module.name }} <ArrowRightOutlined />
          </button>
        </div>
        <p v-if="!draft.scopeModules.length" class="draft-empty">{{ t('hermes.plan_no_modules') }}</p>
      </section>
      <section class="draft-block">
        <div class="draft-block-heading">
          <span>{{ t('hermes.plan_case_drafts') }}</span>
          <small>{{ t('hermes.plan_case_hint') }}</small>
        </div>
        <div v-for="item in draft.caseDrafts" :key="item.id" class="draft-case-row">
          <label class="draft-check-row"><input v-model="item.selected" type="checkbox" /></label>
          <button type="button" class="draft-item-link" @click="emit('open-path', item.path)">
            {{ item.id }} <ArrowRightOutlined />
          </button>
          <input v-model="item.title" class="draft-case-title" maxlength="256" :aria-label="t('hermes.plan_case_title')" />
          <input v-model="item.expected" class="draft-case-expected" maxlength="512" :aria-label="t('hermes.plan_case_expected')" />
        </div>
        <p v-if="!draft.caseDrafts.length" class="draft-empty">{{ t('hermes.plan_no_cases') }}</p>
      </section>
    </div>
    <div class="draft-structure-grid">
      <section class="draft-block">
        <div class="draft-block-heading">
          <span>{{ t('hermes.plan_regression_scope') }}</span>
          <small>{{ t('hermes.plan_regression_hint') }}</small>
        </div>
        <label v-for="item in draft.regressionScope" :key="item.taskId" class="draft-regression-row">
          <input v-model="item.selected" type="checkbox" />
          <span class="draft-regression-copy"><strong>{{ item.name }}</strong><small>{{ item.reason }}</small></span>
          <button type="button" class="text-action" @click="emit('open-path', item.path)">{{ t('hermes.view_evidence') }}</button>
        </label>
        <p v-if="!draft.regressionScope.length" class="draft-empty">{{ t('hermes.plan_no_regressions') }}</p>
      </section>
      <section class="draft-block draft-diff-block">
        <div class="draft-block-heading">
          <span>{{ t('hermes.plan_diff_title') }}</span>
          <small>{{ t('hermes.plan_diff_hint') }}</small>
        </div>
        <div v-for="row in diffRows" :key="row.key" class="draft-diff-row" :class="{ changed: row.changed }">
          <strong>{{ row.label }}</strong>
          <div><small>{{ t('hermes.plan_diff_before') }}</small><span>{{ row.before }}</span></div>
          <div><small>{{ t('hermes.plan_diff_after') }}</small><span>{{ row.after }}</span></div>
        </div>
      </section>
    </div>
    <div class="draft-sources">
      <span class="source-label">{{ t('hermes.plan_sources') }}</span>
      <button
        v-for="item in draft.sources"
        :key="item.path"
        type="button"
        class="source-link"
        @click="emit('open-source', item)"
      >
        {{ item.label }} <ArrowRightOutlined />
      </button>
    </div>
    <p class="draft-note"><BulbOutlined /> {{ t('hermes.plan_draft_note') }}</p>
  </section>
</template>

<script setup lang="ts">
import { useI18n } from 'vue-i18n'
import { ArrowRightOutlined, BulbOutlined, CloseOutlined, PlusOutlined } from '@ant-design/icons-vue'
import type { HermesSource } from './hermesPanelTypes'
import type { PlanDraft, PlanDraftDiffRow } from '../composables/useHermesPlanDraft'

defineProps<{
  saving: boolean
  confirmed: boolean
  changedCount: number
  selectedModuleCount: number
  selectedCaseCount: number
  selectedRegressionCount: number
  failedTaskCount: number
  diffRows: PlanDraftDiffRow[]
}>()

const emit = defineEmits<{
  save: []
  confirm: []
  'add-point': []
  'remove-point': [index: number]
  'open-path': [path: string]
  'open-source': [source: HermesSource]
}>()
const draft = defineModel<PlanDraft | null>('draft', { required: true })
const { t } = useI18n()
</script>

<style scoped>
.plan-draft-card {
  padding: 22px 24px;
  border: 1px solid var(--c-border);
  border-top: 4px solid var(--c-success);
  border-radius: var(--radius-lg);
  background: var(--c-bg-elevated);
  box-shadow: var(--shadow-sm);
}

.plan-draft-heading,
.points-heading { display: flex; align-items: center; }
.plan-draft-heading { align-items: flex-start; justify-content: space-between; gap: 16px; }
.section-kicker { color: var(--c-ai); }
h2 { margin: 4px 0 0; color: var(--c-text); font-size: 18px; font-weight: 700; letter-spacing: -.02em; }
.plan-draft-heading p { margin: 12px 0 0; color: var(--c-text-tertiary); line-height: 1.6; font-size: 12px; }
.plan-draft-heading :deep(.ant-btn) { flex: 0 0 auto; }
.draft-status-line { display: flex; align-items: center; gap: 7px; margin-top: 12px; color: var(--c-text-tertiary); font-size: 11px; }
.draft-status-line strong { color: var(--c-ai); font-size: 11px; }
.draft-status-dot { width: 7px; height: 7px; border-radius: 50%; background: var(--c-warning); box-shadow: 0 0 0 4px color-mix(in srgb, var(--c-warning) 12%, transparent); }
.draft-status-dot.confirmed { background: var(--c-success); box-shadow: 0 0 0 4px color-mix(in srgb, var(--c-success) 12%, transparent); }
.plan-form-grid { display: grid; grid-template-columns: .8fr 1.2fr; gap: 14px; margin-top: 18px; }
.plan-form-grid label { display: flex; flex-direction: column; gap: 6px; color: var(--c-text-secondary); font-size: 12px; font-weight: 600; }
.plan-form-grid textarea { resize: vertical; }
.plan-points { margin-top: 16px; }

.plan-form-grid input,
.plan-form-grid textarea,
.point-row input {
  min-width: 0;
  width: 100%;
  padding: 10px 14px;
  color: var(--c-text);
  font: inherit;
  font-size: 13px;
  border: 1px solid var(--c-border);
  border-radius: var(--radius-md);
  outline: none;
  background: var(--c-bg-elevated);
  transition: border-color .18s ease, box-shadow .18s ease;
}

.plan-form-grid input:focus,
.plan-form-grid textarea:focus,
.point-row input:focus { border-color: var(--c-ai); box-shadow: 0 0 0 3px var(--c-ai-soft); }
.draft-impact-grid { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 10px; margin-top: 18px; }
.draft-impact-grid > div { display: grid; gap: 4px; padding: 11px 12px; border: 1px solid var(--c-border); border-radius: var(--radius-md); background: var(--c-bg-subtle); }
.draft-impact-grid span, .draft-block-heading small, .draft-diff-row small { color: var(--c-text-tertiary); font-size: 10px; }
.draft-impact-grid strong { color: var(--c-text); font-size: 18px; font-family: 'JetBrains Mono', monospace; }
.draft-structure-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 12px; margin-top: 12px; }
.draft-block { min-width: 0; padding: 14px; border: 1px solid var(--c-border); border-radius: var(--radius-md); background: color-mix(in srgb, var(--c-bg-subtle) 72%, var(--c-bg-elevated)); }
.draft-block-heading { display: flex; align-items: baseline; justify-content: space-between; gap: 10px; margin-bottom: 10px; color: var(--c-text-secondary); font-size: 12px; font-weight: 700; }
.draft-block-heading small { font-weight: 400; text-align: right; }
.draft-check-row { display: flex; align-items: center; gap: 8px; min-width: 0; padding: 7px 0; color: var(--c-text-secondary); font-size: 12px; cursor: pointer; }
.draft-check-row input, .draft-regression-row > input { flex: 0 0 auto; width: 14px; height: 14px; accent-color: var(--c-ai); }
.draft-item-link { display: inline-flex; align-items: center; min-width: 0; gap: 4px; padding: 0; overflow: hidden; color: var(--c-ai); font: inherit; font-size: 11px; text-align: left; text-overflow: ellipsis; white-space: nowrap; border: 0; cursor: pointer; background: transparent; }
.draft-item-link:hover { color: var(--c-text); }
.draft-case-row { display: grid; grid-template-columns: auto auto minmax(0, 1fr); gap: 7px 9px; align-items: center; padding: 7px 0; border-top: 1px solid var(--c-border); }
.draft-case-row:first-of-type { border-top: 0; }
.draft-case-row .draft-check-row { grid-row: span 2; padding: 0; }
.draft-case-title { grid-column: 3; }
.draft-case-expected { grid-column: 2 / -1; }
.draft-case-row > input { min-width: 0; padding: 6px 8px; color: var(--c-text); font-size: 11px; border: 1px solid var(--c-border); border-radius: var(--radius-sm); background: var(--c-bg-elevated); }
.draft-regression-row { display: flex; align-items: flex-start; gap: 8px; padding: 8px 0; border-top: 1px solid var(--c-border); }
.draft-regression-row:first-of-type { border-top: 0; }
.draft-regression-copy { display: grid; flex: 1; min-width: 0; gap: 3px; }
.draft-regression-copy strong, .draft-regression-copy small { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.draft-regression-copy strong { color: var(--c-text); font-size: 12px; }
.draft-regression-copy small { color: var(--c-text-tertiary); font-size: 10px; }
.draft-empty { margin: 10px 0 0; color: var(--c-text-tertiary); font-size: 11px; }
.draft-diff-row { display: grid; grid-template-columns: 90px minmax(0, 1fr) minmax(0, 1fr); gap: 8px; align-items: start; padding: 8px 0; border-top: 1px solid var(--c-border); }
.draft-diff-row:first-of-type { border-top: 0; }
.draft-diff-row > strong { color: var(--c-text-secondary); font-size: 11px; }
.draft-diff-row > div { display: grid; gap: 3px; min-width: 0; }
.draft-diff-row > div span { overflow: hidden; color: var(--c-text-secondary); font-size: 11px; line-height: 1.45; text-overflow: ellipsis; }
.draft-diff-row.changed > div:last-child span { color: var(--c-ai); font-weight: 600; }
.draft-sources { display: flex; flex-wrap: wrap; align-items: center; gap: 8px; margin-top: 16px; padding-top: 12px; border-top: 1px solid var(--c-border); }
.source-label { color: var(--c-text-tertiary); font-size: 11px; }
.source-link, .text-action, .icon-action { border: 0; cursor: pointer; background: transparent; }
.source-link, .text-action { display: inline-flex; gap: 5px; align-items: center; padding: 0; color: var(--c-primary); font-size: 12px; font-weight: 600; }
.source-link:hover, .text-action:hover { color: var(--c-primary); border-color: var(--c-primary); }
.points-heading { justify-content: space-between; margin-bottom: 8px; color: var(--c-text-secondary); font-size: 12px; font-weight: 600; }
.point-row { display: flex; gap: 8px; align-items: center; margin-top: 6px; }
.point-row > span { width: 24px; color: var(--c-ai); font-size: 11px; font-weight: 800; font-family: 'JetBrains Mono', monospace; }
.icon-action { flex: 0 0 26px; width: 26px; height: 26px; color: var(--c-text-tertiary); border-radius: var(--radius-sm); }
.icon-action:hover { color: var(--c-error); background: var(--c-error-soft); }
.draft-note { margin: 14px 0 0; color: var(--c-text-tertiary); font-size: 11px; }
button:focus-visible, input:focus-visible, textarea:focus-visible { outline: 2px solid var(--c-ai); outline-offset: 2px; }

@media (max-width: 680px) {
  .plan-draft-heading { display: block; }
  .plan-form-grid, .draft-impact-grid, .draft-structure-grid { grid-template-columns: 1fr; }
  .plan-draft-card { padding-right: 16px; padding-left: 16px; }
  .draft-diff-row { grid-template-columns: 1fr; }
  .draft-diff-row > strong { margin-bottom: -2px; }
}
</style>
