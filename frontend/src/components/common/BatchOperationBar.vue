<template>
  <div v-if="selectedCount > 0" class="batch-bar">
    <span class="batch-bar-count">{{ t('common.selected_count', { count: selectedCount }) }}</span>
    <a-space>
      <slot />
      <a-button size="small" type="link" @click="emit('cancel')">{{ t('common.cancel_selection') }}</a-button>
    </a-space>
  </div>
</template>

<script setup lang="ts">
import { useI18n } from 'vue-i18n'

defineProps<{
  selectedCount: number
}>()

const emit = defineEmits<{
  (event: 'cancel'): void
}>()

const { t } = useI18n()
</script>

<style scoped>
.batch-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 12px;
  padding: 8px 12px;
  margin-bottom: 12px;
  background: #e6f4ff;
  border: 1px solid #91caff;
  border-radius: 4px;
}

.batch-bar-count {
  color: #1890ff;
  font-weight: 500;
}

@media (max-width: 640px) {
  .batch-bar {
    align-items: flex-start;
    flex-direction: column;
  }

  .batch-bar :deep(.ant-space) {
    width: 100%;
    row-gap: 8px;
    flex-wrap: wrap;
  }
}
</style>
