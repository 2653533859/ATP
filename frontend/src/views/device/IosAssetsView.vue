<template>
  <div class="page-shell">
    <div class="page-hero">
      <div>
        <h2 class="page-title">{{ t('ios_assets.title') }}</h2>
        <div class="page-subtitle">{{ t('ios_assets.subtitle') }}</div>
      </div>
      <a-tag color="orange">{{ t('ios_assets.preview') }}</a-tag>
    </div>
    <a-alert type="warning" show-icon :message="t('ios_assets.scope_notice')" style="margin-bottom: 16px" />

    <a-tabs>
      <a-tab-pane key="devices" :tab="t('ios_assets.devices')">
        <a-button type="primary" style="margin-bottom: 12px" @click="deviceModalOpen = true">{{ t('ios_assets.register_device') }}</a-button>
        <a-table :data-source="devices" :loading="loading" row-key="id" :pagination="false">
          <a-table-column key="name" :title="t('ios_assets.name')"><template #default="{ record }">{{ record.name || record.model || '-' }}</template></a-table-column>
          <a-table-column data-index="udid" title="UDID" />
          <a-table-column data-index="platform_version" title="iOS" />
          <a-table-column data-index="appium_server_url" title="Appium" />
          <a-table-column key="status" :title="t('ios_assets.status')"><template #default="{ record }"><a-tag>{{ record.status }}</a-tag></template></a-table-column>
          <a-table-column key="action" :title="t('common.action')"><template #default="{ record }"><a-popconfirm :title="t('ios_assets.delete_confirm')" @confirm="deleteDevice(record.id)"><a-button danger type="link">{{ t('common.delete') }}</a-button></a-popconfirm></template></a-table-column>
        </a-table>
      </a-tab-pane>
      <a-tab-pane key="apps" :tab="t('ios_assets.apps')">
        <a-space style="margin-bottom: 12px">
          <a-select v-model:value="projectId" :options="projectOptions" :placeholder="t('ios_assets.select_project')" style="width: 240px" @change="loadApps" />
          <a-upload :before-upload="uploadIpa" :show-upload-list="false" accept=".ipa"><a-button type="primary" :disabled="!projectId" :loading="uploading">{{ t('ios_assets.upload_ipa') }}</a-button></a-upload>
        </a-space>
        <a-table :data-source="apps" :loading="loadingApps" row-key="id" :pagination="false">
          <a-table-column data-index="filename" :title="t('ios_assets.filename')" />
          <a-table-column data-index="bundle_id" title="Bundle ID" />
          <a-table-column data-index="version_name" :title="t('ios_assets.version')" />
          <a-table-column key="action" :title="t('common.action')"><template #default="{ record }"><a-popconfirm :title="t('ios_assets.delete_confirm')" @confirm="deleteApp(record.id)"><a-button danger type="link">{{ t('common.delete') }}</a-button></a-popconfirm></template></a-table-column>
        </a-table>
      </a-tab-pane>
    </a-tabs>

    <a-modal v-model:open="deviceModalOpen" :title="t('ios_assets.register_device')" :confirm-loading="saving" @ok="saveDevice">
      <a-form layout="vertical">
        <a-form-item label="UDID" required><a-input v-model:value="deviceForm.udid" /></a-form-item>
        <a-form-item :label="t('ios_assets.name')"><a-input v-model:value="deviceForm.name" /></a-form-item>
        <a-form-item :label="t('ios_assets.model')"><a-input v-model:value="deviceForm.model" /></a-form-item>
        <a-form-item label="iOS"><a-input v-model:value="deviceForm.platform_version" /></a-form-item>
        <a-form-item label="Appium URL" required><a-input v-model:value="deviceForm.appium_server_url" /></a-form-item>
      </a-form>
    </a-modal>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { message } from 'ant-design-vue'
import { useI18n } from 'vue-i18n'
import { iosApi, projectApi, type IosAppItem, type IosDeviceItem, type ProjectItem } from '@/api'

const { t } = useI18n()
const devices = ref<IosDeviceItem[]>([])
const apps = ref<IosAppItem[]>([])
const projects = ref<ProjectItem[]>([])
const projectId = ref<number>()
const loading = ref(false)
const loadingApps = ref(false)
const uploading = ref(false)
const saving = ref(false)
const deviceModalOpen = ref(false)
const deviceForm = reactive({ udid: '', name: '', model: '', platform_version: '', appium_server_url: 'http://127.0.0.1:4723' })
const projectOptions = computed(() => projects.value.map((item) => ({ label: item.name, value: item.id })))

async function loadDevices() { loading.value = true; try { devices.value = await iosApi.devices() } finally { loading.value = false } }
async function loadApps() { if (!projectId.value) return; loadingApps.value = true; try { apps.value = await iosApi.apps(projectId.value) } finally { loadingApps.value = false } }
async function saveDevice() {
  if (!deviceForm.udid.trim() || !deviceForm.appium_server_url.trim()) return message.warning(t('ios_assets.required'))
  saving.value = true
  try { await iosApi.createDevice({ ...deviceForm }); deviceModalOpen.value = false; await loadDevices(); message.success(t('common.success')) } finally { saving.value = false }
}
async function deleteDevice(id: number) { await iosApi.deleteDevice(id); await loadDevices() }
async function deleteApp(id: number) { await iosApi.deleteApp(id); await loadApps() }
async function uploadIpa(file: File) {
  if (!projectId.value) return false
  uploading.value = true
  try { const form = new FormData(); form.append('project_id', String(projectId.value)); form.append('file', file); await iosApi.uploadApp(form); await loadApps() } finally { uploading.value = false }
  return false
}
onMounted(async () => { projects.value = await projectApi.list(); await loadDevices() })
</script>
