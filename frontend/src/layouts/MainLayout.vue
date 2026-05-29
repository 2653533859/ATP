<template>
  <a-layout style="min-height: 100vh">
    <!-- 侧边栏 -->
    <a-layout-sider v-model:collapsed="collapsed" collapsible theme="dark">
      <div class="logo">{{ collapsed ? t('layout.sider_title_short') : t('layout.sider_title_full') }}</div>
      <a-menu
        v-model:selectedKeys="selectedKeys"
        theme="dark"
        mode="inline"
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
        <a-menu-item key="/devices">
          <MobileOutlined />
          <span>{{ t('menu.devices') }}</span>
        </a-menu-item>
        <a-menu-item key="/apks">
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
          <a-menu-item key="/system/notifications">{{ t('menu.system.notifications') }}</a-menu-item>
          <a-menu-item key="/system/bug-trackers">{{ t('menu.system.bug_trackers') }}</a-menu-item>
          <a-menu-item key="/system/storage">{{ t('menu.system.storage') }}</a-menu-item>
          <a-menu-item key="/system/global-variables">{{ t('menu.system.global_variables') }}</a-menu-item>
          <a-menu-item key="/system/ai-llm-configs">{{ t('menu.system.ai_llm_configs') }}</a-menu-item>
          <a-menu-item v-if="auth.user?.role === 'admin'" key="/system/healing-examples">AI 自愈示例</a-menu-item>
          <a-menu-item v-if="auth.user?.role === 'admin'" key="/system/ai-healing-stats">AI 自愈报表</a-menu-item>
          <a-menu-item key="/system/datasets">{{ t('menu.system.datasets') }}</a-menu-item>
          <a-menu-item key="/system/performance">{{ t('menu.system.performance') }}</a-menu-item>
          <a-menu-item v-if="auth.user?.role === 'admin'" key="/system/audit-logs">{{ t('menu.system.audit_logs') }}</a-menu-item>
          <a-menu-item v-if="auth.user?.role === 'admin'" key="/system/run-retention">{{ t('menu.system.run_retention') }}</a-menu-item>
          <a-menu-item v-if="auth.user?.role === 'admin'" key="/system/dashboard-alerts">{{ t('menu.system.dashboard_alerts') }}</a-menu-item>
        </a-sub-menu>
      </a-menu>
    </a-layout-sider>

    <a-layout>
      <!-- 顶栏 -->
      <a-layout-header class="header">
        <a-space style="float: right">
          <a-select
            :value="currentLocale"
            size="small"
            style="width: 110px"
            :options="localeOptions"
            @change="onLocaleChange"
          />
          <span>{{ auth.user?.username }}</span>
          <a-button type="text" @click="handleLogout">{{ t('common.logout') }}</a-button>
        </a-space>
      </a-layout-header>

      <!-- 内容区 -->
      <a-layout-content class="content">
        <RouterView />
      </a-layout-content>
    </a-layout>
  </a-layout>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { ProjectOutlined, ProfileOutlined, PlayCircleOutlined, SettingOutlined, MobileOutlined, AndroidOutlined, AppstoreOutlined, ClockCircleOutlined, DashboardOutlined, ApiOutlined } from '@ant-design/icons-vue'
import { useAuthStore } from '@/stores/auth'
import { getLocale, setLocale, type SupportedLocale } from '@/locales'

const router = useRouter()
const route = useRoute()
const auth = useAuthStore()
const { t } = useI18n()

const collapsed = ref(false)
const selectedKeys = ref([route.path])

watch(() => route.path, (path) => { selectedKeys.value = [path] })

function onMenuClick({ key }: { key: string }) {
  router.push(key)
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

function onLocaleChange(value: SupportedLocale) {
  setLocale(value)
}
</script>

<style scoped>
.logo {
  height: 64px;
  color: #fff;
  font-size: 16px;
  font-weight: bold;
  display: flex;
  align-items: center;
  justify-content: center;
  overflow: hidden;
  white-space: nowrap;
}
.header {
  background: #fff;
  padding: 0 24px;
  display: flex;
  align-items: center;
  justify-content: flex-end;
  box-shadow: 0 1px 4px rgba(0, 21, 41, 0.08);
}
.content {
  margin: 24px;
  padding: 24px;
  background: #fff;
  border-radius: 8px;
  min-height: 360px;
}
</style>
