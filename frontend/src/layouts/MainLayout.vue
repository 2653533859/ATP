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
          <a-menu-item key="/workbench/todos">{{ t('menu.workbench.todos') }}</a-menu-item>
          <a-menu-item key="/projects">{{ t('menu.workbench.projects') }}</a-menu-item>
          <a-menu-item key="/tasks">{{ t('menu.workbench.tasks') }}</a-menu-item>
          <a-menu-item key="/runs">{{ t('menu.runs') }}</a-menu-item>
        </a-sub-menu>

        <a-sub-menu key="test-capabilities">
          <template #icon><PlayCircleOutlined /></template>
          <template #title>{{ t('menu.groups.test_capabilities') }}</template>
          <a-menu-item key="/api-workbench">{{ t('menu.capabilities.api') }}</a-menu-item>
          <a-menu-item v-if="canAccess(['admin', 'engineer'])" key="/mobile-special/workbench">{{ t('menu.capabilities.app') }}</a-menu-item>
          <a-menu-item v-if="canAccess(['admin', 'engineer'])" key="/devices">{{ t('menu.devices') }}</a-menu-item>
          <a-menu-item v-if="canAccess(['admin', 'engineer'])" key="/apks">{{ t('menu.apks') }}</a-menu-item>
          <a-menu-item v-if="canAccess(['admin', 'engineer'])" key="/mobile-special/tasks">{{ t('menu.mobile_special.tasks') }}</a-menu-item>
          <a-menu-item v-if="canAccess(['admin', 'engineer'])" key="/mobile-special/reports">{{ t('menu.mobile_special.reports') }}</a-menu-item>
          <a-menu-item key="/ui-workbench">{{ t('menu.capabilities.ui') }}</a-menu-item>
          <a-menu-item key="/system/performance">{{ t('menu.capabilities.performance') }}</a-menu-item>
          <a-menu-item key="/ai-workbench">{{ t('menu.capabilities.ai') }}</a-menu-item>
        </a-sub-menu>

        <a-sub-menu key="test-assets">
          <template #icon><AppstoreOutlined /></template>
          <template #title>{{ t('menu.groups.test_assets_new') }}</template>
          <a-menu-item key="/cases">{{ t('menu.assets.cases') }}</a-menu-item>
          <a-menu-item key="/plans">{{ t('menu.assets.plans') }}</a-menu-item>
          <a-menu-item key="/bugs">{{ t('menu.assets.bugs') }}</a-menu-item>
          <a-menu-item key="/reports">{{ t('menu.assets.reports') }}</a-menu-item>
          <a-menu-item key="/case-reviews">{{ t('menu.assets.reviews') }}</a-menu-item>
          <a-menu-item key="/suites">{{ t('menu.suites') }}</a-menu-item>
          <a-menu-item key="/mock-rules">{{ t('menu.mock_rules') }}</a-menu-item>
          <a-menu-item key="/system/datasets">{{ t('menu.system.datasets') }}</a-menu-item>
          <a-menu-item key="/system/web-assets">{{ t('menu.system.web_assets') }}</a-menu-item>
          <a-menu-item key="/system/api-contract-assets">{{ t('menu.system.api_contract_assets') }}</a-menu-item>
        </a-sub-menu>

        <a-sub-menu key="intelligence-center">
          <template #icon><ApiOutlined /></template>
          <template #title>{{ t('menu.groups.intelligence_center') }}</template>
          <a-menu-item key="/hermes">{{ t('menu.intelligence.hermes') }}</a-menu-item>
          <a-menu-item key="/requirements">{{ t('menu.intelligence.requirements') }}</a-menu-item>
          <a-menu-item key="/knowledge">{{ t('menu.intelligence.knowledge') }}</a-menu-item>
        </a-sub-menu>

        <a-sub-menu key="system-center">
          <template #icon><SettingOutlined /></template>
          <template #title>{{ t('menu.groups.system_center') }}</template>
          <a-menu-item v-if="canAccess(['admin', 'engineer'])" key="/system/toolbox">{{ t('menu.system_center.toolbox') }}</a-menu-item>
          <a-menu-item key="/system/config">{{ t('menu.system_center.config') }}</a-menu-item>
          <a-menu-item key="/system/environments">{{ t('menu.system.environments') }}</a-menu-item>
          <a-menu-item v-if="canAccess(['admin'])" key="/system/startup-config">{{ t('menu.system.startup_config') }}</a-menu-item>
          <a-menu-item key="/system/global-variables">{{ t('menu.system.global_variables') }}</a-menu-item>
          <a-menu-item v-if="canAccess(['admin'])" key="/system/ai-llm-configs">{{ t('menu.system.ai_llm_configs') }}</a-menu-item>
          <a-menu-item v-if="canAccess(['admin'])" key="/system/healing-examples">{{ t('menu.system.ai_healing_examples') }}</a-menu-item>
          <a-menu-item v-if="canAccess(['admin'])" key="/system/ai-healing-stats">{{ t('menu.system.ai_healing_stats') }}</a-menu-item>
          <a-menu-item v-if="canAccess(['admin', 'engineer'])" key="/system/storage">{{ t('menu.system.storage') }}</a-menu-item>
          <a-menu-item v-if="canAccess(['admin', 'engineer'])" key="/system/notifications">{{ t('menu.system.notifications') }}</a-menu-item>
          <a-menu-item v-if="canAccess(['admin', 'engineer'])" key="/system/bug-trackers">{{ t('menu.system.bug_trackers') }}</a-menu-item>
          <a-menu-item v-if="canAccess(['admin'])" key="/system/users">{{ t('menu.system.users') }}</a-menu-item>
          <a-menu-item v-if="canAccess(['admin'])" key="/system/audit-logs">{{ t('menu.system.audit_logs') }}</a-menu-item>
          <a-menu-item v-if="canAccess(['admin'])" key="/system/run-retention">{{ t('menu.system.run_retention') }}</a-menu-item>
          <a-menu-item v-if="canAccess(['admin'])" key="/system/dashboard-alerts">{{ t('menu.system.dashboard_alerts') }}</a-menu-item>
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
          <span class="header-title">{{ t(routeTitleKey) }}</span>
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
import { computed, onMounted, ref, watch } from 'vue'
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

const router = useRouter()
const route = useRoute()
const auth = useAuthStore()
const themeStore = useThemeStore()
const { t } = useI18n()

const routeMenuGroups: Record<string, string> = {
  '/dashboard': 'workbench',
  '/workbench': 'workbench',
  '/projects': 'workbench',
  '/tasks': 'workbench',
  '/runs': 'workbench',
  '/api-workbench': 'test-capabilities',
  '/mobile-special': 'test-capabilities',
  '/ui-workbench': 'test-capabilities',
  '/ai-workbench': 'test-capabilities',
  '/cases': 'test-assets',
  '/plans': 'test-assets',
  '/bugs': 'test-assets',
  '/reports': 'test-assets',
  '/case-reviews': 'test-assets',
  '/suites': 'test-assets',
  '/mock-rules': 'test-assets',
  '/system/datasets': 'test-assets',
  '/system/web-assets': 'test-assets',
  '/system/api-contract-assets': 'test-assets',
  '/system/performance': 'test-capabilities',
  '/system': 'system-center',
  '/devices': 'test-capabilities',
  '/apks': 'test-capabilities',
}

const systemRouteTitles: Record<string, string> = {
  '/system/environments': 'menu.system.environments',
  '/system/startup-config': 'menu.system.startup_config',
  '/system/global-variables': 'menu.system.global_variables',
  '/system/datasets': 'menu.system.datasets',
  '/system/web-assets': 'menu.system.web_assets',
  '/system/api-contract-assets': 'menu.system.api_contract_assets',
  '/system/ai-llm-configs': 'menu.system.ai_llm_configs',
  '/system/healing-examples': 'menu.system.ai_healing_examples',
  '/system/ai-healing-stats': 'menu.system.ai_healing_stats',
  '/system/performance': 'menu.system.performance',
  '/system/storage': 'menu.system.storage',
  '/system/run-retention': 'menu.system.run_retention',
  '/system/dashboard-alerts': 'menu.system.dashboard_alerts',
  '/system/notifications': 'menu.system.notifications',
  '/system/bug-trackers': 'menu.system.bug_trackers',
  '/system/users': 'menu.system.users',
  '/system/audit-logs': 'menu.system.audit_logs',
}

function findRouteEntry<T>(entries: Record<string, T>, path: string) {
  return Object.entries(entries).find(([prefix]) => path.startsWith(prefix))?.[1]
}

function getMenuOpenKeys(path: string) {
  const group = findRouteEntry(routeMenuGroups, path)
  if (group) return [group]
  return []
}

const collapsed = ref(false)
function getSelectedMenuKey(path: string) {
  if (path.startsWith('/projects/') && path.endsWith('/cases')) return '/cases'
  if (path.startsWith('/projects/')) return '/projects'
  if (path.startsWith('/cases/')) return '/cases'
  if (path.startsWith('/runs/')) return '/runs'
  if (path.startsWith('/mobile-special/reports/')) return '/mobile-special/reports'
  return path
}

const selectedKeys = ref([getSelectedMenuKey(route.path)])
const openKeys = ref<string[]>(getMenuOpenKeys(route.path))

watch(() => route.path, (path) => {
  selectedKeys.value = [getSelectedMenuKey(path)]
  openKeys.value = getMenuOpenKeys(path)
})

onMounted(() => {
  if (window.matchMedia('(max-width: 768px)').matches) {
    collapsed.value = true
  }
})

const isDark = computed(() => themeStore.mode === 'dark')
const siderTheme = computed<'light' | 'dark'>(() => (themeStore.mode === 'dark' ? 'dark' : 'light'))
const userInitial = computed(() => (auth.user?.username?.[0] ?? '?').toUpperCase())

function canAccess(roles: UserRole[]) {
  return hasAnyRole(auth.user?.role, roles)
}

const routeTitleKey = computed(() => {
  if (route.meta.menuTitleKey) return String(route.meta.menuTitleKey)
  const p = route.path
  if (p.startsWith('/dashboard')) return 'menu.dashboard'
  if (p.startsWith('/projects')) return 'menu.projects'
  if (p.startsWith('/account')) return 'account.title'
  if (p.startsWith('/cases')) return 'menu.cases'
  if (p.startsWith('/runs')) return 'menu.runs'
  if (p.startsWith('/suites')) return 'menu.suites'
  if (p.startsWith('/plans')) return 'menu.plans'
  if (p.startsWith('/devices')) return 'menu.devices'
  if (p.startsWith('/apks')) return 'menu.apks'
  if (p.startsWith('/mock')) return 'menu.mock_rules'
  if (p.startsWith('/mobile-special')) return 'menu.mobile_special.title'
  if (p.startsWith('/system')) return findRouteEntry(systemRouteTitles, p) ?? 'menu.system.title'
  return 'layout.sider_title_full'
})

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
.header-title {
  font-size: 15px;
  font-weight: 600;
  color: var(--c-text);
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

  .header-title {
    max-width: 42vw;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
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
