<template>
  <a-popover
    v-model:open="open"
    :trigger="disabled ? [] : 'click'"
    :placement="placement"
    overlay-class-name="atp-template-picker-overlay"
  >
    <template #content>
      <div
        class="tpl-picker"
        :style="{ width: `${width}px` }"
        @click.stop
      >
        <div v-if="title || showSearchBar" class="tpl-picker-header">
          <div v-if="title" class="tpl-picker-header-top">
            <span class="tpl-picker-header-title">{{ title }}</span>
            <span class="tpl-picker-count">{{ filteredItems.length }}</span>
          </div>
          <div v-if="showSearchBar" class="tpl-picker-search-wrap">
            <input
              v-model="keyword"
              type="text"
              class="tpl-picker-search"
              :placeholder="resolvedSearchPlaceholder"
            />
            <span v-if="!title" class="tpl-picker-count">{{ filteredItems.length }}</span>
          </div>
        </div>

        <div v-if="groups.length >= 2" class="tpl-picker-tabs">
          <button
            type="button"
            class="tpl-picker-tab"
            :class="{ 'is-active': activeGroup === '__all__' }"
            @click="activeGroup = '__all__'"
          >
            {{ t('smart_json.picker_all_groups') }}
          </button>
          <button
            v-for="groupName in groups"
            :key="groupName"
            type="button"
            class="tpl-picker-tab"
            :class="{ 'is-active': activeGroup === groupName }"
            @click="activeGroup = groupName"
          >
            {{ groupName }}
          </button>
        </div>

        <div class="tpl-picker-list" :style="{ maxHeight: `${maxHeight}px` }">
          <div v-if="!filteredItems.length" class="tpl-picker-empty">
            {{ t('smart_json.picker_empty') }}
          </div>
          <button
            v-for="item in filteredItems"
            :key="item.id"
            type="button"
            class="tpl-picker-row"
            @click="handleSelect(item)"
          >
            <div class="tpl-picker-row-head">
              <span class="tpl-picker-title" :title="item.label">{{ item.label }}</span>
              <span class="tpl-picker-row-meta">
                <span
                  v-if="item.badge"
                  class="tpl-picker-badge"
                  :class="`tone-${item.badgeTone || 'neutral'}`"
                >
                  {{ item.badge }}
                </span>
                <span
                  v-if="item.deletable"
                  role="button"
                  tabindex="0"
                  class="tpl-picker-del"
                  @click.stop="handleDelete(item.id)"
                  @keydown.enter.stop.prevent="handleDelete(item.id)"
                >
                  ×
                </span>
              </span>
            </div>
            <div v-if="item.description" class="tpl-picker-desc" :title="item.description">
              {{ item.description }}
            </div>
            <code v-if="item.preview" class="tpl-picker-code" :title="item.preview">
              {{ item.preview }}
            </code>
          </button>
        </div>

        <div v-if="footerActionLabel" class="tpl-picker-footer">
          <button
            type="button"
            class="tpl-picker-footer-btn"
            @click="handleFooterAction"
          >
            {{ footerActionLabel }}
          </button>
        </div>
      </div>
    </template>

    <slot />
  </a-popover>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import type { TemplatePickerItem } from '@/utils/templatePickerItems'

export type { TemplatePickerItem }

const props = withDefaults(
  defineProps<{
    items: readonly TemplatePickerItem[]
    title?: string
    searchPlaceholder?: string
    width?: number
    maxHeight?: number
    placement?: 'bottomLeft' | 'bottomRight' | 'bottom' | 'topLeft' | 'topRight'
    disabled?: boolean
    searchable?: boolean
    footerActionLabel?: string
  }>(),
  {
    title: '',
    searchPlaceholder: '',
    width: 360,
    maxHeight: 296,
    placement: 'bottomRight',
    disabled: false,
    searchable: undefined,
    footerActionLabel: '',
  },
)

const emit = defineEmits<{
  select: [item: TemplatePickerItem]
  delete: [id: string]
  'footer-action': []
}>()

const { t } = useI18n()
const open = ref(false)
const keyword = ref('')
const activeGroup = ref('__all__')

const resolvedSearchPlaceholder = computed(
  () => props.searchPlaceholder || t('smart_json.picker_search_placeholder'),
)

const showSearchBar = computed(() => {
  if (props.searchable !== undefined) return props.searchable
  return props.items.length >= 6
})

const groups = computed(() => {
  const seen: string[] = []
  for (const item of props.items) {
    if (item.group && !seen.includes(item.group)) {
      seen.push(item.group)
    }
  }
  return seen
})

const filteredItems = computed(() => {
  const kw = keyword.value.trim().toLowerCase()
  return props.items.filter((item) => {
    if (activeGroup.value !== '__all__' && item.group !== activeGroup.value) {
      return false
    }
    if (!kw) return true
    return (
      item.label.toLowerCase().includes(kw) ||
      (item.preview && item.preview.toLowerCase().includes(kw)) ||
      (item.description && item.description.toLowerCase().includes(kw)) ||
      (item.badge && item.badge.toLowerCase().includes(kw))
    )
  })
})

watch(groups, (nextGroups) => {
  if (activeGroup.value !== '__all__' && !nextGroups.includes(activeGroup.value)) {
    activeGroup.value = '__all__'
  }
})

watch(open, (nextOpen) => {
  if (nextOpen && props.disabled) {
    open.value = false
    return
  }
  if (!nextOpen) {
    keyword.value = ''
    activeGroup.value = '__all__'
  }
})

function handleSelect(item: TemplatePickerItem) {
  open.value = false
  emit('select', item)
}

function handleDelete(id: string) {
  emit('delete', id)
}

function handleFooterAction() {
  open.value = false
  emit('footer-action')
}
</script>

<style>
.tpl-picker {
  max-width: calc(100vw - 24px);
  display: flex;
  flex-direction: column;
  color: var(--c-text);
  background: var(--c-bg-elevated);
}

.tpl-picker-header {
  padding: 8px 10px;
  border-bottom: 1px solid var(--c-border-subtle);
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.tpl-picker-header-top {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}

.tpl-picker-header-title {
  font-size: 12px;
  font-weight: 600;
  color: var(--c-text);
}

.tpl-picker-search-wrap {
  display: flex;
  align-items: center;
  gap: 6px;
}

.tpl-picker-search {
  flex: 1;
  min-width: 0;
  height: 28px;
  padding: 0 9px;
  border: 1px solid var(--c-border);
  border-radius: var(--radius-sm);
  background: var(--c-bg-subtle);
  color: var(--c-text);
  font-size: 12px;
  outline: none;
  transition: border-color 0.15s ease, background-color 0.15s ease;
}

.tpl-picker-search:focus {
  border-color: var(--c-primary);
  background: var(--c-bg-elevated);
}

.tpl-picker-count {
  flex-shrink: 0;
  min-width: 22px;
  height: 20px;
  padding: 0 6px;
  border-radius: var(--radius-full);
  background: var(--c-bg-subtle);
  color: var(--c-text-secondary);
  font-size: 11px;
  font-weight: 600;
  display: inline-flex;
  align-items: center;
  justify-content: center;
}

.tpl-picker-tabs {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 6px 10px;
  border-bottom: 1px solid var(--c-border-subtle);
  overflow-x: auto;
  scrollbar-width: none;
}

.tpl-picker-tabs::-webkit-scrollbar {
  display: none;
}

.tpl-picker-tab {
  flex-shrink: 0;
  padding: 2px 9px;
  height: 22px;
  border: 1px solid transparent;
  border-radius: var(--radius-full);
  background: var(--c-bg-subtle);
  color: var(--c-text-secondary);
  font-size: 11px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.15s ease;
}

.tpl-picker-tab:hover {
  color: var(--c-text);
  border-color: var(--c-border-strong);
}

.tpl-picker-tab.is-active {
  background: var(--c-primary-soft);
  color: var(--c-primary);
  border-color: transparent;
  font-weight: 600;
}

.tpl-picker-list {
  overflow-y: auto;
  overscroll-behavior: contain;
  padding: 6px;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.tpl-picker-empty {
  padding: 22px 12px;
  text-align: center;
  color: var(--c-text-tertiary);
  font-size: 12px;
}

.tpl-picker-row {
  width: 100%;
  text-align: left;
  padding: 7px 9px;
  border: 1px solid transparent;
  border-radius: var(--radius-sm);
  background: transparent;
  display: flex;
  flex-direction: column;
  gap: 4px;
  cursor: pointer;
  transition: background-color 0.12s ease, border-color 0.12s ease;
}

.tpl-picker-row:hover {
  background: var(--c-bg-subtle);
  border-color: var(--c-border);
}

.tpl-picker-row:focus-visible {
  outline: 2px solid var(--c-primary);
  outline-offset: -1px;
}

.tpl-picker-row-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  min-width: 0;
}

.tpl-picker-title {
  flex: 1;
  min-width: 0;
  font-size: 12.5px;
  font-weight: 500;
  color: var(--c-text);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.tpl-picker-row-meta {
  flex-shrink: 0;
  display: inline-flex;
  align-items: center;
  gap: 6px;
}

.tpl-picker-badge {
  padding: 1px 6px;
  border-radius: var(--radius-xs);
  font-size: 10px;
  font-weight: 600;
  font-family: 'JetBrains Mono', Consolas, monospace;
  line-height: 16px;
}

.tpl-picker-badge.tone-neutral {
  background: var(--c-bg-muted);
  color: var(--c-text-secondary);
}

.tpl-picker-badge.tone-primary {
  background: var(--c-primary-soft);
  color: var(--c-primary);
}

.tpl-picker-badge.tone-success {
  background: var(--c-success-soft);
  color: var(--c-success);
}

.tpl-picker-badge.tone-warning {
  background: var(--c-warning-soft);
  color: var(--c-warning);
}

.tpl-picker-badge.tone-danger {
  background: var(--c-error-soft);
  color: var(--c-error);
}

.tpl-picker-del {
  width: 18px;
  height: 18px;
  border-radius: var(--radius-xs);
  color: var(--c-text-tertiary);
  font-size: 14px;
  line-height: 16px;
  text-align: center;
  transition: background-color 0.12s ease, color 0.12s ease;
}

.tpl-picker-del:hover {
  background: var(--c-error-soft);
  color: var(--c-error);
}

.tpl-picker-desc {
  font-size: 11px;
  color: var(--c-text-secondary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.tpl-picker-code {
  display: block;
  max-width: 100%;
  padding: 2px 6px;
  border-radius: var(--radius-xs);
  background: var(--c-bg-subtle);
  color: var(--c-text-secondary);
  font-family: 'JetBrains Mono', Consolas, monospace;
  font-size: 11px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.tpl-picker-row:hover .tpl-picker-code {
  background: var(--c-bg-elevated);
}

.tpl-picker-footer {
  padding: 6px 8px;
  border-top: 1px solid var(--c-border-subtle);
  background: var(--c-bg-subtle);
}

.tpl-picker-footer-btn {
  width: 100%;
  height: 28px;
  border: 1px dashed var(--c-border-strong);
  border-radius: var(--radius-sm);
  background: var(--c-bg-elevated);
  color: var(--c-primary);
  font-size: 12px;
  font-weight: 600;
  cursor: pointer;
  transition: border-color 0.15s ease, background-color 0.15s ease;
}

.tpl-picker-footer-btn:hover {
  border-color: var(--c-primary);
  background: var(--c-primary-soft);
}
</style>
