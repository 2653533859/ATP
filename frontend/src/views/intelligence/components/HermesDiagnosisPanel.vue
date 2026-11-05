<template>
  <section class="diagnosis-result">
    <div class="diagnosis-heading">
      <div>
        <h2>{{ t('hermes.diagnosis_title') }}</h2>
      </div>
      <a-tag :color="diagnosis.result.status === 'done' ? 'green' : 'orange'">{{ diagnosis.result.source }}</a-tag>
    </div>
    <p class="diagnosis-summary">{{ diagnosis.result.summary }}</p>
    <div v-if="diagnosis.result.repair_suggestions.length" class="suggestion-grid">
      <div
        v-for="suggestion in diagnosis.result.repair_suggestions"
        :key="`${diagnosis.taskId}-${suggestion.step_index}`"
        class="suggestion-card"
      >
        <span>{{ t('hermes.suggestion_step', { index: suggestion.step_index + 1 }) }}</span>
        <strong>{{ suggestion.step_name }}</strong>
        <p>{{ suggestion.suggested_change }}</p>
        <small>{{ suggestion.evidence }}</small>
      </div>
    </div>
    <div class="source-list diagnosis-source">
      <span class="source-label">{{ t('hermes.sources') }}</span>
      <button type="button" class="source-link" @click="emit('open-task', diagnosis.taskId)">
        {{ t('hermes.run_detail_source') }} <ArrowRightOutlined />
      </button>
    </div>
  </section>
</template>

<script setup lang="ts">
import { useI18n } from 'vue-i18n'
import { ArrowRightOutlined } from '@ant-design/icons-vue'
import type { HermesDiagnosis } from './hermesPanelTypes'

defineProps<{ diagnosis: HermesDiagnosis }>()
const emit = defineEmits<{ 'open-task': [taskId: string] }>()
const { t } = useI18n()
</script>

<style scoped>
.diagnosis-result {
  padding: 20px 24px;
  border: 1px solid var(--c-border);
  border-left: 3px solid var(--c-error);
  border-radius: var(--radius-lg);
  background: var(--c-bg-elevated);
  box-shadow: var(--shadow-sm);
}

.diagnosis-heading { display: flex; align-items: center; justify-content: space-between; gap: 16px; }

h2 {
  margin: 0;
  color: var(--c-text);
  font-size: 16px;
  font-weight: 600;
}

.diagnosis-summary { margin: 12px 0 0; color: var(--c-text-secondary); line-height: 1.6; font-size: 13px; }
.suggestion-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(210px, 1fr)); gap: 10px; margin-top: 16px; }
.suggestion-card { padding: 12px 14px; border: 1px solid var(--c-border); border-radius: var(--radius-md); background: var(--c-bg-subtle); }
.suggestion-card > span, .suggestion-card small { color: var(--c-text-tertiary); font-size: 11px; }
.suggestion-card strong { display: block; margin-top: 4px; color: var(--c-text); font-size: 13px; }
.suggestion-card p { margin: 6px 0; color: var(--c-text-secondary); font-size: 12px; line-height: 1.5; }
.source-list { display: flex; flex-wrap: wrap; gap: 8px; align-items: center; margin-top: 16px; }
.source-label { color: var(--c-text-tertiary); font-size: 11px; }
.source-link { display: inline-flex; gap: 5px; align-items: center; padding: 0; color: var(--c-primary); font-size: 12px; font-weight: 600; border: 0; cursor: pointer; background: transparent; }
.source-link:hover { color: var(--c-primary); }
button:focus-visible { outline: 2px solid var(--c-primary); outline-offset: 2px; }

@media (max-width: 680px) {
  .diagnosis-result { padding-right: 16px; padding-left: 16px; }
}
</style>
