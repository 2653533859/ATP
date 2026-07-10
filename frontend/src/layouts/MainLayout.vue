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
        :theme="siderTheme"
        mode="inline"
        class="app-menu"
        @click="onMenuClick"
      >
        <a-menu-item key="/dashboard">
          <DashboardOutlined />
          <span>{{ t('menu.dashboard') }}</span>
        </a-menu-item>
        <a-menu-item key="/projects">
          <ProjectOutlined />
          <span>{{ t('menu.projects') }}</span>
        </a-menu-item>
        <a-menu-item key="/cases">
          <ProfileOutlined />
          <span>{{ t('menu.cases') }}</span>
        </a-menu-item>
        <a-menu-item key="/runs">
          <PlayCircleOutlined />
          <span>{{ t('menu.runs') }}</span>
        </a-menu-item>
        <a-menu-item key="/suites">
          <AppstoreOutlined />
          <span>{{ t('menu.suites') }}</span>
        </a-menu-item>
        <a-menu-item key="/plans">
          <ClockCircleOutlined />
          <span>{{ t('menu.plans') }}</span>
        </a-menu-item>
        <a-menu-item v-if="canAccess(['admin', 'engineer'])" key="/devices">
          <MobileOutlined />
          <span>{{ t('menu.devices') }}</span>
        </a-menu-item>
        <a-menu-item v-if="canAccess(['admin', 'engineer'])" key="/apks">
          <AndroidOutlined />
          <span>{{ t('menu.apks') }}</span>
        </a-menu-item>
        <a-menu-item key="/mock-rules">
          <ApiOutlined />
          <span>{{ t('menu.mock_rules') }}</span>
        </a-menu-item>
        <a-sub-menu key="mobile-special">
          <template #icon><MobileOutlined /></template>
          <template #title>{{ t('menu.mobile_special.title') }}</template>
          <a-menu-item key="/mobile-special/tasks">{{ t('menu.mobile_special.tasks') }}</a-menu-item>
          <a-menu-item key="/mobile-special/reports">{{ t('menu.mobile_special.reports') }}</a-menu-item>
        </a-sub-menu>
        <a-sub-menu key="system">
          <template #icon><SettingOutlined /></template>
          <template #title>{{ t('menu.system.title') }}</template>
          <a-menu-item key="/system/environments">{{ t('menu.system.environments') }}</a-menu-item>
          <a-menu-item v-if="canAccess(['admin', 'engineer'])" key="/system/notifications">{{ t('menu.system.notifications') }}</a-menu-item>
          <a-menu-item v-if="canAccess(['admin', 'engineer'])" key="/system/bug-trackers">{{ t('menu.system.bug_trackers') }}</a-menu-item>
          <a-menu-item v-if="canAccess(['admin', 'engineer'])" key="/system/storage">{{ t('menu.system.storage') }}</a-menu-item>
          <a-menu-item key="/system/global-variables">{{ t('menu.system.global_variables') }}</a-menu-item>
          <a-menu-item v-if="canAccess(['admin'])" key="/system/ai-llm-configs">{{ t('menu.system.ai_llm_configs') }}</a-menu-item>
          <a-menu-item v-if="canAccess(['admin'])" key="/system/healing-examples">AI 自愈示例</a-menu-item>
          <a-menu-item v-if="canAccess(['admin'])" key="/system/ai-healing-stats">AI 自愈报表</a-menu-item>
          <a-menu-item key="/system/datasets">{{ t('menu.system.datasets') }}</a-menu-item>
          <a-menu-item key="/system/performance">{{ t('menu.system.performance') }}</a-menu-item>
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
  ProjectOutlined,
  ProfileOutlined,
  PlayCircleOutlined,
  SettingOutlined,
  MobileOutlined,
  AndroidOutlined,
  AppstoreOutlined,
  ClockCircleOutlined,
  DashboardOutlined,
  ApiOutlined,
  MenuFoldOutlined,
  MenuUnfoldOutlined,
  BulbOutlined,
  BulbFilled,
  DownOutlined,
  LogoutOutlined,
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

const collapsed = ref(false)
const selectedKeys = ref([route.path])

watch(() => route.path, (path) => { selectedKeys.value = [path] })

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
  const p = route.path
  if (p.startsWith('/dashboard')) return 'menu.dashboard'
  if (p.startsWith('/projects')) return 'menu.projects'
  if (p.startsWith('/cases')) return 'menu.cases'
  if (p.startsWith('/runs')) return 'menu.runs'
  if (p.startsWith('/suites')) return 'menu.suites'
  if (p.startsWith('/plans')) return 'menu.plans'
  if (p.startsWith('/devices')) return 'menu.devices'
  if (p.startsWith('/apks')) return 'menu.apks'
  if (p.startsWith('/mock')) return 'menu.mock_rules'
  if (p.startsWith('/mobile-special')) return 'menu.mobile_special.title'
  if (p.startsWith('/system')) return 'menu.system.title'
  return 'layout.sider_title_full'
})

function onMenuClick({ key }: { key: string | number }) {
  router.push(String(key))
}

function handleLogout() {
  auth.logout()
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
