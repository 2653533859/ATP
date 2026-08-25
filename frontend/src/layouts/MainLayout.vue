<template>
  <a-layout class="app-layout" style="min-height: 100vh">
    <!-- 侧边栏 -->
    <a-layout-sider
      v-model:collapsed="collapsed"
      collapsible
      :trigger="null"
      :width="232"
      :theme="siderTheme"
      class="app-sider"
    >
      <div class="brand" :class="{ 'brand-collapsed': collapsed }">
        <div class="brand-logo"><ThunderboltFilled /></div>
        <span v-if="!collapsed" class="brand-name">{{ t('layout.sider_title_full') }}</span>
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
          <span v-if="activeProjectId" class="project-context">{{ t('layout.project_context', { id: activeProjectId }) }}</span>
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
              <span class="user-name">{{ auth.user?.username }}</span>
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
  </a-layout>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
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
} from '@ant-design/icons-vue'
import { useAuthStore } from '@/stores/auth'
import { useThemeStore } from '@/stores/theme'
import { getLocale, setLocale, type SupportedLocale } from '@/locales'
import { hasAnyRole, type UserRole } from '@/utils/permissions'
import { workbenchApi } from '@/api'
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
let workbenchRefreshTimer: number | undefined

const collapsed = ref(false)

const selectedKeys = ref([getSelectedMenuKey(route.path)])
const openKeys = ref<string[]>(getMenuOpenKeys(route.path))

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

watch(() => route.query.project_id, () => {
  void refreshWorkbenchSummary()
})

onMounted(() => {
  if (window.matchMedia('(max-width: 768px)').matches) {
    collapsed.value = true
  }
  void refreshWorkbenchSummary()
  workbenchRefreshTimer = window.setInterval(refreshWorkbenchSummary, 30_000)
})

onBeforeUnmount(() => {
  if (workbenchRefreshTimer !== undefined) window.clearInterval(workbenchRefreshTimer)
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
}

.brand {
  height: 64px;
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 0 20px;
  overflow: hidden;
}
.brand-collapsed {
  padding: 0;
  justify-content: center;
}
.brand-logo {
  width: 32px;
  height: 32px;
  border-radius: 9px;
  background: linear-gradient(135deg, #6366f1, #4f46e5);
  color: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 18px;
  flex-shrink: 0;
  box-shadow: 0 2px 8px rgba(79, 70, 229, 0.35);
}
.brand-name {
  font-size: 16px;
  font-weight: 700;
  white-space: nowrap;
  color: var(--c-text);
  letter-spacing: -0.01em;
}

.app-menu {
  background: transparent;
  border-inline-end: none !important;
  padding: 8px;
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
}
.app-menu :deep(.ant-menu-item),
.app-menu :deep(.ant-menu-submenu-title) {
  border-radius: 8px;
}
.app-menu :deep(.ant-menu-submenu > .ant-menu-submenu-title) {
  color: var(--c-text);
  font-weight: 600;
}

.app-header {
  position: sticky;
  top: 0;
  z-index: 9;
  height: 60px;
  padding: 0 20px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  background: var(--c-header-bg);
  backdrop-filter: blur(8px);
  border-bottom: 1px solid var(--c-border);
}
.header-left {
  display: flex;
  align-items: center;
  gap: 8px;
}
.header-breadcrumb {
  min-width: 0;
}
.header-breadcrumb :deep(.ant-breadcrumb-link) {
  color: var(--c-text);
  font-size: 15px;
  font-weight: 600;
}
.project-context {
  padding: 4px 9px;
  color: var(--c-primary);
  background: color-mix(in srgb, var(--c-primary) 10%, transparent);
  border: 1px solid color-mix(in srgb, var(--c-primary) 20%, transparent);
  border-radius: 999px;
  font-size: 12px;
  white-space: nowrap;
}
.collapse-btn {
  font-size: 16px;
  color: var(--c-text-secondary);
}
.header-right {
  display: flex;
  align-items: center;
  gap: 8px;
}
.icon-btn {
  font-size: 16px;
  color: var(--c-text-secondary);
}

.user-chip {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 4px 10px 4px 4px;
  border-radius: 999px;
  cursor: pointer;
  transition: background 0.2s ease;
}
.user-chip:hover {
  background: var(--c-bg-subtle);
}
.user-avatar {
  background: var(--c-primary);
  color: #fff;
  font-weight: 600;
}
.user-name {
  font-size: 14px;
  color: var(--c-text);
}
.user-caret {
  font-size: 10px;
  color: var(--c-text-tertiary);
}

.app-content {
  padding: 20px;
  background: var(--c-bg-body);
}
.content-card {
  background: var(--c-bg-elevated);
  border: 1px solid var(--c-border);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-sm);
  padding: 24px;
  min-height: calc(100vh - 100px);
}

@media (max-width: 768px) {
  .app-layout,
  .app-layout :deep(.ant-layout) {
    min-width: 0;
  }

  .app-sider {
    position: fixed;
    inset: 0 auto 0 0;
    z-index: 20;
    height: 100vh;
    box-shadow: var(--shadow-lg);
  }

  .app-sider.ant-layout-sider-collapsed {
    transform: translateX(-100%);
    min-width: 232px !important;
    width: 232px !important;
    flex: 0 0 232px !important;
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
  }

  .user-name,
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
