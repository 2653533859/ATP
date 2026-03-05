<template>
  <a-layout style="min-height: 100vh">
    <!-- 侧边栏 -->
    <a-layout-sider v-model:collapsed="collapsed" collapsible theme="dark">
      <div class="logo">{{ collapsed ? 'ATP' : 'ATP 测试平台' }}</div>
      <a-menu
        v-model:selectedKeys="selectedKeys"
        theme="dark"
        mode="inline"
        @click="onMenuClick"
      >
        <a-menu-item key="/projects">
          <ProjectOutlined />
          <span>项目管理</span>
        </a-menu-item>
        <a-menu-item key="/runs">
          <PlayCircleOutlined />
          <span>执行记录</span>
        </a-menu-item>
        <a-menu-item key="/devices">
          <MobileOutlined />
          <span>设备管理</span>
        </a-menu-item>
        <a-sub-menu key="system">
          <template #icon><SettingOutlined /></template>
          <template #title>系统管理</template>
          <a-menu-item key="/system/environments">环境管理</a-menu-item>
        </a-sub-menu>
      </a-menu>
    </a-layout-sider>

    <a-layout>
      <!-- 顶栏 -->
      <a-layout-header class="header">
        <a-space style="float: right">
          <span>{{ auth.user?.username }}</span>
          <a-button type="text" @click="handleLogout">退出</a-button>
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
import { ref, watch } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { ProjectOutlined, PlayCircleOutlined, SettingOutlined, MobileOutlined } from '@ant-design/icons-vue'
import { useAuthStore } from '@/stores/auth'

const router = useRouter()
const route = useRoute()
const auth = useAuthStore()

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
