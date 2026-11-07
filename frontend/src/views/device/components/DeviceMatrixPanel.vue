<template>
  <div class="device-matrix-grid">
    <div
      v-for="device in devices"
      :key="device.id"
      class="device-card-item"
      :class="`status-${device.status}`"
    >
      <div class="card-head">
        <div class="device-naming">
          <h3 class="device-model-title" :title="device.model || device.name || device.serial">
            {{ device.model || device.name || device.serial }}
          </h3>
          <span class="device-brand-subtitle">{{ device.brand || '品牌未上报' }}</span>
        </div>
        <div class="card-tags">
          <span v-if="device.serial && device.serial.includes(':')" class="protocol-tag" style="background: rgba(22, 119, 255, 0.15); color: #1677ff">远程</span>
          <span class="protocol-tag">ADB</span>
          <span :class="['status-chip', `chip-${device.status}`]">{{ statusText(device.status) }}</span>
        </div>
      </div>

      <div class="card-body">
        <div class="device-telemetry-badge" :class="`telemetry-${device.status}`">
          <div class="device-telemetry-icon">
            <MobileOutlined />
          </div>
          <div class="device-telemetry-status">
            <span class="telemetry-dot" />
            <span class="telemetry-state-text">{{ device.status === 'online' ? '连接活跃' : (device.status === 'busy' ? '正在执行' : '设备离线') }}</span>
          </div>
          <span class="telemetry-serial-code" :title="device.serial">{{ device.serial || '--' }}</span>
        </div>

        <div class="device-specs-sheet">
          <div class="spec-row"><span class="spec-label">系统</span><span class="spec-val">Android {{ device.os_version || '--' }}</span></div>
          <div class="spec-row"><span class="spec-label">分辨率</span><span class="spec-val">{{ device.resolution || '--' }}</span></div>
          <div class="spec-row"><span class="spec-label">最后使用人</span><span class="spec-val user-val">--</span></div>
          <div class="spec-row"><span class="spec-label">Agent</span><span class="spec-val agent-val">--</span></div>
          <div class="spec-row"><span class="spec-label">备注</span><span class="spec-val remark-val">{{ device.description || '--' }}</span></div>
        </div>
      </div>

      <div class="card-footer-actions">
        <div class="minor-actions">
          <a-button type="link" size="small" class="footer-link" @click="emit('edit', device)">详情</a-button>
          <a-tooltip title="后端暂未提供远程重启能力">
            <a-button type="link" size="small" class="footer-link" disabled>重启</a-button>
          </a-tooltip>
          <a-popconfirm
            v-if="device.serial && device.serial.includes(':')"
            title="确定要断开该远程设备的 ADB 连接吗？"
            @confirm="emit('disconnect', device.serial)"
          >
            <a-button type="link" size="small" class="footer-link" style="color: #fa8c16">断开</a-button>
          </a-popconfirm>
          <a-popconfirm :title="t('device.confirm_delete')" @confirm="emit('delete', device.id)">
            <a-button type="link" size="small" danger class="footer-link">删除</a-button>
          </a-popconfirm>
        </div>
        <button
          :class="['cta-use-btn', { disabled: device.status === 'offline' }]"
          :disabled="device.status === 'offline'"
          @click="device.status !== 'offline' ? emit('use', device) : null"
        >
          {{ device.status === 'offline' ? '设备已离线' : '立即使用' }}
        </button>
      </div>
    </div>

    <div v-if="devices.length === 0" class="empty-matrix-card">
      <a-empty :description="t('device.empty')" />
    </div>
  </div>
</template>

<script setup lang="ts">
import { MobileOutlined } from '@ant-design/icons-vue'
import { useI18n } from 'vue-i18n'
import type { DeviceItem, DeviceStatus } from '@/api'

defineProps<{ devices: DeviceItem[] }>()
const emit = defineEmits<{
  edit: [device: DeviceItem]
  delete: [id: number]
  use: [device: DeviceItem]
  disconnect: [serial: string]
}>()
const { t } = useI18n()

function statusText(status: DeviceStatus) {
  if (status === 'online') return '空闲'
  if (status === 'busy') return '使用中'
  return '离线'
}
</script>

<style scoped>
.device-matrix-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(340px, 1fr)); gap: 16px; }
.device-card-item { display: flex; flex-direction: column; justify-content: space-between; padding: 16px; border: 1px solid var(--c-border); border-radius: var(--radius-md); background: var(--c-bg-elevated); box-shadow: var(--shadow-xs); transition: border-color 0.15s ease; }
.device-card-item:hover { border-color: var(--c-border-strong); }
.card-head { display: flex; align-items: flex-start; justify-content: space-between; margin-bottom: 14px; }
.device-naming { flex: 1; min-width: 0; }
.device-model-title { margin: 0; overflow: hidden; color: var(--c-text); font-size: 15px; font-weight: 600; text-overflow: ellipsis; white-space: nowrap; }
.device-brand-subtitle { display: block; margin-top: 2px; color: var(--c-text-tertiary); font-size: 11px; }
.card-tags { display: flex; flex-shrink: 0; align-items: center; gap: 6px; }
.protocol-tag { padding: 1px 6px; border-radius: 4px; background: var(--c-bg-subtle); color: var(--c-text-secondary); font-family: ui-monospace, SFMono-Regular, Consolas, monospace; font-size: 10px; font-weight: 500; }
.status-chip { padding: 2px 8px; border-radius: 4px; font-size: 11px; font-weight: 500; }
.chip-online { background: var(--c-success-soft); color: var(--c-success); }
.chip-busy { background: var(--c-warning-soft); color: var(--c-warning); }
.chip-offline { background: var(--c-bg-muted); color: var(--c-text-secondary); }
.card-body { display: flex; align-items: center; gap: 16px; margin-bottom: 14px; }
.device-telemetry-badge { width: 100px; height: 116px; border: 1px solid var(--c-border); border-radius: var(--radius-sm); background: var(--c-bg-subtle); display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 8px; padding: 8px 6px; flex-shrink: 0; }
.device-telemetry-icon { font-size: 26px; color: var(--c-text-secondary); line-height: 1; }
.device-telemetry-status { display: flex; align-items: center; gap: 4px; font-size: 10px; font-weight: 500; }
.telemetry-dot { width: 6px; height: 6px; border-radius: 50%; }
.telemetry-online .telemetry-dot { background: var(--c-success); }
.telemetry-busy .telemetry-dot { background: var(--c-warning); }
.telemetry-offline .telemetry-dot { background: var(--c-text-tertiary); }
.telemetry-serial-code { font-size: 10px; font-family: ui-monospace, SFMono-Regular, Consolas, monospace; color: var(--c-text-tertiary); max-width: 88px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.device-specs-sheet { display: flex; flex: 1; flex-direction: column; gap: 6px; font-size: 12px; }
.spec-row { display: flex; align-items: center; line-height: 1.4; }
.spec-label { flex-shrink: 0; width: 68px; color: var(--c-text-secondary); }
.spec-val { overflow: hidden; color: var(--c-text); font-weight: 500; text-overflow: ellipsis; white-space: nowrap; }
.user-val, .agent-val { font-family: ui-monospace, SFMono-Regular, Consolas, monospace; }
.card-footer-actions { display: flex; flex-direction: column; gap: 10px; padding-top: 10px; border-top: 1px solid var(--c-border-subtle); }
.minor-actions { display: flex; align-items: center; justify-content: flex-end; gap: 8px; }
.footer-link { padding: 0 4px; color: var(--c-text-secondary); font-size: 12px; }
.footer-link:hover { color: var(--c-primary); }
.cta-use-btn { display: flex; align-items: center; justify-content: center; width: 100%; height: 32px; border: none; border-radius: var(--radius-sm); background: var(--c-primary); color: #fff; font-size: 12px; font-weight: 500; cursor: pointer; transition: background-color 0.15s; }
.cta-use-btn:hover:not(.disabled) { background: var(--c-primary-hover); }
.cta-use-btn.disabled { background: var(--c-bg-muted); color: var(--c-text-secondary); cursor: not-allowed; }
.empty-matrix-card { grid-column: 1 / -1; padding: 60px 0; border: 1px dashed var(--c-border); border-radius: var(--radius-md); background: var(--c-bg-elevated); }
</style>
