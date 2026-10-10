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
          <div v-if="item.role === 'assistant'" class="markdown-body" v-html="renderMarkdown(item.text)" />
          <p v-else class="message-text">{{ item.text }}</p>
          <span v-if="item.mode" class="message-mode">{{ t(`hermes.modes.${item.mode}`) }}</span>
          <details v-if="item.toolSteps?.length" class="message-tool-chain">
            <summary>{{ t('hermes.tool_chain') }}</summary>
            <span class="tool-chain-label">
              {{ t('hermes.tool_chain') }}
              <span v-if="item.planner">· {{ t(`hermes.planner_source.${item.planner.source}`) }}</span>
              <span v-if="item.planner?.validation === 'accepted'">· {{ t('hermes.planner_validated') }}</span>
            </span>
            <span v-for="step in item.toolSteps" :key="`${item.id}-${step.tool}`" class="tool-chain-step">
              {{ t(`hermes.tool_labels.${step.tool}`) }} · {{ t(`hermes.tool_status.${step.status}`) }}
              <small v-if="step.reason">{{ step.reason }}</small>
            </span>
          </details>
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
          <a-space v-if="item.role === 'assistant' && item.backendIndex != null && item.backendMessageId" size="small">
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

    <form class="composer" @submit.prevent="submitMessage">
      <a-textarea
        v-model:value="inputText"
        :auto-size="{ minRows: 3, maxRows: 10 }"
        :disabled="busy"
        :placeholder="t('hermes.input_placeholder')"
        :aria-label="t('hermes.input_aria')"
        @keydown="handleComposerKeydown"
      />
      <div class="composer-actions">
        <span>{{ t('hermes.input_shortcut') }}</span>
        <a-button type="primary" html-type="submit" :disabled="!inputText.trim() || busy">
          {{ t('hermes.send') }} <ArrowRightOutlined />
        </a-button>
      </div>
    </form>
    <p class="composer-note"><BulbOutlined /> {{ t('hermes.composer_note') }}</p>
  </section>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { ArrowRightOutlined, BulbOutlined } from '@ant-design/icons-vue'
import type { HermesMessage, HermesPromptKey, HermesPromptOption, HermesSource } from './hermesPanelTypes'
import { renderMarkdown } from '@/utils/markdown'

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
const { t } = useI18n()
const busy = computed(() => props.loading || props.diagnosing || props.querying)

function submitMessage() {
  if (!busy.value && inputText.value.trim()) emit('submit')
}

function handleComposerKeydown(event: KeyboardEvent) {
  if (event.isComposing || event.key !== 'Enter' || !(event.ctrlKey || event.metaKey)) return
  event.preventDefault()
  submitMessage()
}

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
  padding: 14px 20px;
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
  gap: 16px;
  height: clamp(220px, 34vh, 400px);
  min-height: 220px;
  padding: 18px 20px;
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

.message-text,
.markdown-body {
  margin-bottom: 0;
  padding: 12px 16px;
  color: var(--c-text);
  line-height: 1.65;
  font-size: 13px;
  border: 1px solid var(--c-border);
  border-radius: 4px 16px 16px 16px;
  background: var(--c-bg-elevated);
  box-shadow: var(--shadow-xs);
  word-break: break-word;
}

.markdown-body :deep(h1),
.markdown-body :deep(h2),
.markdown-body :deep(h3),
.markdown-body :deep(h4) {
  margin: 12px 0 6px;
  font-weight: 700;
  color: var(--c-text);
  line-height: 1.35;
}

.markdown-body :deep(h1) { font-size: 16px; }
.markdown-body :deep(h2) { font-size: 15px; border-bottom: 1px solid var(--c-border); padding-bottom: 4px; }
.markdown-body :deep(h3) { font-size: 14px; }
.markdown-body :deep(h4) { font-size: 13px; }

.markdown-body :deep(p) { margin: 0 0 8px; }
.markdown-body :deep(p:last-child) { margin-bottom: 0; }
.markdown-body :deep(ul), .markdown-body :deep(ol) { margin: 0 0 8px; padding-left: 20px; }
.markdown-body :deep(li) { margin-bottom: 3px; }
.markdown-body :deep(blockquote) {
  margin: 6px 0;
  padding: 6px 12px;
  border-left: 3px solid var(--c-primary);
  background: var(--c-primary-soft);
  color: var(--c-text-secondary);
  border-radius: 0 var(--radius-sm) var(--radius-sm) 0;
}
.markdown-body :deep(pre) {
  margin: 8px 0;
  padding: 10px 12px;
  overflow-x: auto;
  border: 1px solid var(--c-border);
  border-radius: var(--radius-md);
  background: var(--c-bg-subtle);
  font-family: 'JetBrains Mono', Consolas, Monaco, monospace;
  font-size: 12px;
  line-height: 1.5;
}
.markdown-body :deep(code) {
  padding: 2px 6px;
  border-radius: 4px;
  background: var(--c-primary-soft);
  color: var(--c-primary);
  font-family: 'JetBrains Mono', Consolas, Monaco, monospace;
  font-size: 12px;
}
.markdown-body :deep(pre code) { padding: 0; background: transparent; color: var(--c-text); font-size: 12px; }
.markdown-body :deep(table) { width: 100%; margin: 8px 0; border-collapse: collapse; }
.markdown-body :deep(th), .markdown-body :deep(td) { padding: 5px 8px; border: 1px solid var(--c-border); font-size: 12px; }
.markdown-body :deep(th) { background: var(--c-bg-subtle); font-weight: 600; }
.markdown-body :deep(hr) { margin: 12px 0; border: 0; border-top: 1px solid var(--c-border); }

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

.message-tool-chain { margin-top: 9px; color: var(--c-text-tertiary); font-size: 10px; }
.tool-chain-label { color: var(--c-ai); font-family: 'JetBrains Mono', monospace; letter-spacing: .04em; text-transform: uppercase; }
.tool-chain-step { display: inline-block; margin: 4px 4px 0 0; padding: 3px 7px; border: 1px solid var(--c-border); border-radius: var(--radius-full); background: var(--c-bg-subtle); }
.tool-chain-step small { display: block; max-width: 360px; margin-top: 2px; color: var(--c-text-secondary); font-size: 10px; white-space: normal; }
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

.prompt-stations { border-top: 1px solid var(--c-border); padding: 12px 22px; }
.prompt-grid { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 0; }

.prompt-card {
  display: grid;
  grid-template-columns: auto minmax(0, 1fr) auto;
  gap: 10px;
  align-items: center;
  padding: 8px 10px;
  color: var(--c-text);
  text-align: left;
  border: 1px solid var(--c-border);
  border-radius: var(--radius-md);
  cursor: pointer;
  background: var(--c-bg-elevated);
  transition: transform .18s ease, border-color .18s ease, box-shadow .18s ease;
}

.prompt-card:hover:not(:disabled) { border-color: var(--c-ai); background: var(--c-bg-subtle); }
.prompt-card:disabled { cursor: wait; opacity: .55; }
.prompt-icon { display: grid; place-items: center; width: 20px; height: 20px; color: var(--c-text-secondary); font-size: 11px; font-weight: 600; border-radius: 4px; background: var(--c-bg-subtle); }
.prompt-icon-explain_failure, .prompt-icon-test_plan, .prompt-icon-quality { background: var(--c-bg-subtle); }
.prompt-card strong, .prompt-card small { display: block; }
.prompt-card strong { font-size: 12px; font-weight: 600; }
.prompt-card small { display: none; }
.prompt-card > .anticon { color: var(--c-text-tertiary); }
.composer { display: flex; flex-direction: column; gap: 10px; border-top: 1px solid var(--c-border); }

.composer :deep(textarea) {
  min-width: 0;
  width: 100%;
  padding: 10px 14px;
  color: var(--c-text);
  font: inherit;
  font-size: 14px;
  line-height: 1.7;
  border: 1px solid var(--c-border);
  border-radius: var(--radius-md);
  outline: none;
  background: var(--c-bg-elevated);
  transition: border-color .18s ease, box-shadow .18s ease;
}

.composer :deep(textarea:focus) { border-color: var(--c-ai); box-shadow: 0 0 0 3px var(--c-ai-soft); }
.composer-actions { display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 8px; }
.composer-actions > span { font-size: 11px; color: var(--c-text-tertiary); }
.composer .ant-btn { flex-shrink: 0; border-radius: var(--radius-md); }
.composer-note { margin: -6px 24px 16px; color: var(--c-text-tertiary); font-size: 11px; }
button:focus-visible, :deep(textarea:focus-visible), summary:focus-visible { outline: 2px solid var(--c-ai); outline-offset: 2px; }
.message-tool-chain > summary { cursor: pointer; font-size: 11px; color: var(--c-text-tertiary); }
.message-tool-chain[open] > summary { margin-bottom: 6px; }

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
