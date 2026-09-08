<template>
  <section class="conversation-card" aria-live="polite">
    <header class="conversation-header">
      <div>
        <span class="section-kicker">HERMES / PROJECT COPILOT</span>
        <h2>{{ t('hermes.conversation_title') }}</h2>
      </div>
      <a-tag color="green"><span class="tag-dot" /> {{ t('hermes.data_bound') }}</a-tag>
    </header>

    <div class="message-list" role="log" :aria-label="t('hermes.message_list_aria')">
      <article v-for="item in messages" :key="item.id" class="message" :class="`message-${item.role}`">
        <div class="message-avatar" aria-hidden="true">
          <span v-if="item.role === 'assistant'">H</span>
          <span v-else>你</span>
        </div>
        <div class="message-body">
          <div class="message-meta">
            <strong>{{ item.role === 'assistant' ? 'Hermes' : t('hermes.you') }}</strong>
            <span>{{ formatTime(item.createdAt) }}</span>
          </div>
          <p class="message-text">{{ item.text }}</p>
          <span v-if="item.mode" class="message-mode">{{ t(`hermes.modes.${item.mode}`) }}</span>
          <div v-if="item.toolSteps?.length" class="message-tool-chain">
            <span class="tool-chain-label">{{ t('hermes.tool_chain') }}</span>
            <span v-for="step in item.toolSteps" :key="`${item.id}-${step.tool}`" class="tool-chain-step">
              {{ t(`hermes.tool_labels.${step.tool}`) }} · {{ t(`hermes.tool_status.${step.status}`) }}
            </span>
          </div>
          <div v-if="item.taskIds?.length" class="message-task-list">
            <button
              v-for="taskId in item.taskIds"
              :key="taskId"
              type="button"
              class="message-task"
              @click="emit('select-task', taskId)"
            >
              <span class="task-status" />
              <span>{{ taskNames[taskId] || taskId }}</span>
              <ArrowRightOutlined />
            </button>
          </div>
          <div v-if="item.sources?.length" class="source-list">
            <span class="source-label">{{ t('hermes.sources') }}</span>
            <button
              v-for="source in item.sources"
              :key="`${item.id}-${source.label}`"
              type="button"
              class="source-link"
              @click="emit('open-source', source)"
            >
              {{ source.label }} <ArrowRightOutlined />
            </button>
          </div>
          <a-space v-if="item.role === 'assistant' && item.backendIndex != null" size="small">
            <a-button type="text" size="small" @click="emit('rate-message', item, 'helpful')">{{ t('hermes.helpful') }}</a-button>
            <a-button type="text" size="small" @click="emit('rate-message', item, 'not_helpful')">{{ t('hermes.not_helpful') }}</a-button>
          </a-space>
        </div>
      </article>
      <div v-if="diagnosing" class="thinking-row">
        <span class="thinking-pulse" />
        <span>{{ t('hermes.diagnosing') }}</span>
      </div>
      <div v-if="querying" class="thinking-row">
        <span class="thinking-pulse" />
        <span>{{ t('hermes.querying') }}</span>
      </div>
    </div>

    <div class="prompt-stations">
      <span class="section-kicker">{{ t('hermes.prompt_kicker') }}</span>
      <div class="prompt-grid">
        <button
          v-for="prompt in promptOptions"
          :key="prompt.key"
          type="button"
          class="prompt-card"
          :disabled="busy"
          @click="emit('ask-prompt', prompt.key)"
        >
          <span class="prompt-icon" :class="`prompt-icon-${prompt.key}`">{{ prompt.mark }}</span>
          <span>
            <strong>{{ prompt.title }}</strong>
            <small>{{ prompt.description }}</small>
          </span>
          <ArrowRightOutlined />
        </button>
      </div>
    </div>

    <form class="composer" @submit.prevent="emit('submit')">
      <input
        v-model="inputText"
        :disabled="busy"
        :placeholder="t('hermes.input_placeholder')"
        :aria-label="t('hermes.input_aria')"
      />
      <a-button type="primary" html-type="submit" :disabled="!inputText.trim() || busy">
        {{ t('hermes.send') }} <ArrowRightOutlined />
      </a-button>
    </form>
    <p class="composer-note"><BulbOutlined /> {{ t('hermes.composer_note') }}</p>
  </section>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { ArrowRightOutlined, BulbOutlined } from '@ant-design/icons-vue'
import type { HermesMessage, HermesPromptKey, HermesPromptOption, HermesSource } from './hermesPanelTypes'

const props = defineProps<{
  messages: HermesMessage[]
  promptOptions: HermesPromptOption[]
  taskNames: Record<string, string>
  loading: boolean
  diagnosing: boolean
  querying: boolean
}>()

const emit = defineEmits<{
  'select-task': [taskId: string]
  'open-source': [source: HermesSource]
  'rate-message': [message: HermesMessage, rating: 'helpful' | 'not_helpful']
  'ask-prompt': [key: HermesPromptKey]
  submit: []
}>()
const inputText = defineModel<string>('inputText', { required: true })
const busy = computed(() => props.loading || props.diagnosing || props.querying)
const { t } = useI18n()

function formatTime(value?: string | null) {
  return value ? value.slice(0, 19).replace('T', ' ') : t('hermes.not_available')
}
</script>

<style scoped>
.conversation-card {
  min-width: 0;
  overflow: hidden;
  border: 1px solid var(--c-border);
  border-radius: var(--radius-lg);
  background: var(--c-bg-elevated);
  box-shadow: var(--shadow-sm);
}

.conversation-header,
.prompt-stations,
.composer {
  padding: 18px 22px;
}

.conversation-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  border-bottom: 1px solid var(--c-border);
}

.section-kicker { color: var(--c-ai); }

h2 {
  margin: 4px 0 0;
  color: var(--c-text);
  font-size: 18px;
  font-weight: 700;
  letter-spacing: -.02em;
}

.conversation-header :deep(.ant-tag) {
  display: inline-flex;
  align-items: center;
  gap: 7px;
  margin: 0;
  border-radius: var(--radius-full);
}

.message-list {
  display: flex;
  flex-direction: column;
  gap: 20px;
  min-height: 340px;
  max-height: 580px;
  padding: 22px;
  overflow: auto;
  background: var(--c-bg-subtle);
}

.message { display: flex; gap: 12px; max-width: 90%; }
.message-user { align-self: flex-end; flex-direction: row-reverse; }

.message-avatar {
  display: grid;
  flex: 0 0 32px;
  place-items: center;
  width: 32px;
  height: 32px;
  color: #fff;
  font-size: 12px;
  font-weight: 800;
  border-radius: var(--radius-md);
  background: linear-gradient(135deg, #40ebe3 0%, #4a51ff 100%);
  box-shadow: 0 2px 8px rgba(127, 105, 255, .35);
}

.message-user .message-avatar {
  background: linear-gradient(135deg, #5a4bfe, #897eff);
  box-shadow: 0 2px 8px rgba(90, 75, 254, .35);
}

.message-body { min-width: 0; }

.message-meta {
  display: flex;
  gap: 9px;
  align-items: baseline;
  margin-bottom: 5px;
  color: var(--c-text-tertiary);
  font-size: 11px;
}

.message-meta strong { color: var(--c-text); font-size: 12px; font-weight: 600; }

.message-text {
  margin-bottom: 0;
  padding: 12px 16px;
  color: var(--c-text);
  line-height: 1.65;
  font-size: 13px;
  border: 1px solid var(--c-border);
  border-radius: 4px 16px 16px 16px;
  background: var(--c-bg-elevated);
  box-shadow: var(--shadow-xs);
}

.message-user .message-text {
  border-color: var(--c-primary-glow);
  border-radius: 16px 4px 16px 16px;
  background: var(--c-primary-soft);
}

.message-mode {
  display: inline-flex;
  margin-top: 8px;
  padding: 3px 8px;
  color: var(--c-primary);
  font-size: 10px;
  font-weight: 600;
  line-height: 1.2;
  border: 1px solid var(--c-primary-glow);
  border-radius: var(--radius-full);
  background: var(--c-primary-soft);
}

.message-tool-chain { display: flex; flex-wrap: wrap; align-items: center; gap: 6px; margin-top: 9px; color: var(--c-text-tertiary); font-size: 10px; }
.tool-chain-label { color: var(--c-ai); font-family: 'JetBrains Mono', monospace; letter-spacing: .04em; text-transform: uppercase; }
.tool-chain-step { padding: 3px 7px; border: 1px solid var(--c-border); border-radius: var(--radius-full); background: var(--c-bg-subtle); }
.message-task-list { display: flex; flex-direction: column; gap: 7px; margin-top: 10px; }

.message-task,
.source-link { border: 0; cursor: pointer; background: transparent; }

.message-task {
  display: flex;
  align-items: center;
  gap: 8px;
  width: min(440px, 100%);
  padding: 8px 12px;
  color: var(--c-text);
  text-align: left;
  border: 1px solid var(--c-border);
  border-radius: var(--radius-sm);
  background: var(--c-bg-elevated);
  transition: all .15s ease;
}

.message-task:hover,
.source-link:hover { color: var(--c-primary); border-color: var(--c-primary); }
.message-task > span:nth-child(2) { flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.task-status { width: 7px; height: 7px; border-radius: 50%; background: var(--c-error); }
.source-list { display: flex; flex-wrap: wrap; gap: 8px; align-items: center; margin-top: 10px; }
.source-label { color: var(--c-text-tertiary); font-size: 11px; }
.source-link { display: inline-flex; gap: 5px; align-items: center; padding: 0; color: var(--c-primary); font-size: 12px; font-weight: 600; }
.thinking-row { display: flex; align-items: center; gap: 9px; margin-left: 44px; color: var(--c-text-secondary); font-size: 12px; }

.thinking-pulse {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--c-ai);
  animation: pulse 1.1s ease-in-out infinite;
}

.prompt-stations { border-top: 1px solid var(--c-border); }
.prompt-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 10px; margin-top: 12px; }

.prompt-card {
  display: grid;
  grid-template-columns: auto minmax(0, 1fr) auto;
  gap: 10px;
  align-items: center;
  padding: 12px 14px;
  color: var(--c-text);
  text-align: left;
  border: 1px solid var(--c-border);
  border-radius: var(--radius-md);
  cursor: pointer;
  background: var(--c-bg-elevated);
  transition: transform .18s ease, border-color .18s ease, box-shadow .18s ease;
}

.prompt-card:hover:not(:disabled) { border-color: var(--c-ai); box-shadow: var(--shadow-sm); transform: translateY(-2px); }
.prompt-card:disabled { cursor: wait; opacity: .55; }
.prompt-icon { display: grid; place-items: center; width: 30px; height: 30px; color: #fff; font-size: 13px; font-weight: 800; border-radius: var(--radius-sm); background: var(--c-ai); }
.prompt-icon-explain_failure { background: var(--c-error); }
.prompt-icon-test_plan { background: var(--c-info); }
.prompt-icon-quality { background: var(--c-primary); }
.prompt-card strong, .prompt-card small { display: block; }
.prompt-card strong { font-size: 12px; font-weight: 600; }
.prompt-card small { margin-top: 2px; overflow: hidden; color: var(--c-text-tertiary); font-size: 11px; text-overflow: ellipsis; white-space: nowrap; }
.prompt-card > .anticon { color: var(--c-text-tertiary); }
.composer { display: flex; gap: 10px; border-top: 1px solid var(--c-border); }

.composer input {
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

.composer input:focus { border-color: var(--c-ai); box-shadow: 0 0 0 3px var(--c-ai-soft); }
.composer .ant-btn { flex-shrink: 0; border-radius: var(--radius-md); }
.composer-note { margin: -6px 24px 16px; color: var(--c-text-tertiary); font-size: 11px; }
button:focus-visible, input:focus-visible { outline: 2px solid var(--c-ai); outline-offset: 2px; }

@keyframes pulse {
  0%, 100% { opacity: .35; transform: scale(.8); }
  50% { opacity: 1; transform: scale(1.15); }
}

@media (prefers-reduced-motion: reduce) {
  .thinking-pulse, .prompt-card { animation: none; transition: none; }
}

@media (max-width: 680px) {
  .conversation-header, .prompt-stations, .composer { padding-right: 16px; padding-left: 16px; }
  .message-list { padding: 16px; }
  .message { max-width: 100%; }
  .prompt-grid { grid-template-columns: 1fr; }
  .composer { align-items: stretch; flex-direction: column; }
}
</style>
