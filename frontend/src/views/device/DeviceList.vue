<template>
  <div class="device-page">
    <div class="toolbar">
      <a-space>
        <a-select
          v-model:value="statusFilter"
          placeholder="设备状态"
          allow-clear
          style="width: 130px"
          @change="loadDevices"
        >
          <a-select-option value="online">在线</a-select-option>
          <a-select-option value="offline">离线</a-select-option>
          <a-select-option value="busy">执行中</a-select-option>
        </a-select>
      </a-space>
      <a-button type="primary" :loading="scanning" @click="handleScan">
        <ReloadOutlined /> 扫描设备
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
            <a-button type="link" size="small" @click="openEdit(record)">编辑</a-button>
            <a-popconfirm title="确认删除该设备记录？" @confirm="handleDelete(record.id)">
              <a-button type="link" size="small" danger>删除</a-button>
            </a-popconfirm>
          </a-space>
        </template>
      </template>
    </a-table>

    <!-- 编辑 Modal -->
    <a-modal
      v-model:open="editOpen"
      title="编辑设备"
      ok-text="保存"
      cancel-text="取消"
      :confirm-loading="saving"
      @ok="handleSave"
    >
      <a-form layout="vertical">
        <a-form-item label="设备名称">
          <a-input v-model:value="editForm.name" placeholder="自定义设备名称" />
        </a-form-item>
        <a-form-item label="备注">
          <a-textarea v-model:value="editForm.description" placeholder="设备备注信息" :rows="3" />
        </a-form-item>
      </a-form>
    </a-modal>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { message } from 'ant-design-vue'
import { ReloadOutlined } from '@ant-design/icons-vue'
import { deviceApi } from '@/api'

const devices = ref<any[]>([])
const loading = ref(false)
const scanning = ref(false)
const statusFilter = ref<string | undefined>(undefined)

const editOpen = ref(false)
const saving = ref(false)
const editingId = ref<number | null>(null)
const editForm = ref({ name: '', description: '' })

const columns = [
  { title: '设备信息', key: 'device_info', width: 240 },
  { title: '状态', key: 'status', width: 100 },
  { title: '系统版本', key: 'os', width: 200 },
  { title: '分辨率', dataIndex: 'resolution', key: 'resolution', width: 120 },
  { title: '最后在线', key: 'last_seen', width: 170 },
  { title: '操作', key: 'action', width: 140, fixed: 'right' as const },
]

function statusBadge(s: string) {
  return { online: 'success', offline: 'default', busy: 'processing' }[s] ?? 'default'
}

function statusLabel(s: string) {
  return { online: '在线', offline: '离线', busy: '执行中' }[s] ?? s
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
  } catch (e: any) {
    message.error(e ?? '加载设备列表失败')
  } finally {
    loading.value = false
  }
}

async function handleScan() {
  scanning.value = true
  try {
    devices.value = await deviceApi.scan()
    message.success(`扫描完成，发现 ${devices.value.length} 台设备`)
  } catch (e: any) {
    message.error(e ?? '设备扫描失败')
  } finally {
    scanning.value = false
  }
}

function openEdit(record: any) {
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
    message.success('保存成功')
    editOpen.value = false
    loadDevices()
  } catch (e: any) {
    message.error(e ?? '保存失败')
  } finally {
    saving.value = false
  }
}

async function handleDelete(id: number) {
  try {
    await deviceApi.delete(id)
    message.success('已删除')
    loadDevices()
  } catch (e: any) {
    message.error(e ?? '删除失败')
  }
}

onMounted(loadDevices)
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
</style>
