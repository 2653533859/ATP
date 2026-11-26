<template>
  <div class="tabbed-hub-shell">
    <nav v-if="visibleTabs.length > 1" class="hub-tabbar" role="tablist" :aria-label="t(hubTitleKey)">
      <button
        v-for="tab in visibleTabs"
        :key="tab.path"
        type="button"
        role="tab"
        class="hub-tab-btn"
        :class="{ 'is-active': activeTabPath === tab.path }"
        :aria-selected="activeTabPath === tab.path"
        @click="selectTab(tab.path)"
      >
        <span class="hub-tab-label">{{ t(tab.labelKey) }}</span>
      </button>
    </nav>
    <div class="hub-view-body">
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
import {
  TABBED_HUBS,
  getVisibleHubTabs,
  matchActiveHubTab,
  type HubId,
} from './hubConfig'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()
const { t } = useI18n()
const localMode = computed(() => getRuntimeMode()?.mode === 'local')

const hubId = computed<HubId | undefined>(() => {
  for (let i = route.matched.length - 1; i >= 0; i -= 1) {
    const id = route.matched[i]?.meta?.hubId
    if (typeof id === 'string' && id in TABBED_HUBS) {
      return id as HubId
    }
  }
  return undefined
})

const hubTitleKey = computed(() => (hubId.value ? TABBED_HUBS[hubId.value].titleKey : 'layout.sider_title_full'))

const visibleTabs = computed(() => {
  if (!hubId.value) return []
  return getVisibleHubTabs(hubId.value, {
    role: auth.user?.role,
    localMode: localMode.value,
    supportsFeature,
  })
})

const activeTabPath = computed(() => matchActiveHubTab(visibleTabs.value, route.path))

function selectTab(targetPath: string) {
  if (targetPath === activeTabPath.value) return
  const projectId = projectIdFromQuery(route.query.project_id ?? route.params.projectId)
  const query = projectId ? { project_id: String(projectId) } : undefined
  void router.push(query ? { path: targetPath, query } : { path: targetPath })
}
</script>

<style scoped>
.tabbed-hub-shell {
  display: flex;
  flex-direction: column;
  gap: 14px;
  min-width: 0;
}

.hub-tabbar {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 5px 6px;
  background: var(--c-bg-elevated);
  border: 1px solid var(--c-border);
  border-radius: var(--radius-md);
  box-shadow: var(--shadow-xs);
  overflow-x: auto;
  scrollbar-width: thin;
}

.hub-tab-btn {
  position: relative;
  border: 0;
  background: transparent;
  padding: 7px 14px;
  border-radius: var(--radius-sm);
  font-size: 13px;
  font-weight: 500;
  color: var(--c-text-secondary);
  cursor: pointer;
  white-space: nowrap;
  transition: background 0.15s ease, color 0.15s ease;
  font-family: inherit;
}

.hub-tab-btn:hover {
  color: var(--c-text);
  background: var(--c-bg-subtle);
}

.hub-tab-btn.is-active {
  color: var(--c-primary);
  background: var(--c-primary-soft);
  font-weight: 600;
}

.hub-tab-btn:focus-visible {
  outline: 2px solid var(--c-primary);
  outline-offset: 2px;
}

.hub-view-body {
  min-width: 0;
  flex: 1;
}
</style>
