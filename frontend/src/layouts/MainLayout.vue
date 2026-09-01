<template>
  <a-layout class="app-layout" style="min-height: 100vh">
    <!-- 侧边栏 -->
    <a-layout-sider
      v-model:collapsed="collapsed"
      collapsible
      :trigger="null"
      :width="240"
      :theme="siderTheme"
      class="app-sider"
    >
      <div class="sider-inner">
        <div>
          <div class="brand" :class="{ 'brand-collapsed': collapsed }">
            <div class="brand-logo"><ThunderboltFilled /></div>
            <div v-if="!collapsed" class="brand-text">
              <span class="brand-name">{{ t('layout.sider_title_full') }}</span>
              <span class="brand-tag">PRO</span>
            </div>
          </div>
          <a-menu
            v-model:selectedKeys="selectedKeys"
            v-model:openKeys="openKeys"
            :theme="siderTheme"
            mode="inline"
            class="app-menu"
            @click="onMenuClick"
          >
            <a-sub-menu key="workbench">
              <template #icon><DashboardOutlined /></template>
              <template #title>{{ t('menu.groups.workbench') }}</template>
              <a-menu-item key="/dashboard">{{ t('menu.workbench.home') }}</a-menu-item>
              <a-menu-item key="/workbench/todos">
                <span class="menu-item-with-badge">
                  <span>{{ t('menu.workbench.todos') }}</span>
                  <a-badge v-if="workbenchTodoCount > 0" :count="workbenchTodoCount" :overflow-count="99" />
                </span>
              </a-menu-item>
              <a-menu-item key="/projects">{{ t('menu.workbench.projects') }}</a-menu-item>
              <a-menu-item key="/tasks">
                <span class="menu-item-with-badge">
                  <span>{{ t('menu.workbench.tasks') }}</span>
                  <a-badge v-if="activeTaskCount > 0" :count="activeTaskCount" :overflow-count="99" />
                </span>
              </a-menu-item>
            </a-sub-menu>

            <a-sub-menu key="test-capabilities">
              <template #icon><PlayCircleOutlined /></template>
              <template #title>{{ t('menu.groups.test_capabilities') }}</template>
              <a-menu-item key="/api-workbench">{{ t('menu.capabilities.api') }}</a-menu-item>
              <a-menu-item v-if="canAccess(['admin', 'engineer'])" key="/mobile-special/workbench">{{ t('menu.capabilities.app') }}</a-menu-item>
              <a-menu-item key="/ui-workbench">{{ t('menu.capabilities.ui') }}</a-menu-item>
              <a-menu-item key="/performance-workbench">{{ t('menu.capabilities.performance') }}</a-menu-item>
              <a-menu-item key="/ai-workbench">{{ t('menu.capabilities.ai') }}</a-menu-item>
            </a-sub-menu>

            <a-sub-menu key="test-assets">
              <template #icon><AppstoreOutlined /></template>
              <template #title>{{ t('menu.groups.test_assets_new') }}</template>
              <a-menu-item key="/cases">{{ t('menu.assets.cases') }}</a-menu-item>
              <a-menu-item key="/suites">{{ t('menu.assets.suites') }}</a-menu-item>
              <a-menu-item key="/plans">{{ t('menu.assets.plans') }}</a-menu-item>
              <a-menu-item key="/bugs">{{ t('menu.assets.bugs') }}</a-menu-item>
              <a-menu-item key="/reports">{{ t('menu.assets.reports') }}</a-menu-item>
              <a-menu-item key="/case-reviews">{{ t('menu.assets.reviews') }}</a-menu-item>
            </a-sub-menu>

            <a-sub-menu key="intelligence-center">
              <template #icon><ApiOutlined /></template>
              <template #title>{{ t('menu.groups.intelligence_center') }}</template>
              <a-menu-item key="/hermes">{{ t('menu.intelligence.hermes') }}</a-menu-item>
              <a-menu-item key="/requirements">{{ t('menu.intelligence.requirements') }}</a-menu-item>
              <a-menu-item key="/knowledge">{{ t('menu.intelligence.knowledge') }}</a-menu-item>
            </a-sub-menu>

            <a-sub-menu v-if="canAccess(['admin', 'engineer'])" key="system-center">
              <template #icon><SettingOutlined /></template>
              <template #title>{{ t('menu.groups.system_center') }}</template>
              <a-menu-item v-if="canAccess(['admin', 'engineer'])" key="/system/toolbox">{{ t('menu.system_center.toolbox') }}</a-menu-item>
              <a-menu-item v-if="canAccess(['admin', 'engineer'])" key="/system/config">{{ t('menu.system_center.config') }}</a-menu-item>
            </a-sub-menu>
          </a-menu>
        </div>

        <!-- 侧边栏底部 Web 录制 Worker 状态 -->
        <div v-if="!collapsed" class="sider-footer">
          <div class="worker-status-card">
            <div class="worker-status-header">
              <span class="worker-indicator">
                <span :class="['status-dot', `status-dot-${workerState}`]"></span>
                {{ t('layout.worker.title') }}
              </span>
              <span :class="['worker-badge', `worker-badge-${workerState}`]">
                {{ t(`layout.worker.states.${workerState}`) }}
              </span>
            </div>
            <div class="worker-progress">
              <div class="worker-progress-bar" :style="{ width: `${workerAvailabilityPercent}%` }"></div>
            </div>
            <div class="worker-meta">
              <span>{{ workerNodeSummary }}</span>
              <span>{{ t('layout.worker.queue', { count: activeTaskCount }) }}</span>
            </div>
          </div>
        </div>
      </div>
    </a-layout-sider>

    <a-layout>
      <!-- 顶栏 -->
      <a-layout-header class="app-header">
        <div class="header-left">
          <a-button type="text" class="collapse-btn" @click="collapsed = !collapsed">
            <MenuUnfoldOutlined v-if="collapsed" />
            <MenuFoldOutlined v-else />
          </a-button>
          <a-breadcrumb class="header-breadcrumb">
            <a-breadcrumb-item v-for="key in breadcrumbKeys" :key="key">{{ t(key) }}</a-breadcrumb-item>
          </a-breadcrumb>
          <span v-if="activeProjectId" class="project-context">
            <span class="context-dot"></span>
            {{ t('layout.project_context', { id: activeProjectId }) }}
          </span>
        </div>

        <!-- 顶部搜索与全局指令面板触发器 -->
        <div class="header-center">
          <button type="button" class="quick-search-trigger" @click="openQuickSearch">
            <SearchOutlined class="search-icon" />
            <span class="search-placeholder">{{ t('layout.quick_search.trigger') }}</span>
            <span class="search-kbd">⌘ K</span>
          </button>
        </div>

        <div class="header-right">
          <a-tooltip :title="t('layout.theme_toggle')">
            <a-button type="text" class="icon-btn" @click="themeStore.toggle()">
              <BulbFilled v-if="isDark" />
              <BulbOutlined v-else />
            </a-button>
          </a-tooltip>
          <a-select
            :value="currentLocale"
            size="small"
            style="width: 104px"
            :options="localeOptions"
            @change="onLocaleChange"
          />
          <a-dropdown placement="bottomRight">
            <div class="user-chip">
              <a-avatar size="small" class="user-avatar">{{ userInitial }}</a-avatar>
              <div class="user-details">
                <span class="user-name">{{ auth.user?.username }}</span>
                <span class="user-role">{{ auth.user?.role || t('layout.role_engineer') }}</span>
              </div>
              <DownOutlined class="user-caret" />
            </div>
            <template #overlay>
              <a-menu>
                <a-menu-item key="account" @click="router.push('/account')">
                  <UserOutlined />
                  <span>{{ t('account.menu') }}</span>
                </a-menu-item>
                <a-menu-item v-if="canAccess(['admin'])" key="users" @click="router.push('/system/users')">
                  <UserOutlined />
                  <span>{{ t('menu.system.users') }}</span>
                </a-menu-item>
                <a-menu-item key="logout" @click="handleLogout">
                  <LogoutOutlined />
                  <span>{{ t('common.logout') }}</span>
                </a-menu-item>
              </a-menu>
            </template>
          </a-dropdown>
        </div>
      </a-layout-header>

      <!-- 内容区 -->
      <a-layout-content class="app-content">
        <div class="content-card">
          <RouterView />
        </div>
      </a-layout-content>
    </a-layout>

    <!-- 快捷指令模态框 -->
    <a-modal
      v-model:open="quickSearchOpen"
      :footer="null"
      :closable="false"
      width="560px"
      class="quick-search-modal"
    >
      <div class="quick-search-box">
        <div class="quick-search-input-wrap">
          <SearchOutlined class="quick-search-icon" />
          <a-input
            ref="quickSearchInputRef"
            v-model:value="searchQuery"
            :placeholder="t('layout.quick_search.input_placeholder')"
            :bordered="false"
            class="quick-search-input"
            @press-enter="executeSearch"
          />
          <button type="button" class="quick-search-esc" @click="quickSearchOpen = false">ESC</button>
        </div>
        <div class="quick-nav-section">
          <div class="quick-nav-title">{{ t('layout.quick_search.section_title') }}</div>
          <div class="quick-nav-list">
            <button type="button" class="quick-nav-item" @click="navTo('/dashboard')">
              <DashboardOutlined />
              <span>{{ t('layout.quick_search.pages.dashboard') }}</span>
              <span class="quick-nav-hint">{{ t('layout.quick_search.hints.overview') }}</span>
            </button>
            <button type="button" class="quick-nav-item" @click="navTo('/api-workbench')">
              <ApiOutlined />
              <span>{{ t('layout.quick_search.pages.api_workbench') }}</span>
              <span class="quick-nav-hint">{{ t('layout.quick_search.hints.api_runner') }}</span>
            </button>
            <button type="button" class="quick-nav-item" @click="navTo('/cases')">
              <AppstoreOutlined />
              <span>{{ t('layout.quick_search.pages.cases') }}</span>
              <span class="quick-nav-hint">{{ t('layout.quick_search.hints.cases') }}</span>
            </button>
            <button type="button" class="quick-nav-item" @click="navTo('/hermes')">
              <ThunderboltFilled style="color: var(--c-ai);" />
              <span>{{ t('layout.quick_search.pages.hermes') }}</span>
              <span class="quick-nav-hint">{{ t('layout.quick_search.hints.ai_copilot') }}</span>
            </button>
          </div>
        </div>
      </div>
    </a-modal>
  </a-layout>
</template>

<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useI18n } from 'vue-i18n'
import {
  PlayCircleOutlined,
  SettingOutlined,
  AppstoreOutlined,
  DashboardOutlined,
  ApiOutlined,
  MenuFoldOutlined,
  MenuUnfoldOutlined,
  BulbOutlined,
  BulbFilled,
  DownOutlined,
  LogoutOutlined,
  UserOutlined,
  ThunderboltFilled,
  SearchOutlined,
} from '@ant-design/icons-vue'
import { useAuthStore } from '@/stores/auth'
import { useThemeStore } from '@/stores/theme'
import { getLocale, setLocale, type SupportedLocale } from '@/locales'
import { hasAnyRole, type UserRole } from '@/utils/permissions'
import { webRecordingApi, workbenchApi, type WebRecordingWorkersResponse } from '@/api'
import {
  getBreadcrumbKeys,
  getMenuOpenKeys,
  getRouteTitleKey,
  getSelectedMenuKey,
} from './navigation'

const router = useRouter()
const route = useRoute()
const auth = useAuthStore()
const themeStore = useThemeStore()
const { t } = useI18n()

const workbenchTodoCount = ref(0)
const activeTaskCount = ref(0)
const workerStatus = ref<WebRecordingWorkersResponse | null>(null)
const workerStatusLoading = ref(true)
let workbenchRefreshTimer: number | undefined

const collapsed = ref(false)

const selectedKeys = ref([getSelectedMenuKey(route.path)])
const openKeys = ref<string[]>(getMenuOpenKeys(route.path))

// 快捷搜索状态
const quickSearchOpen = ref(false)
const searchQuery = ref('')
const quickSearchInputRef = ref()

type WorkerState = 'checking' | 'ready' | 'degraded' | 'unavailable' | 'local'

const workerState = computed<WorkerState>(() => {
  const status = workerStatus.value
  if (!status) return workerStatusLoading.value ? 'checking' : 'unavailable'
  if (status.mode !== 'worker') return 'local'
  if (status.ready && status.available_count > 0) return 'ready'
  if (status.registered_count > 0) return 'degraded'
  return 'unavailable'
})

const workerAvailabilityPercent = computed(() => {
  const status = workerStatus.value
  if (!status) return 0
  if (status.mode !== 'worker') return 100
  if (!status.registered_count) return 0
  return Math.round(Math.min(status.available_count / status.registered_count, 1) * 100)
})

const workerNodeSummary = computed(() => {
  const status = workerStatus.value
  if (!status) return t('layout.worker.checking_detail')
  if (status.mode !== 'worker') return t('layout.worker.local_mode')
  return t('layout.worker.nodes', {
    available: status.available_count,
    registered: status.registered_count,
  })
})

function openQuickSearch() {
  quickSearchOpen.value = true
  nextTick(() => {
    quickSearchInputRef.value?.focus?.()
  })
}

function navTo(path: string) {
  quickSearchOpen.value = false
  router.push(path)
}

function executeSearch() {
  const keyword = searchQuery.value.trim()
  if (keyword) {
    quickSearchOpen.value = false
    const query: Record<string, string> = { keyword }
    const projectId = queryProjectId(route.query.project_id)
    if (projectId) query.project_id = String(projectId)
    void router.push({ path: '/cases', query })
  }
}

// 键盘监听 ⌘+K / Ctrl+K
function onGlobalKeydown(e: KeyboardEvent) {
  if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
    e.preventDefault()
    quickSearchOpen.value = !quickSearchOpen.value
    if (quickSearchOpen.value) {
      nextTick(() => quickSearchInputRef.value?.focus?.())
    }
  }
}

watch(() => route.path, (path) => {
  selectedKeys.value = [getSelectedMenuKey(path)]
  openKeys.value = getMenuOpenKeys(path)
})

function queryProjectId(value: unknown) {
  const raw = Array.isArray(value) ? value[0] : value
  const parsed = Number(raw)
  return Number.isInteger(parsed) && parsed > 0 ? parsed : undefined
}

async function refreshWorkbenchSummary() {
  try {
    const summary = await workbenchApi.overview({
      project_id: queryProjectId(route.query.project_id),
      todo_limit: 1,
      task_limit: 1,
    })
    workbenchTodoCount.value = summary.counts.total_todos ?? 0
    activeTaskCount.value = summary.counts.active_tasks ?? 0
  } catch {
    // 侧栏徽标是辅助信息，聚合接口失败时不打断当前页面。
    workbenchTodoCount.value = 0
    activeTaskCount.value = 0
  }
}

async function refreshWorkerStatus() {
  workerStatusLoading.value = true
  try {
    workerStatus.value = await webRecordingApi.workers()
  } catch {
    workerStatus.value = null
  } finally {
    workerStatusLoading.value = false
  }
}

watch(() => route.query.project_id, () => {
  void refreshWorkbenchSummary()
})

onMounted(() => {
  if (window.matchMedia('(max-width: 768px)').matches) {
    collapsed.value = true
  }
  void refreshWorkbenchSummary()
  void refreshWorkerStatus()
  workbenchRefreshTimer = window.setInterval(() => {
    void refreshWorkbenchSummary()
    void refreshWorkerStatus()
  }, 30_000)
  window.addEventListener('keydown', onGlobalKeydown)
})

onBeforeUnmount(() => {
  if (workbenchRefreshTimer !== undefined) window.clearInterval(workbenchRefreshTimer)
  window.removeEventListener('keydown', onGlobalKeydown)
})

const isDark = computed(() => themeStore.mode === 'dark')
const siderTheme = computed<'light' | 'dark'>(() => (themeStore.mode === 'dark' ? 'dark' : 'light'))
const userInitial = computed(() => (auth.user?.username?.[0] ?? '?').toUpperCase())

function canAccess(roles: UserRole[]) {
  return hasAnyRole(auth.user?.role, roles)
}

const routeTitleKey = computed(() => {
  return getRouteTitleKey(route.path, route.meta.menuTitleKey)
})

const breadcrumbKeys = computed(() => getBreadcrumbKeys(route.path, routeTitleKey.value))

const activeProjectId = computed(() => {
  const projectId = route.query.project_id ?? route.params.projectId
  return projectId ? String(projectId) : ''
})

function onMenuClick({ key }: { key: string | number }) {
  router.push(String(key))
}

async function handleLogout() {
  await auth.logout()
  router.push({ name: 'login' })
}

const currentLocale = computed<SupportedLocale>(() => getLocale())

const localeOptions = computed(() => [
  { label: t('lang.zh'), value: 'zh-CN' },
  { label: t('lang.en'), value: 'en-US' },
])

// a-select @change 的参数类型是 SelectValue；此处选项只会是两个受支持的 locale
function onLocaleChange(value: unknown) {
  setLocale(value as SupportedLocale)
}
</script>

<style scoped>
.app-sider {
  background: var(--c-sider-bg);
  border-right: 1px solid var(--c-sider-border);
  height: 100vh;
  position: sticky;
  top: 0;
  left: 0;
  z-index: 20;
}

.sider-inner {
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  height: 100%;
}

.brand {
  height: 60px;
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 0 18px;
  border-bottom: 1px solid var(--c-border-subtle);
  overflow: hidden;
}
.brand-collapsed {
  padding: 0;
  justify-content: center;
}
.brand-logo {
  width: 32px;
  height: 32px;
  border-radius: 10px;
  background: linear-gradient(135deg, #1677ff 0%, #13c2c2 100%);
  color: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 17px;
  flex-shrink: 0;
  box-shadow: 0 2px 10px rgba(22, 119, 255, 0.24);
}
.brand-text {
  display: flex;
  align-items: center;
  gap: 6px;
}
.brand-name {
  font-size: 15px;
  font-weight: 700;
  white-space: nowrap;
  color: var(--c-text);
  letter-spacing: -0.02em;
}
.brand-tag {
  font-size: 9px;
  font-weight: 700;
  padding: 1px 4px;
  border-radius: 4px;
  background: var(--c-primary-soft);
  color: var(--c-primary);
  border: 1px solid var(--c-primary-glow);
}

.app-menu {
  background: transparent;
  border-inline-end: none !important;
  padding: 10px 8px;
}

.menu-item-with-badge {
  display: inline-flex;
  align-items: center;
  justify-content: space-between;
  width: 100%;
  gap: 8px;
}

.menu-item-with-badge :deep(.ant-badge-count) {
  box-shadow: none;
  font-size: 11px;
}
.app-menu :deep(.ant-menu-item),
.app-menu :deep(.ant-menu-submenu-title) {
  border-radius: var(--radius-sm);
  margin-block: 3px;
  transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1);
}
.app-menu :deep(.ant-menu-submenu > .ant-menu-submenu-title) {
  color: var(--c-text-secondary);
  font-weight: 600;
  font-size: 13px;
}

.app-menu :deep(.ant-menu-item-selected) {
  background-color: var(--c-sider-active-bg) !important;
  color: var(--c-sider-text-active) !important;
  font-weight: 600;
}

/* 侧栏底部 Worker 状态卡片 */
.sider-footer {
  padding: 12px;
  border-top: 1px solid var(--c-border-subtle);
}
.worker-status-card {
  padding: 10px 12px;
  border-radius: var(--radius-md);
  background: var(--c-bg-subtle);
  border: 1px solid var(--c-border);
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.worker-status-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  font-size: 11px;
  font-weight: 600;
  color: var(--c-text-secondary);
}
.worker-indicator {
  display: flex;
  align-items: center;
  gap: 6px;
}
.status-dot {
  width: 6px;
  height: 6px;
  border-radius: 9999px;
  background: var(--c-success);
  box-shadow: 0 0 6px rgba(74, 225, 145, 0.6);
}
.status-dot-checking {
  background: var(--c-warning);
  box-shadow: 0 0 6px var(--c-warning-soft);
}
.status-dot-degraded {
  background: var(--c-warning);
  box-shadow: 0 0 6px var(--c-warning-soft);
}
.status-dot-unavailable {
  background: var(--c-error);
  box-shadow: 0 0 6px var(--c-error-soft);
}
.status-dot-local {
  background: var(--c-info);
  box-shadow: 0 0 6px var(--c-info-soft);
}
.worker-badge {
  font-size: 9px;
  font-weight: 700;
  padding: 1px 5px;
  border-radius: 999px;
  background: var(--c-success-soft);
  color: var(--c-success);
}
.worker-badge-checking,
.worker-badge-degraded {
  background: var(--c-warning-soft);
  color: var(--c-warning);
}
.worker-badge-unavailable {
  background: var(--c-error-soft);
  color: var(--c-error);
}
.worker-badge-local {
  background: var(--c-info-soft);
  color: var(--c-info);
}
.worker-progress {
  width: 100%;
  height: 4px;
  border-radius: 999px;
  background: var(--c-bg-muted);
  overflow: hidden;
}
.worker-progress-bar {
  height: 100%;
  background: linear-gradient(90deg, #1677ff, #13c2c2);
  border-radius: 999px;
}
.worker-meta {
  display: flex;
  justify-content: space-between;
  font-size: 10px;
  color: var(--c-text-tertiary);
  font-family: 'JetBrains Mono', monospace;
}

/* 顶栏 */
.app-header {
  position: sticky;
  top: 0;
  z-index: 15;
  height: 60px;
  padding: 0 20px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  background: var(--c-header-bg);
  backdrop-filter: blur(12px);
  -webkit-backdrop-filter: blur(12px);
  border-bottom: 1px solid var(--c-border);
}
.header-left {
  display: flex;
  align-items: center;
  gap: 12px;
}
.header-breadcrumb {
  min-width: 0;
}
.header-breadcrumb :deep(.ant-breadcrumb-link) {
  color: var(--c-text);
  font-size: 14px;
  font-weight: 600;
}
.project-context {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 3px 10px;
  color: var(--c-primary);
  background: var(--c-primary-soft);
  border: 1px solid var(--c-primary-glow);
  border-radius: var(--radius-full);
  font-size: 12px;
  font-weight: 600;
  white-space: nowrap;
}
.context-dot {
  width: 6px;
  height: 6px;
  border-radius: 9999px;
  background: var(--c-primary);
}
.collapse-btn {
  font-size: 16px;
  color: var(--c-text-secondary);
  border-radius: var(--radius-sm);
}

/* 快捷搜索框 */
.header-center {
  flex: 1;
  max-width: 380px;
  margin: 0 16px;
  min-width: 0;
  display: flex;
}
.quick-search-trigger {
  width: 100%;
  height: 34px;
  padding: 0 12px;
  border-radius: var(--radius-md);
  background: var(--c-bg-subtle);
  border: 1px solid var(--c-border);
  display: flex;
  align-items: center;
  justify-content: space-between;
  cursor: pointer;
  transition: all 0.2s ease;
  font: inherit;
  text-align: left;
}
.quick-search-trigger:hover {
  background: var(--c-bg-elevated);
  border-color: var(--c-primary);
  box-shadow: var(--shadow-sm);
}
.search-icon {
  font-size: 13px;
  color: var(--c-text-tertiary);
  margin-right: 8px;
}
.search-placeholder {
  font-size: 12px;
  color: var(--c-text-tertiary);
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.search-kbd {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  height: 20px;
  min-width: 28px;
  box-sizing: border-box;
  padding: 0 5px;
  font-size: 10px;
  line-height: 1;
  font-family: monospace;
  border-radius: 4px;
  background: transparent;
  border: 1px solid var(--c-border);
  color: var(--c-text-secondary);
  opacity: 0.8;
  white-space: nowrap;
  flex-shrink: 0;
}

.header-right {
  display: flex;
  align-items: center;
  gap: 12px;
}
.icon-btn {
  font-size: 16px;
  color: var(--c-text-secondary);
  border-radius: var(--radius-sm);
}

.user-chip {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 4px 10px 4px 4px;
  border-radius: var(--radius-full);
  border: 1px solid var(--c-border);
  background: var(--c-bg-elevated);
  cursor: pointer;
  transition: all 0.2s ease;
}
.user-chip:hover {
  background: var(--c-bg-subtle);
  border-color: var(--c-border-strong);
}
.user-avatar {
  background: linear-gradient(135deg, #1677ff, #13c2c2);
  color: #fff;
  font-weight: 700;
  font-size: 12px;
}
.user-details {
  display: flex;
  flex-direction: column;
  text-align: left;
  line-height: 1.1;
}
.user-name {
  font-size: 12px;
  font-weight: 600;
  color: var(--c-text);
}
.user-role {
  font-size: 10px;
  color: var(--c-text-tertiary);
}
.user-caret {
  font-size: 10px;
  color: var(--c-text-tertiary);
}

.app-content {
  padding: 20px;
  background: var(--c-bg-body);
  min-height: calc(100vh - 60px);
}
.content-card {
  background: var(--c-bg-elevated);
  border: 1px solid var(--c-border);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-sm);
  padding: 24px;
  min-height: calc(100vh - 100px);
  transition: background-color 0.25s ease, border-color 0.25s ease;
}

/* 快捷搜索模态框 */
.quick-search-box {
  display: flex;
  flex-direction: column;
}
.quick-search-input-wrap {
  display: flex;
  align-items: center;
  padding: 12px 16px;
  border-bottom: 1px solid var(--c-border);
}
.quick-search-icon {
  font-size: 18px;
  color: var(--c-primary);
  margin-right: 12px;
}
.quick-search-input {
  font-size: 14px;
  flex: 1;
}
.quick-search-esc {
  border: 0;
  font: inherit;
  font-size: 11px;
  padding: 2px 6px;
  border-radius: 4px;
  background: var(--c-bg-subtle);
  color: var(--c-text-tertiary);
  cursor: pointer;
}
.quick-nav-section {
  padding: 16px;
}
.quick-nav-title {
  font-size: 11px;
  font-weight: 700;
  text-transform: uppercase;
  color: var(--c-text-tertiary);
  letter-spacing: 0.05em;
  margin-bottom: 10px;
}
.quick-nav-list {
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.quick-nav-item {
  width: 100%;
  border: 0;
  background: transparent;
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 12px;
  border-radius: var(--radius-md);
  font-size: 13px;
  font-weight: 500;
  color: var(--c-text);
  cursor: pointer;
  transition: background 0.15s ease;
  font-family: inherit;
  text-align: left;
}
.quick-nav-item:hover {
  background: var(--c-bg-subtle);
}
.quick-nav-hint {
  margin-left: auto;
  font-size: 11px;
  font-family: monospace;
  color: var(--c-text-tertiary);
}

.quick-search-trigger:focus-visible,
.quick-search-esc:focus-visible,
.quick-nav-item:focus-visible {
  outline: 2px solid var(--c-primary);
  outline-offset: 2px;
}

@media (max-width: 768px) {
  .app-layout,
  .app-layout :deep(.ant-layout) {
    min-width: 0;
  }

  .app-sider {
    position: fixed;
    inset: 0 auto 0 0;
    z-index: 25;
    height: 100vh;
    box-shadow: var(--shadow-lg);
  }

  .app-sider.ant-layout-sider-collapsed {
    transform: translateX(-100%);
    min-width: 240px !important;
    width: 240px !important;
    flex: 0 0 240px !important;
  }

  .app-header {
    height: auto;
    min-height: 56px;
    padding: 10px 12px;
    gap: 8px;
  }

  .header-breadcrumb {
    max-width: 42vw;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .header-center {
    display: none;
  }

  .header-breadcrumb :deep(.ant-breadcrumb-separator) {
    margin-inline: 4px;
  }

  .project-context {
    max-width: 28vw;
    overflow: hidden;
    text-overflow: ellipsis;
  }

  .header-right {
    min-width: 0;
    flex-shrink: 0;
    gap: 4px;
  }

  .header-left {
    min-width: 0;
    flex: 1;
  }

  .header-right .icon-btn {
    width: 32px;
    padding-inline: 0;
  }

  .header-right :deep(.ant-select) {
    width: 76px !important;
  }

  .user-chip {
    padding-right: 4px;
  }

  .user-details,
  .user-caret {
    display: none;
  }

  .app-content {
    padding: 12px;
  }

  .content-card {
    padding: 14px;
    border-radius: var(--radius-md);
    min-height: calc(100vh - 80px);
  }
}
</style>
