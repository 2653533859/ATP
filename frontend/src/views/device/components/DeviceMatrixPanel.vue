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
          <span class="protocol-tag">ADB</span>
          <span :class="['status-chip', `chip-${device.status}`]">{{ statusText(device.status) }}</span>
        </div>
      </div>

      <div class="card-body">
        <div class="phone-mockup" :class="`phone-${device.status}`">
          <div class="phone-top-notch">
            <div class="phone-camera-dot"></div>
            <div class="phone-speaker-bar"></div>
          </div>
          <div class="phone-screen">
            <div v-if="device.status === 'online'" class="screen-live">
              <div class="screen-status-bar">
                <span class="status-time">ADB</span>
                <div class="status-icons"><span class="status-wifi">●</span></div>
              </div>
              <div class="screen-app-grid">
                <div v-for="index in 6" :key="index" class="mini-app" :class="`app-${index}`"></div>
              </div>
              <div class="screen-dock">
                <div class="dock-app dock-phone"></div>
                <div class="dock-app dock-msg"></div>
                <div class="dock-app dock-web"></div>
              </div>
            </div>
            <div v-else class="screen-offline">
              <div class="offline-icon-wrap"><MobileOutlined class="offline-phone-icon" /></div>
              <span class="offline-text">设备离线</span>
            </div>
          </div>
          <div class="phone-bottom-bar"></div>
        </div>

        <div class="device-specs-sheet">
          <div class="spec-row"><span class="spec-label">系统</span><span class="spec-val">Android {{ device.os_version || '--' }}</span></div>
          <div class="spec-row"><span class="spec-label">电量</span><span class="spec-val">--</span></div>
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
          <a-popconfirm :title="t('device.confirm_delete')" @confirm="emit('delete', device.id)">
            <a-button type="link" size="small" danger class="footer-link">删除</a-button>
          </a-popconfirm>
        </div>
        <button
          :class="['cta-use-btn', { disabled: device.status === 'offline' }]"
          :disabled="device.status === 'offline'"
          @click="device.status !== 'offline' ? emit('use', device) : null"
        >
          立即使用
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
}>()
const { t } = useI18n()

function statusText(status: DeviceStatus) {
  if (status === 'online') return '空闲'
  if (status === 'busy') return '使用中'
  return '离线'
}
</script>

<style scoped>
.device-matrix-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(350px, 1fr)); gap: 16px; }
.device-card-item { display: flex; flex-direction: column; justify-content: space-between; padding: 16px; border: 1px solid var(--c-border); border-radius: 12px; background: var(--c-bg-elevated); box-shadow: 0 1px 3px rgba(0, 0, 0, 0.03); transition: transform 0.2s, box-shadow 0.2s, border-color 0.2s; }
.device-card-item:hover { transform: translateY(-2px); border-color: var(--c-border-strong); box-shadow: 0 8px 20px rgba(15, 23, 42, 0.08); }
.card-head { display: flex; align-items: flex-start; justify-content: space-between; margin-bottom: 14px; }
.device-naming { flex: 1; min-width: 0; }
.device-model-title { margin: 0; overflow: hidden; color: var(--c-text); font-size: 16px; font-weight: 700; text-overflow: ellipsis; white-space: nowrap; }
.device-brand-subtitle { display: block; margin-top: 2px; color: var(--c-text-tertiary); font-size: 11px; }
.card-tags { display: flex; flex-shrink: 0; align-items: center; gap: 6px; }
.protocol-tag { padding: 1px 6px; border-radius: 4px; background: var(--c-bg-subtle); color: var(--c-text-secondary); font-family: ui-monospace, SFMono-Regular, Consolas, monospace; font-size: 10px; font-weight: 600; }
.status-chip { padding: 2px 8px; border-radius: 12px; font-size: 11px; font-weight: 600; }
.chip-online { background: #dcfce7; color: #15803d; }
.chip-busy { background: #ffedd5; color: #c2410c; }
.chip-offline { background: #fee2e2; color: #b91c1c; }
.card-body { display: flex; align-items: center; gap: 18px; margin-bottom: 14px; }
.phone-mockup { position: relative; display: flex; flex-shrink: 0; flex-direction: column; justify-content: space-between; width: 106px; height: 182px; overflow: hidden; border: 3px solid #334155; border-radius: 20px; background: #0f172a; box-shadow: 0 4px 14px rgba(0, 0, 0, 0.18); }
.phone-top-notch { z-index: 2; display: flex; align-items: center; justify-content: center; height: 10px; gap: 4px; background: #0f172a; }
.phone-camera-dot { width: 4px; height: 4px; border-radius: 50%; background: #475569; }
.phone-speaker-bar { width: 14px; height: 2px; border-radius: 2px; background: #475569; }
.phone-bottom-bar { display: flex; align-items: center; justify-content: center; height: 6px; background: #0f172a; }
.phone-bottom-bar::after { width: 24px; height: 2px; border-radius: 2px; background: #475569; content: ''; }
.phone-screen { position: relative; flex: 1; overflow: hidden; }
.screen-live { display: flex; flex-direction: column; justify-content: space-between; width: 100%; height: 100%; padding: 4px; background: linear-gradient(135deg, #1e3a8a, #0d9488 70%, #059669); }
.screen-status-bar { display: flex; align-items: center; justify-content: space-between; padding: 0 2px; color: #f8fafc; font-size: 8px; }
.status-icons { display: flex; gap: 3px; font-size: 7px; }
.screen-app-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 5px; padding: 6px 3px; }
.mini-app { height: 16px; border-radius: 4px; box-shadow: 0 1px 3px rgba(0, 0, 0, 0.2); }
.app-1 { background: #38bdf8; } .app-2 { background: #fb7185; } .app-3 { background: #facc15; }
.app-4 { background: #4ade80; } .app-5 { background: #c084fc; } .app-6 { background: #fb923c; }
.screen-dock { display: flex; justify-content: space-around; margin-top: auto; padding: 3px; border-radius: 6px; background: rgba(255, 255, 255, 0.2); backdrop-filter: blur(4px); }
.dock-app { width: 14px; height: 14px; border-radius: 3px; }
.dock-phone { background: #22c55e; } .dock-msg { background: #3b82f6; } .dock-web { background: #eab308; }
.screen-offline { display: flex; flex-direction: column; align-items: center; justify-content: center; width: 100%; height: 100%; gap: 6px; background: #1e293b; color: var(--c-text-secondary); }
.offline-icon-wrap { display: flex; align-items: center; justify-content: center; width: 28px; height: 28px; border-radius: 50%; background: #0f172a; }
.offline-phone-icon { color: var(--c-text-secondary); font-size: 14px; }
.offline-text { color: var(--c-text-tertiary); font-size: 10px; }
.device-specs-sheet { display: flex; flex: 1; flex-direction: column; gap: 6px; font-size: 12px; }
.spec-row { display: flex; align-items: center; line-height: 1.4; }
.spec-label { flex-shrink: 0; width: 68px; color: var(--c-text-secondary); }
.spec-val { overflow: hidden; color: var(--c-text); font-weight: 500; text-overflow: ellipsis; white-space: nowrap; }
.user-val, .agent-val { font-family: ui-monospace, SFMono-Regular, Consolas, monospace; }
.card-footer-actions { display: flex; flex-direction: column; gap: 10px; padding-top: 10px; border-top: 1px solid var(--c-border-subtle); }
.minor-actions { display: flex; align-items: center; justify-content: flex-end; gap: 8px; }
.footer-link { padding: 0 4px; color: var(--c-text-secondary); font-size: 12px; }
.footer-link:hover { color: var(--c-primary); }
.cta-use-btn { display: flex; align-items: center; justify-content: center; width: 100%; height: 34px; border: none; border-radius: 6px; background: var(--c-primary); box-shadow: 0 2px 8px rgba(37, 99, 235, 0.2); color: #fff; font-size: 13px; font-weight: 600; cursor: pointer; transition: all 0.2s; }
.cta-use-btn:hover:not(.disabled) { background: #1d4ed8; box-shadow: 0 4px 12px rgba(37, 99, 235, 0.3); }
.cta-use-btn.disabled { background: var(--c-bg-muted); box-shadow: none; color: var(--c-text-tertiary); cursor: not-allowed; }
.empty-matrix-card { grid-column: 1 / -1; padding: 60px 0; border: 1px dashed var(--c-border); border-radius: 12px; background: var(--c-bg-elevated); }
</style>
