<template>
  <a-modal
    :open="open"
    :title="t('case.drawer.web.recorder.ai_assert_title')"
    :width="640"
    :confirm-loading="loading"
    :ok-text="t('case.drawer.web.recorder.ai_assert_apply')"
    :cancel-text="t('common.cancel')"
    :ok-button-props="{ disabled: loading || !selectedIndexes.length }"
    @ok="handleApply"
    @cancel="emit('close')"
  >
    <div v-if="loading" class="suggest-loading">
      <a-spin />
      <span>{{ t('case.drawer.web.recorder.ai_assert_loading') }}</span>
    </div>

    <template v-else>
      <div v-if="suggestions.length" class="suggest-header">
        <a-tag :color="source === 'llm' ? 'purple' : 'blue'">
          {{
            source === 'llm'
              ? t('case.drawer.web.recorder.ai_assert_source_llm')
              : t('case.drawer.web.recorder.ai_assert_source_heuristic')
          }}
        </a-tag>
      </div>

      <a-empty
        v-if="!suggestions.length"
        :description="t('case.drawer.web.recorder.ai_assert_empty')"
        style="margin: 24px 0"
      />

      <div v-else class="suggest-list">
        <div
          v-for="(item, index) in suggestions"
          :key="`${item.action}-${index}`"
          class="suggest-item"
          :class="{ selected: selectedIndexes.includes(index) }"
          @click="toggleSelection(index)"
        >
          <a-checkbox
            :checked="selectedIndexes.includes(index)"
            @click.stop
            @change="toggleSelection(index)"
          />
          <div class="suggest-item-body">
            <div class="suggest-item-top">
              <a-tag :color="item.action === 'assert_text' ? 'green' : 'cyan'">
                {{
                  item.action === 'assert_text'
                    ? t('case.drawer.web.recorder.ai_assert_type_text')
                    : t('case.drawer.web.recorder.ai_assert_type_visible')
                }}
              </a-tag>
              <strong class="suggest-item-name">{{ item.name }}</strong>
            </div>
            <div class="suggest-item-target">
              <code>{{ formatTarget(item) }}</code>
            </div>
            <div v-if="item.reason" class="suggest-item-reason">{{ item.reason }}</div>
          </div>
        </div>
      </div>
    </template>
  </a-modal>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'
import { message } from 'ant-design-vue'
import { useI18n } from 'vue-i18n'
import type { WebAssertionSuggestionItem } from '@/api'

const props = defineProps<{
  open: boolean
  loading: boolean
  source: 'llm' | 'heuristic'
  suggestions: WebAssertionSuggestionItem[]
}>()

const emit = defineEmits<{
  close: []
  apply: [items: WebAssertionSuggestionItem[]]
}>()

const { t } = useI18n()
const selectedIndexes = ref<number[]>([])

watch(
  () => [props.open, props.suggestions] as const,
  ([open, items]) => {
    if (open) {
      selectedIndexes.value = items.map((_, idx) => idx)
    }
  },
  { immediate: true },
)

function toggleSelection(index: number) {
  if (selectedIndexes.value.includes(index)) {
    selectedIndexes.value = selectedIndexes.value.filter((i) => i !== index)
  } else {
    selectedIndexes.value = [...selectedIndexes.value, index].sort((a, b) => a - b)
  }
}

function formatTarget(item: WebAssertionSuggestionItem): string {
  if (item.action === 'assert_text') {
    return `text = ${String(item.params?.text || '')}`
  }
  return `selector = ${String(item.params?.selector || '')}`
}

function handleApply() {
  const picked = selectedIndexes.value
    .map((idx) => props.suggestions[idx])
    .filter((item): item is WebAssertionSuggestionItem => Boolean(item))
  if (!picked.length) {
    message.warning(t('case.drawer.web.recorder.ai_assert_select_one'))
    return
  }
  emit('apply', picked)
}
</script>

<style scoped>
.suggest-loading {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 10px;
  padding: 32px 0;
  color: #64748b;
}

.suggest-header {
  margin-bottom: 12px;
}

.suggest-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
  max-height: 380px;
  overflow-y: auto;
}

.suggest-item {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  padding: 10px 12px;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  cursor: pointer;
  transition: border-color 0.15s ease, background-color 0.15s ease;
}

.suggest-item.selected {
  border-color: #6366f1;
  background: #f5f3ff;
}

.suggest-item-body {
  flex: 1;
  min-width: 0;
}

.suggest-item-top {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-bottom: 4px;
}

.suggest-item-name {
  font-size: 13px;
  color: #1e293b;
}

.suggest-item-target {
  font-size: 12px;
  color: #334155;
  margin-bottom: 4px;
  word-break: break-all;
}

.suggest-item-reason {
  font-size: 12px;
  color: #64748b;
}
</style>
