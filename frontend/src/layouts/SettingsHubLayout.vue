<template>
  <div class="settings-hub-shell">
    <aside class="settings-hub-nav" :aria-label="t('menu.system_center.config')">
      <div v-for="group in visibleGroups" :key="group.titleKey" class="settings-nav-group">
        <div class="settings-nav-group-title">{{ t(group.titleKey) }}</div>
        <button
          v-for="item in group.items"
          :key="item.path"
          type="button"
          class="settings-nav-item"
          :class="{ 'is-active': isItemActive(item.path) }"
          :aria-current="isItemActive(item.path) ? 'page' : undefined"
          @click="selectItem(item.path)"
        >
          <span>{{ t(item.labelKey) }}</span>
        </button>
      </div>
    </aside>

    <div class="settings-hub-main">
      <RouterView />
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { useAuthStore } from '@/stores/auth'
import { getRuntimeMode, supportsFeature } from '@/runtimeMode'
import { projectIdFromQuery } from '@/utils/projectContext'
import { SETTINGS_HUB_GROUPS, isHubItemVisible } from './hubConfig'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()
const { t } = useI18n()
const localMode = computed(() => getRuntimeMode()?.mode === 'local')

const visibleGroups = computed(() => {
  const ctx = {
    role: auth.user?.role,
    localMode: localMode.value,
    supportsFeature,
  }
  return SETTINGS_HUB_GROUPS
    .map((group) => ({
      titleKey: group.titleKey,
      items: group.items.filter((item) => isHubItemVisible(item, ctx)),
    }))
    .filter((group) => group.items.length > 0)
})

function isItemActive(path: string): boolean {
  return route.path === path || route.path.startsWith(`${path}/`)
}

function selectItem(path: string) {
  if (route.path === path) return
  const projectId = projectIdFromQuery(route.query.project_id ?? route.params.projectId)
  const query = projectId ? { project_id: String(projectId) } : undefined
  void router.push(query ? { path, query } : { path })
}
</script>

<style scoped>
.settings-hub-shell {
  display: flex;
  align-items: flex-start;
  gap: 16px;
  min-width: 0;
}

.settings-hub-nav {
  width: 208px;
  flex-shrink: 0;
  padding: 12px 10px;
  background: var(--c-bg-elevated);
  border: 1px solid var(--c-border);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-xs);
  position: sticky;
  top: 76px;
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.settings-nav-group {
  display: flex;
  flex-direction: column;
  gap: 3px;
}

.settings-nav-group-title {
  padding: 2px 10px 4px;
  font-size: 11px;
  font-weight: 600;
  color: var(--c-text-tertiary);
  letter-spacing: 0.02em;
}

.settings-nav-item {
  width: 100%;
  border: 0;
  background: transparent;
  padding: 8px 10px;
  border-radius: var(--radius-sm);
  text-align: left;
  font-size: 13px;
  font-weight: 500;
  color: var(--c-text-secondary);
  cursor: pointer;
  font-family: inherit;
  transition: background 0.15s ease, color 0.15s ease;
}

.settings-nav-item:hover {
  color: var(--c-text);
  background: var(--c-bg-subtle);
}

.settings-nav-item.is-active {
  color: var(--c-primary);
  background: var(--c-primary-soft);
  font-weight: 600;
}

.settings-nav-item:focus-visible {
  outline: 2px solid var(--c-primary);
  outline-offset: 2px;
}

.settings-hub-main {
  flex: 1;
  min-width: 0;
}

@media (max-width: 960px) {
  .settings-hub-shell {
    flex-direction: column;
    gap: 12px;
  }

  .settings-hub-nav {
    width: 100%;
    position: static;
    flex-direction: row;
    align-items: center;
    overflow-x: auto;
    gap: 10px;
    padding: 8px 10px;
  }

  .settings-nav-group {
    flex-direction: row;
    align-items: center;
    gap: 4px;
    flex-shrink: 0;
  }

  .settings-nav-group-title {
    padding: 0 6px;
    white-space: nowrap;
  }

  .settings-nav-item {
    width: auto;
    white-space: nowrap;
    padding: 6px 10px;
  }

  .settings-hub-main {
    width: 100%;
  }
}
</style>
