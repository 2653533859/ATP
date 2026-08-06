<template>
  <a-modal
    :open="open"
    :title="t('case.drawer.script_preview.title')"
    width="900px"
    :footer="null"
    @cancel="emit('close')"
  >
    <div class="script-preview-meta">
      <a-tag :color="kind === 'web' ? 'blue' : 'purple'">
        {{ kind === 'web' ? 'pytest + Playwright' : 'pytest + uiautomator2' }}
      </a-tag>
      <span>{{ t('case.drawer.script_preview.hint') }}</span>
    </div>

    <MonacoEditor v-model="draft" language="python" height="520px" />

    <div class="script-preview-footer">
      <span class="script-preview-note">
        {{ t('case.drawer.script_preview.save_note') }}
      </span>
      <a-space>
        <a-button @click="emit('close')">{{ t('common.cancel') }}</a-button>
        <a-button type="primary" :loading="saving" :disabled="!draft.trim()" @click="emit('save', draft)">
          {{ t('case.drawer.script_preview.save') }}
        </a-button>
      </a-space>
    </div>
  </a-modal>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import MonacoEditor from './MonacoEditor.vue'

const props = defineProps<{
  open: boolean
  content: string
  kind: 'web' | 'android'
  saving?: boolean
}>()

const emit = defineEmits<{
  close: []
  save: [content: string]
}>()

const { t } = useI18n()
const draft = ref('')

watch(
  () => [props.open, props.content] as const,
  () => {
    if (props.open) draft.value = props.content
  },
  { immediate: true },
)
</script>

<style scoped>
.script-preview-meta {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  margin-bottom: 12px;
  color: #667085;
  font-size: 13px;
  line-height: 1.6;
}

.script-preview-meta :deep(.ant-tag) {
  flex: 0 0 auto;
  margin: 0;
}

.script-preview-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  margin-top: 12px;
}

.script-preview-note {
  color: #98a2b3;
  font-size: 12px;
}

@media (max-width: 720px) {
  .script-preview-footer {
    align-items: flex-start;
    flex-direction: column;
  }
}
</style>
