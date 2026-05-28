<template>
  <div class="device-page">
    <div class="toolbar">
      <a-space>
        <a-select
          v-model:value="statusFilter"
          :placeholder="t('device.status_filter')"
          allow-clear
          style="width: 130px"
          @change="loadDevices"
        >
          <a-select-option value="online">{{ t('device.statuses.online') }}</a-select-option>
          <a-select-option value="offline">{{ t('device.statuses.offline') }}</a-select-option>
          <a-select-option value="busy">{{ t('device.statuses.busy') }}</a-select-option>
        </a-select>
      </a-space>
      <a-button type="primary" :loading="scanning" @click="handleScan">
        <ReloadOutlined /> {{ t('device.scan') }}
      </a-button>
    </div>

    <a-table
      :columns="columns"
      :data-source="devices"
      :loading="loading"
      row-key="id"
      size="middle"
      :pagination="false"
    >
      <template #bodyCell="{ column, record }">
        <template v-if="column.key === 'status'">
          <a-badge
            :status="statusBadge(record.status)"
            :text="statusLabel(record.status)"
          />
        </template>

        <template v-if="column.key === 'device_info'">
          <div>{{ record.brand }} {{ record.model }}</div>
          <div style="color: #999; font-size: 12px">{{ record.serial }}</div>
        </template>

        <template v-if="column.key === 'os'">
          Android {{ record.os_version }}
          <span v-if="record.sdk_version" style="color: #999">(API {{ record.sdk_version }})</span>
        </template>

        <template v-if="column.key === 'last_seen'">
          {{ record.last_seen_at ? formatTime(record.last_seen_at) : '-' }}
        </template>

        <template v-if="column.key === 'action'">
          <a-space>
            <a-button
              v-if="record.status === 'online'"
              type="link"
              size="small"
              @click="openMirror(record)"
            >
              <EyeOutlined /> {{ t('device.mirror') }}
            </a-button>
            <a-button type="link" size="small" @click="openEdit(record)">{{ t('common.edit') }}</a-button>
            <a-popconfirm :title="t('device.confirm_delete')" @confirm="handleDelete(record.id)">
              <a-button type="link" size="small" danger>{{ t('common.delete') }}</a-button>
            </a-popconfirm>
          </a-space>
        </template>
      </template>
    </a-table>

    <a-modal
      v-model:open="editOpen"
      :title="t('device.edit')"
      :ok-text="t('common.save')"
      :cancel-text="t('common.cancel')"
      :confirm-loading="saving"
      @ok="handleSave"
    >
      <a-form layout="vertical">
        <a-form-item :label="t('device.fields.name')">
          <a-input v-model:value="editForm.name" :placeholder="t('device.placeholders.name')" />
        </a-form-item>
        <a-form-item :label="t('device.fields.description')">
          <a-textarea v-model:value="editForm.description" :placeholder="t('device.placeholders.description')" :rows="3" />
        </a-form-item>
      </a-form>
    </a-modal>

    <a-modal
      v-model:open="mirrorOpen"
      :title="t('device.mirror_title', { name: `${mirrorDevice?.brand ?? ''} ${mirrorDevice?.model ?? ''}`.trim() })"
      width="420"
      :footer="null"
      :destroy-on-close="true"
      @cancel="closeMirror"
    >
      <div class="mirror-container">
        <img
          v-if="mirrorSrc"
          :src="mirrorSrc"
          :alt="t('device.screen_alt')"
          class="mirror-img"
          @error="onMirrorError"
        />
        <div v-else class="mirror-placeholder">
          <a-spin :tip="t('device.connecting')" />
        </div>
      </div>
      <div class="mirror-footer">
        <a-button size="small" @click="refreshMirror">
          <ReloadOutlined /> {{ t('device.refresh_screenshot') }}
        </a-button>
        <span style="color: #999; font-size: 12px">{{ t('device.auto_refresh') }}</span>
      </div>
    </a-modal>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, onMounted, onUnmounted } from 'vue'
import { message } from 'ant-design-vue'
import { ReloadOutlined, EyeOutlined } from '@ant-design/icons-vue'
import { useI18n } from 'vue-i18n'
import { deviceApi } from '@/api'
import type { DeviceItem, DeviceStatus } from '@/api'

const { t } = useI18n()
const devices = ref<DeviceItem[]>([])
const loading = ref(false)
const scanning = ref(false)
const statusFilter = ref<string | undefined>(undefined)

const editOpen = ref(false)
const saving = ref(false)
const editingId = ref<number | null>(null)
const editForm = ref({ name: '', description: '' })

const mirrorOpen = ref(false)
const mirrorDevice = ref<DeviceItem | null>(null)
const mirrorSrc = ref<string | null>(null)
let mirrorTimer: ReturnType<typeof setInterval> | null = null
let mirrorObjectUrl: string | null = null
let mirrorRefreshing = false
let mirrorSession = 0

const columns = computed(() => [
  { title: t('device.columns.device_info'), key: 'device_info', width: 240 },
  { title: t('device.columns.status'), key: 'status', width: 100 },
  { title: t('device.columns.os'), key: 'os', width: 200 },
  { title: t('device.columns.resolution'), dataIndex: 'resolution', key: 'resolution', width: 120 },
  { title: t('device.columns.last_seen'), key: 'last_seen', width: 170 },
  { title: t('device.columns.action'), key: 'action', width: 180, fixed: 'right' as const },
])

function errorMessage(error: unknown, fallback: string) {
  if (typeof error === 'string') return error
  if (error instanceof Error) return error.message
  return fallback
}

function statusBadge(s: DeviceStatus) {
  return { online: 'success', offline: 'default', busy: 'processing' }[s] ?? 'default'
}

function statusLabel(s: DeviceStatus) {
  return {
    online: t('device.statuses.online'),
    offline: t('device.statuses.offline'),
    busy: t('device.statuses.busy'),
  }[s] ?? s
}

function formatTime(t: string) {
  return t?.slice(0, 19).replace('T', ' ')
}

async function loadDevices() {
  loading.value = true
  try {
    devices.value = await deviceApi.list(
      statusFilter.value ? { status_filter: statusFilter.value } : undefined,
    )
  } catch (e: unknown) {
    message.error(errorMessage(e, t('device.msg.load_failed')))
  } finally {
    loading.value = false
  }
}

async function handleScan() {
  scanning.value = true
  try {
    devices.value = await deviceApi.scan()
    message.success(t('device.msg.scan_success', { count: devices.value.length }))
  } catch (e: unknown) {
    message.error(errorMessage(e, t('device.msg.scan_failed')))
  } finally {
    scanning.value = false
  }
}

function openEdit(record: DeviceItem) {
  editingId.value = record.id
  editForm.value = {
    name: record.name ?? '',
    description: record.description ?? '',
  }
  editOpen.value = true
}

async function handleSave() {
  if (!editingId.value) return
  saving.value = true
  try {
    await deviceApi.update(editingId.value, editForm.value)
    message.success(t('device.msg.save_success'))
    editOpen.value = false
    loadDevices()
  } catch (e: unknown) {
    message.error(errorMessage(e, t('device.msg.save_failed')))
  } finally {
    saving.value = false
  }
}

async function handleDelete(id: number) {
  try {
    await deviceApi.delete(id)
    message.success(t('device.msg.delete_success'))
    loadDevices()
  } catch (e: unknown) {
    message.error(errorMessage(e, t('device.msg.delete_failed')))
  }
}

function openMirror(record: DeviceItem) {
  mirrorDevice.value = record
  mirrorOpen.value = true
  mirrorSession += 1
  void refreshMirror(mirrorSession)
  mirrorTimer = setInterval(() => {
    void refreshMirror(mirrorSession)
  }, 500)
}

function closeMirror() {
  mirrorSession += 1
  mirrorOpen.value = false
  mirrorDevice.value = null
  mirrorSrc.value = null
  mirrorRefreshing = false
  revokeMirrorObjectUrl()
  if (mirrorTimer) {
    clearInterval(mirrorTimer)
    mirrorTimer = null
  }
}

function revokeMirrorObjectUrl() {
  if (mirrorObjectUrl) {
    URL.revokeObjectURL(mirrorObjectUrl)
    mirrorObjectUrl = null
  }
}

async function refreshMirror(sessionId = mirrorSession) {
  if (!mirrorDevice.value || mirrorRefreshing || sessionId !== mirrorSession) return
  mirrorRefreshing = true
  try {
    const blob = await deviceApi.screenshot(mirrorDevice.value.id)
    if (!mirrorOpen.value || sessionId !== mirrorSession) return

    const nextUrl = URL.createObjectURL(blob)
    revokeMirrorObjectUrl()
    mirrorObjectUrl = nextUrl
    mirrorSrc.value = nextUrl
  } catch (_e) {
    // Keep the last frame if screenshot refresh fails.
  } finally {
    mirrorRefreshing = false
  }
}

function onMirrorError() {
  // Keep the last frame when the image element reports an error.
}

onMounted(loadDevices)

onUnmounted(() => {
  closeMirror()
})
</script>

<style scoped>
.device-page {
  display: flex;
  flex-direction: column;
  gap: 16px;
}
.toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.mirror-container {
  display: flex;
  justify-content: center;
  align-items: center;
  min-height: 400px;
  background: #000;
  border-radius: 8px;
  overflow: hidden;
}
.mirror-img {
  max-width: 100%;
  max-height: 600px;
  object-fit: contain;
}
.mirror-placeholder {
  display: flex;
  justify-content: center;
  align-items: center;
  height: 400px;
  color: #999;
}
.mirror-footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-top: 12px;
}
</style>
