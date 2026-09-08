<template>
  <section class="governance-card" :aria-label="t('hermes.governance_aria')">
    <div class="governance-heading">
      <div>
        <span class="section-kicker">{{ t('hermes.governance_kicker') }}</span>
        <h2>{{ t('hermes.governance_title') }}</h2>
      </div>
      <div class="governance-meta">
        <span class="governance-version">{{ summary.prompt_version }}</span>
        <span>{{ t('hermes.governance_eval_set', { size: summary.evaluation_set.size, version: summary.evaluation_set.version }) }}</span>
      </div>
    </div>
    <div class="governance-metrics">
      <div class="governance-metric governance-metric-citation">
        <strong>{{ governanceRate(summary.citation_coverage) }}</strong>
        <span>{{ t('hermes.governance_citation') }}</span>
      </div>
      <div class="governance-metric governance-metric-refusal">
        <strong>{{ governanceRate(summary.refusal_rate) }}</strong>
        <span>{{ t('hermes.governance_refusal') }}</span>
      </div>
      <div class="governance-metric">
        <strong>{{ summary.average_latency_ms }}<small>ms</small></strong>
        <span>{{ t('hermes.governance_latency') }}</span>
      </div>
      <div class="governance-metric">
        <strong>{{ governanceRate(summary.helpful_rate) }}</strong>
        <span>{{ t('hermes.governance_helpful') }}</span>
      </div>
    </div>
    <div class="governance-footer">
      <span>{{ t('hermes.governance_activity', { sessions: summary.sessions, messages: summary.assistant_messages }) }}</span>
      <span>{{ t('hermes.governance_feedback', { count: summary.feedback_total }) }}</span>
      <span v-if="!summary.cost_tracking.available" class="governance-cost-note">{{ t('hermes.governance_cost_unavailable') }}</span>
    </div>
  </section>
</template>

<script setup lang="ts">
import { useI18n } from 'vue-i18n'
import type { HermesGovernanceSummary } from '@/api'

defineProps<{ summary: HermesGovernanceSummary }>()

const { t } = useI18n()

function governanceRate(value: number | null | undefined) {
  return value == null ? '—' : `${Math.round(value * 100)}%`
}
</script>

<style scoped>
.governance-card {
  position: relative;
  overflow: hidden;
  padding: 17px 20px 15px;
  border: 1px solid var(--c-border);
  border-radius: var(--radius-lg);
  background:
    linear-gradient(100deg, color-mix(in srgb, var(--c-ai) 7%, var(--c-bg-elevated)), var(--c-bg-elevated) 58%),
    var(--c-bg-elevated);
  box-shadow: var(--shadow-sm);
}

.governance-card::after {
  position: absolute;
  top: -44px;
  right: 7%;
  width: 140px;
  height: 140px;
  border: 1px solid color-mix(in srgb, var(--c-ai) 22%, transparent);
  border-radius: 50%;
  content: '';
  pointer-events: none;
}

.governance-heading,
.governance-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 14px;
}

.governance-meta,
.governance-footer {
  color: var(--c-text-tertiary);
  font-size: 10px;
}

.section-kicker {
  color: var(--c-ai);
}

h2 {
  margin-bottom: 0;
  color: var(--c-text);
  font-size: 18px;
  font-weight: 700;
  letter-spacing: -.02em;
}

.governance-meta {
  display: flex;
  flex-wrap: wrap;
  justify-content: flex-end;
  gap: 7px;
  text-align: right;
}

.governance-version {
  padding: 3px 7px;
  color: var(--c-ai);
  border: 1px solid color-mix(in srgb, var(--c-ai) 30%, transparent);
  border-radius: var(--radius-full);
  background: color-mix(in srgb, var(--c-ai) 9%, transparent);
  font-family: 'JetBrains Mono', monospace;
}

.governance-metrics {
  position: relative;
  z-index: 1;
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 10px;
  margin-top: 14px;
}

.governance-metric {
  display: flex;
  flex-direction: column;
  gap: 4px;
  min-width: 0;
  padding: 10px 12px;
  border-left: 2px solid var(--c-border-strong);
  background: color-mix(in srgb, var(--c-bg-subtle) 68%, transparent);
}

.governance-metric strong {
  color: var(--c-text);
  font-size: 21px;
  font-family: 'JetBrains Mono', monospace;
  letter-spacing: -.04em;
}

.governance-metric strong small {
  margin-left: 2px;
  color: var(--c-text-tertiary);
  font-size: 10px;
  letter-spacing: 0;
}

.governance-metric span {
  overflow: hidden;
  color: var(--c-text-tertiary);
  font-size: 10px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.governance-metric-citation { border-left-color: var(--c-success); }
.governance-metric-refusal { border-left-color: var(--c-warning); }

.governance-footer {
  justify-content: flex-start;
  flex-wrap: wrap;
  margin-top: 12px;
  padding-top: 10px;
  border-top: 1px solid var(--c-border);
}

.governance-cost-note {
  margin-left: auto;
  color: var(--c-warning);
}

@media (max-width: 680px) {
  .governance-heading {
    display: block;
  }

  .governance-meta {
    justify-content: flex-start;
    margin-top: 10px;
    text-align: left;
  }

  .governance-metrics {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .governance-cost-note {
    margin-left: 0;
  }
}
</style>
