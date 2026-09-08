<template>
  <section class="conversation-context-card" :aria-label="t('hermes.conversation_context_aria')">
    <div class="conversation-context-heading">
      <div>
        <span class="section-kicker">{{ t('hermes.session_kicker') }}</span>
        <strong>{{ t('hermes.session_id', { id: shortConversationId }) }}</strong>
        <p>{{ t('hermes.session_description') }}</p>
      </div>
      <a-button size="small" @click="emit('new-conversation')">
        <PlusOutlined /> {{ t('hermes.new_conversation') }}
      </a-button>
    </div>
    <div class="conversation-filter-grid">
      <div class="conversation-filter">
        <label for="hermes-source-filter">{{ t('hermes.source_filter') }}</label>
        <a-select
          id="hermes-source-filter"
          v-model:value="sourceTypes"
          mode="multiple"
          :options="sourceTypeOptions"
          :max-tag-count="1"
          allow-clear
          :placeholder="t('hermes.source_filter_placeholder')"
        />
      </div>
      <div class="conversation-filter">
        <label for="hermes-date-filter">{{ t('hermes.date_filter') }}</label>
        <a-range-picker
          id="hermes-date-filter"
          v-model:value="dateRange"
          :placeholder="[t('hermes.date_from'), t('hermes.date_to')]"
          allow-clear
        />
      </div>
      <div class="conversation-filter">
        <label for="hermes-context-budget">{{ t('hermes.context_budget') }}</label>
        <a-select id="hermes-context-budget" v-model:value="contextBudget" :options="contextBudgetOptions" />
      </div>
    </div>
    <div class="conversation-context-status">
      <span class="status-dot" />
      <span>{{ t('hermes.context_status', { used: historyUsed, omitted: historyOmitted, chars: contextChars, budget: contextBudget }) }}</span>
    </div>
  </section>
</template>

<script setup lang="ts">
import { useI18n } from 'vue-i18n'
import { PlusOutlined } from '@ant-design/icons-vue'
import type { Dayjs } from 'dayjs'
import type { HermesSourceType } from '@/api'

defineProps<{
  shortConversationId: string
  sourceTypeOptions: Array<{ label: string; value: HermesSourceType }>
  contextBudgetOptions: Array<{ label: string; value: number }>
  historyUsed: number
  historyOmitted: number
  contextChars: number
}>()

const emit = defineEmits<{ 'new-conversation': [] }>()
const sourceTypes = defineModel<HermesSourceType[]>('sourceTypes', { required: true })
const dateRange = defineModel<[Dayjs, Dayjs] | undefined>('dateRange', { required: true })
const contextBudget = defineModel<number>('contextBudget', { required: true })
const { t } = useI18n()
</script>

<style scoped>
.conversation-context-card {
  display: flex;
  flex-direction: column;
  gap: 14px;
  padding: 16px 20px;
  border: 1px solid var(--c-border);
  border-radius: var(--radius-lg);
  background:
    linear-gradient(110deg, color-mix(in srgb, var(--c-ai) 5%, var(--c-bg-elevated)), var(--c-bg-elevated));
  box-shadow: var(--shadow-sm);
}

.section-kicker {
  color: var(--c-ai);
}

.conversation-context-heading,
.conversation-context-status {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
}

.conversation-context-heading strong {
  display: block;
  margin-top: 4px;
  color: var(--c-text);
  font-size: 13px;
  font-family: 'JetBrains Mono', monospace;
}

.conversation-context-heading p {
  margin: 5px 0 0;
  color: var(--c-text-secondary);
  font-size: 12px;
}

.conversation-context-heading :deep(.ant-btn) {
  flex: 0 0 auto;
  border-color: var(--c-border-strong);
  border-radius: var(--radius-md);
}

.conversation-filter-grid {
  display: grid;
  grid-template-columns: minmax(180px, 1fr) minmax(240px, 1.2fr) minmax(150px, .7fr);
  gap: 12px;
}

.conversation-filter {
  display: flex;
  flex-direction: column;
  gap: 6px;
  min-width: 0;
}

.conversation-filter label {
  color: var(--c-text-secondary);
  font-size: 11px;
  font-weight: 700;
  letter-spacing: .04em;
}

.conversation-filter :deep(.ant-select),
.conversation-filter :deep(.ant-picker) {
  width: 100%;
}

.conversation-context-status {
  justify-content: flex-start;
  color: var(--c-text-secondary);
  font-size: 11px;
}

.status-dot {
  flex: 0 0 auto;
  width: 6px;
  height: 6px;
}

@media (max-width: 680px) {
  .conversation-context-heading {
    display: block;
  }

  .conversation-context-heading :deep(.ant-btn) {
    margin-top: 10px;
  }

  .conversation-filter-grid {
    grid-template-columns: 1fr;
  }
}
</style>
