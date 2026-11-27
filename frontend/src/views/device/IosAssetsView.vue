<template>
  <div class="page-shell">
    <div class="page-hero">
      <div>
        <h2 class="page-title">{{ t('ios_assets.title') }}</h2>
      </div>
      <a-tag color="orange">{{ t('ios_assets.preview') }}</a-tag>
    </div>
    <a-alert type="warning" show-icon :message="t('ios_assets.scope_notice')" style="margin-bottom: 16px" />

    <a-tabs>
      <a-tab-pane key="devices" :tab="t('ios_assets.devices')">
        <a-button v-if="canManageDevices" type="primary" style="margin-bottom: 12px" @click="openDeviceModal">{{ t('ios_assets.register_device') }}</a-button>
        <a-table :data-source="devices" :loading="loading" row-key="id" :pagination="false">
          <a-table-column key="name" :title="t('ios_assets.name')"><template #default="{ record }">{{ record.name || record.model || '-' }}</template></a-table-column>
          <a-table-column data-index="udid" title="UDID" />
          <a-table-column data-index="platform_version" title="iOS" />
          <a-table-column data-index="appium_server_url" title="Appium" />
          <a-table-column key="status" :title="t('ios_assets.status')"><template #default="{ record }"><a-tag>{{ record.status }}</a-tag></template></a-table-column>
          <a-table-column key="action" :title="t('common.action')" :width="220">
            <template #default="{ record }">
              <a-space size="small">
                <a-button type="link" size="small" :disabled="!canManageDevices" @click="openEditDeviceModal(record)">{{ t('common.edit') }}</a-button>
                <a-button type="link" size="small" :disabled="!canManageDevices" :loading="heartbeatingDeviceId === record.id" @click="heartbeatDevice(record.id)">{{ t('ios_assets.heartbeat') }}</a-button>
                <a-popconfirm :disabled="!canManageDevices" :title="t('ios_assets.delete_confirm')" @confirm="deleteDevice(record.id)">
                  <a-button danger type="link" size="small" :disabled="!canManageDevices">{{ t('common.delete') }}</a-button>
                </a-popconfirm>
              </a-space>
            </template>
          </a-table-column>
        </a-table>
      </a-tab-pane>
      <a-tab-pane key="apps" :tab="t('ios_assets.apps')">
        <a-space style="margin-bottom: 12px">
          <a-select v-model:value="projectId" :options="projectOptions" :placeholder="t('ios_assets.select_project')" allow-clear style="width: 240px" @change="onProjectChange" />
          <a-upload :disabled="!projectId || !canModifyProject" :before-upload="uploadIpa" :show-upload-list="false" accept=".ipa"><a-button type="primary" :disabled="!projectId || !canModifyProject" :loading="uploading">{{ t('ios_assets.upload_ipa') }}</a-button></a-upload>
        </a-space>
        <a-table :data-source="apps" :loading="loadingApps" row-key="id" :pagination="false">
          <a-table-column data-index="filename" :title="t('ios_assets.filename')" />
          <a-table-column data-index="bundle_id" title="Bundle ID" />
          <a-table-column data-index="version_name" :title="t('ios_assets.version')" />
          <a-table-column key="action" :title="t('common.action')" :width="210">
            <template #default="{ record }">
              <a-space size="small">
                <a-button type="link" size="small" :loading="downloadingAppId === record.id" @click="downloadApp(record.id)">{{ t('ios_assets.download') }}</a-button>
                <a-button type="link" size="small" :disabled="!canModifyProject" @click="openEditAppModal(record)">{{ t('common.edit') }}</a-button>
                <a-popconfirm :disabled="!canModifyProject" :title="t('ios_assets.delete_confirm')" @confirm="deleteApp(record.id)">
                  <a-button danger type="link" size="small" :disabled="!canModifyProject">{{ t('common.delete') }}</a-button>
                </a-popconfirm>
              </a-space>
            </template>
          </a-table-column>
        </a-table>
      </a-tab-pane>
    </a-tabs>

    <a-modal v-model:open="deviceModalOpen" :title="editingDeviceId ? t('ios_assets.edit_device') : t('ios_assets.register_device')" :confirm-loading="saving" :mask-closable="false" @ok="saveDevice" @cancel="resetDeviceForm">
      <a-form layout="vertical">
        <a-form-item label="UDID" required><a-input v-model:value="deviceForm.udid" :disabled="!!editingDeviceId" /></a-form-item>
        <a-form-item :label="t('ios_assets.name')"><a-input v-model:value="deviceForm.name" /></a-form-item>
        <a-form-item :label="t('ios_assets.model')"><a-input v-model:value="deviceForm.model" /></a-form-item>
        <a-form-item label="iOS"><a-input v-model:value="deviceForm.platform_version" /></a-form-item>
        <a-form-item label="Appium URL" required><a-input v-model:value="deviceForm.appium_server_url" /></a-form-item>
        <a-form-item v-if="editingDeviceId" :label="t('ios_assets.status')">
          <a-select v-model:value="deviceForm.status" :options="iosStatusOptions" />
        </a-form-item>
      </a-form>
    </a-modal>

    <a-modal v-model:open="appModalOpen" :title="t('ios_assets.edit_app')" :confirm-loading="savingApp" :mask-closable="false" @ok="saveApp">
      <a-form layout="vertical">
        <a-form-item label="Bundle ID"><a-input v-model:value="appForm.bundle_id" /></a-form-item>
        <a-form-item :label="t('ios_assets.version')"><a-input v-model:value="appForm.version_name" /></a-form-item>
        <a-form-item :label="t('ios_assets.signing_identity')"><a-input v-model:value="appForm.signing_identity" /></a-form-item>
        <a-form-item :label="t('ios_assets.provisioning_profile')"><a-input v-model:value="appForm.provisioning_profile" /></a-form-item>
        <a-form-item :label="t('common.description')"><a-textarea v-model:value="appForm.description" :rows="3" /></a-form-item>
      </a-form>
    </a-modal>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { message } from 'ant-design-vue'
import { useI18n } from 'vue-i18n'
import { useRoute } from 'vue-router'
import { iosApi, projectApi, type IosAppItem, type IosDeviceItem, type ProjectItem } from '@/api'
import { useAuthStore } from '@/stores/auth'
import { extractApiError } from '@/utils/apiError'
import { canEditProjectAssets, canEditProjectByRole } from '@/utils/permissions'

const { t } = useI18n()
const route = useRoute()
const auth = useAuthStore()
const devices = ref<IosDeviceItem[]>([])
const apps = ref<IosAppItem[]>([])
const projects = ref<ProjectItem[]>([])
const projectId = ref<number>()
const loading = ref(false)
const loadingApps = ref(false)
const uploading = ref(false)
const saving = ref(false)
const deviceModalOpen = ref(false)
const editingDeviceId = ref<number | null>(null)
const heartbeatingDeviceId = ref<number | null>(null)
const appModalOpen = ref(false)
const savingApp = ref(false)
const editingAppId = ref<number | null>(null)
const downloadingAppId = ref<number | null>(null)
const deviceForm = reactive({
  udid: '',
  name: '',
  model: '',
  platform_version: '',
  appium_server_url: 'http://127.0.0.1:4723',
  status: 'online' as IosDeviceItem['status'],
})
const appForm = reactive({
  bundle_id: '',
  version_name: '',
  signing_identity: '',
  provisioning_profile: '',
  description: '',
})
const iosStatusOptions = computed(() => [
  { label: t('device.statuses.online'), value: 'online' },
  { label: t('device.statuses.offline'), value: 'offline' },
  { label: t('device.statuses.busy'), value: 'busy' },
])
const projectOptions = computed(() => projects.value.map((item) => ({ label: item.name, value: item.id })))
const currentProject = computed(() => projects.value.find((item) => item.id === projectId.value))
const canModifyProject = computed(() => canEditProjectByRole(auth.user?.role, currentProject.value?.current_user_role))
const canManageDevices = computed(() => canEditProjectAssets(auth.user?.role))

function resetDeviceForm() {
  editingDeviceId.value = null
  Object.assign(deviceForm, {
    udid: '',
    name: '',
    model: '',
    platform_version: '',
    appium_server_url: 'http://127.0.0.1:4723',
    status: 'online' as IosDeviceItem['status'],
  })
}

function openDeviceModal() {
  resetDeviceForm()
  deviceModalOpen.value = true
}

function openEditDeviceModal(device: IosDeviceItem) {
  editingDeviceId.value = device.id
  Object.assign(deviceForm, {
    udid: device.udid,
    name: device.name || '',
    model: device.model || '',
    platform_version: device.platform_version || '',
    appium_server_url: device.appium_server_url,
    status: device.status,
  })
  deviceModalOpen.value = true
}

function openEditAppModal(app: IosAppItem) {
  editingAppId.value = app.id
  Object.assign(appForm, {
    bundle_id: app.bundle_id || '',
    version_name: app.version_name || '',
    signing_identity: app.signing_identity || '',
    provisioning_profile: app.provisioning_profile || '',
    description: app.description || '',
  })
  appModalOpen.value = true
}

async function loadDevices() {
  loading.value = true
  try {
    devices.value = await iosApi.devices()
  } catch (error: unknown) {
    message.error(extractApiError(error, '加载 iOS 设备失败'))
  } finally {
    loading.value = false
  }
}

async function loadApps() {
  if (!projectId.value) {
    apps.value = []
    return
  }
  loadingApps.value = true
  try {
    apps.value = await iosApi.apps(projectId.value)
  } catch (error: unknown) {
    message.error(extractApiError(error, '加载 IPA 资产失败'))
  } finally {
    loadingApps.value = false
  }
}

function onProjectChange() {
  void loadApps()
}

async function saveDevice() {
  if (!canManageDevices.value) return
  if (!deviceForm.udid.trim() || !deviceForm.appium_server_url.trim()) return message.warning(t('ios_assets.required'))
  saving.value = true
  try {
    if (editingDeviceId.value) {
      await iosApi.updateDevice(editingDeviceId.value, {
        name: deviceForm.name.trim() || undefined,
        model: deviceForm.model.trim() || undefined,
        platform_version: deviceForm.platform_version.trim() || undefined,
        appium_server_url: deviceForm.appium_server_url.trim(),
        status: deviceForm.status,
      })
    } else {
      await iosApi.createDevice({
        udid: deviceForm.udid.trim(),
        name: deviceForm.name.trim() || undefined,
        model: deviceForm.model.trim() || undefined,
        platform_version: deviceForm.platform_version.trim() || undefined,
        appium_server_url: deviceForm.appium_server_url.trim(),
      })
    }
    deviceModalOpen.value = false
    resetDeviceForm()
    await loadDevices()
    message.success(t('common.success'))
  } catch (error: unknown) {
    message.error(extractApiError(error, '保存 iOS 设备失败'))
  } finally {
    saving.value = false
  }
}

async function heartbeatDevice(id: number) {
  if (!canManageDevices.value) return
  heartbeatingDeviceId.value = id
  try {
    await iosApi.heartbeatDevice(id)
    await loadDevices()
    message.success(t('ios_assets.heartbeat_success'))
  } catch (error: unknown) {
    message.error(extractApiError(error, '刷新 iOS 设备心跳失败'))
  } finally {
    heartbeatingDeviceId.value = null
  }
}

async function saveApp() {
  if (!canModifyProject.value || !editingAppId.value) return
  savingApp.value = true
  try {
    await iosApi.updateApp(editingAppId.value, {
      bundle_id: appForm.bundle_id.trim() || null,
      version_name: appForm.version_name.trim() || null,
      signing_identity: appForm.signing_identity.trim() || null,
      provisioning_profile: appForm.provisioning_profile.trim() || null,
      description: appForm.description.trim() || null,
    })
    appModalOpen.value = false
    await loadApps()
    message.success(t('common.success'))
  } catch (error: unknown) {
    message.error(extractApiError(error, '更新 IPA 资产失败'))
  } finally {
    savingApp.value = false
  }
}

async function downloadApp(id: number) {
  downloadingAppId.value = id
  try {
    const res = await iosApi.downloadApp(id)
    if (res?.url) {
      window.open(res.url, '_blank', 'noopener,noreferrer')
    }
  } catch (error: unknown) {
    message.error(extractApiError(error, '获取 IPA 下载链接失败'))
  } finally {
    downloadingAppId.value = null
  }
}

async function deleteDevice(id: number) {
  if (!canManageDevices.value) return
  try {
    await iosApi.deleteDevice(id)
    await loadDevices()
    message.success(t('common.success'))
  } catch (error: unknown) {
    message.error(extractApiError(error, '删除 iOS 设备失败'))
  }
}

async function deleteApp(id: number) {
  if (!canModifyProject.value) return
  try {
    await iosApi.deleteApp(id)
    await loadApps()
    message.success(t('common.success'))
  } catch (error: unknown) {
    message.error(extractApiError(error, '删除 IPA 资产失败'))
  }
}

async function uploadIpa(file: File) {
  if (!projectId.value || !canModifyProject.value) return false
  uploading.value = true
  try {
    const form = new FormData()
    form.append('project_id', String(projectId.value))
    form.append('file', file)
    await iosApi.uploadApp(form)
    await loadApps()
    message.success(t('common.success'))
  } catch (error: unknown) {
    message.error(extractApiError(error, '上传 IPA 失败'))
  } finally {
    uploading.value = false
  }
  return false
}

onMounted(async () => {
  try {
    projects.value = await projectApi.list()
    const queryPid = Number(route.query.project_id)
    if (Number.isInteger(queryPid) && queryPid > 0 && projects.value.some((p) => p.id === queryPid)) {
      projectId.value = queryPid
      await loadApps()
    }
  } catch (error: unknown) {
    message.error(extractApiError(error, '加载项目列表失败'))
  }
  await loadDevices()
})
</script>
