<template>
  <div
    class="ios-device-card"
    :class="[
      `status-${deviceStatus.toLowerCase()}`,
      { 'card-busy': isBusy, 'card-selected': selected }
    ]"
    @click="$emit('select', device)"
  >
    <!-- 卡片顶部: 设备名称、型号与状态角标 -->
    <div class="card-head">
      <div class="device-naming">
        <div class="name-row">
          <AppleOutlined class="apple-icon" />
          <h4 class="device-title" :title="device.device_name || device.udid">
            {{ device.device_name || 'iPhone' }}
          </h4>
        </div>
        <span class="device-model-sub">{{ device.model }} · iOS {{ device.ios_version }}</span>
      </div>

      <div class="card-status-badge">
        <span class="status-dot" :class="`dot-${deviceStatus.toLowerCase()}`" />
        <span class="status-text">{{ statusLabel }}</span>
      </div>
    </div>

    <!-- 中部: 拟真 iPhone 小屏与关键规格参数 -->
    <div class="card-body">
      <!-- 拟真机身指示器 -->
      <div class="mini-iphone-mockup" :class="`mockup-${deviceStatus.toLowerCase()}`">
        <div class="mini-notch" />
        <div class="mini-screen">
          <div v-if="deviceStatus !== 'OFFLINE'" class="mini-screen-online">
            <span class="mini-screen-text">{{ device.model }}</span>
            <span class="mini-screen-port">Port: {{ device.local_tunnel_port }}</span>
          </div>
          <div v-else class="mini-screen-offline">
            <DisconnectOutlined class="offline-icon" />
            <span class="offline-lbl">已离线</span>
          </div>
        </div>
        <div class="mini-home-bar" />
      </div>

      <!-- 硬件指标与租约规格表 -->
      <div class="specs-grid">
        <div class="spec-item">
          <span class="spec-label">设备 UDID</span>
          <span class="spec-val font-mono" :title="device.udid">
            {{ formatUdid(device.udid) }}
            <CopyOutlined class="copy-btn" @click.stop="copyUdid(device.udid)" />
          </span>
        </div>

        <div class="spec-item">
          <span class="spec-label">电池电量</span>
          <div class="battery-spec-val">
            <span :class="batteryColorClass">{{ device.battery_level ?? 100 }}%</span>
            <ThunderboltOutlined v-if="device.battery_level != null" class="charging-icon" />
          </div>
        </div>

        <div class="spec-item">
          <span class="spec-label">机身温度</span>
          <span class="spec-val font-mono">{{ device.temperature_celsius ?? 28.5 }} ℃</span>
        </div>

        <div class="spec-item">
          <span class="spec-label">WDA 隧道端口</span>
          <span class="spec-val font-mono text-primary">:{{ device.local_tunnel_port }}</span>
        </div>

        <div class="spec-item">
          <span class="spec-label">所属 macOS Agent</span>
          <span class="spec-val" :title="device.agent_name">{{ device.agent_name || device.agent_id }}</span>
        </div>

        <div class="spec-item">
          <span class="spec-label">租约占用状态</span>
          <span v-if="isBusy" class="spec-val text-warning font-semibold">
            {{ leaseInfo?.owner_label || '任务占用中' }}
          </span>
          <span v-else-if="deviceStatus === 'ONLINE'" class="spec-val text-success">
            空闲可申领
          </span>
          <span v-else class="spec-val text-muted">
            不可用
          </span>
        </div>
      </div>
    </div>

    <!-- 底部动作条 -->
    <div class="card-footer-actions" @click.stop>
      <div class="footer-left">
        <a-tag v-if="device.wda_alive" color="success" class="mini-pill-tag">WDA 存活</a-tag>
        <a-tag v-else color="error" class="mini-pill-tag">WDA 离线</a-tag>
      </div>

      <div class="footer-right">
        <a-space size="small">
          <!-- 投屏按钮 -->
          <a-button
            size="small"
            type="primary"
            :disabled="deviceStatus === 'OFFLINE'"
            @click="handleOpenMirror"
          >
            <MobileOutlined /> 投屏控制
          </a-button>

          <!-- 申领 / 释放租约按钮 -->
          <a-button
            v-if="!isBusy"
            size="small"
            :disabled="deviceStatus !== 'ONLINE'"
            @click="handleAcquireLease"
          >
            申领租约
          </a-button>
          <a-button
            v-else
            size="small"
            danger
            @click="handleReleaseLease"
          >
            归还租约
          </a-button>
        </a-space>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { message } from 'ant-design-vue'
import {
  AppleOutlined,
  CopyOutlined,
  ThunderboltOutlined,
  MobileOutlined,
  DisconnectOutlined,
} from '@ant-design/icons-vue'
import type { IosTunnelDeviceItem, IosLeaseItem } from '@/api/iosTunnel'

const props = defineProps<{
  device: IosTunnelDeviceItem
  leaseInfo?: IosLeaseItem | null
  selected?: boolean
}>()

const emit = defineEmits<{
  (e: 'select', device: IosTunnelDeviceItem): void
  (e: 'open-mirror', device: IosTunnelDeviceItem): void
  (e: 'acquire-lease', device: IosTunnelDeviceItem): void
  (e: 'release-lease', device: IosTunnelDeviceItem): void
}>()

const isBusy = computed(() => {
  return props.device.status === 'BUSY' || Boolean(props.leaseInfo?.is_active)
})

const deviceStatus = computed(() => {
  if (props.device.status === 'OFFLINE' || props.device.health_status === 'OFFLINE') {
    return 'OFFLINE'
  }
  if (!props.device.wda_alive) {
    return 'WDA_UNHEALTHY'
  }
  if (isBusy.value) {
    return 'BUSY'
  }
  return 'ONLINE'
})

const statusLabel = computed(() => {
  switch (deviceStatus.value) {
    case 'ONLINE':
      return '在线空闲'
    case 'BUSY':
      return '租用占用'
    case 'WDA_UNHEALTHY':
      return 'WDA异常'
    case 'OFFLINE':
    default:
      return '设备离线'
  }
})

const batteryColorClass = computed(() => {
  const level = props.device.battery_level ?? 100
  if (level > 40) return 'text-success font-mono'
  if (level > 20) return 'text-warning font-mono'
  return 'text-danger font-mono'
})

function formatUdid(udid: string): string {
  if (udid.length > 16) {
    return `${udid.slice(0, 8)}...${udid.slice(-6)}`
  }
  return udid
}

function copyUdid(udid: string) {
  navigator.clipboard?.writeText(udid)
  message.success('UDID 已复制到剪贴板')
}

function handleOpenMirror() {
  emit('open-mirror', props.device)
}

function handleAcquireLease() {
  emit('acquire-lease', props.device)
}

function handleReleaseLease() {
  emit('release-lease', props.device)
}
</script>

<style scoped>
.ios-device-card {
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  background: var(--c-bg-card, #ffffff);
  border: 1px solid var(--c-border, #e2e8f0);
  border-radius: 12px;
  padding: 14px;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.05);
  transition: all 0.2s ease;
  cursor: pointer;
  position: relative;
  overflow: hidden;
}

.ios-device-card:hover {
  border-color: var(--c-primary, #1677ff);
  box-shadow: 0 4px 12px rgba(22, 119, 255, 0.12);
  transform: translateY(-2px);
}

.ios-device-card.card-selected {
  border-color: var(--c-primary, #1677ff);
  background: #f0f7ff;
}

.card-head {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 12px;
}

.device-naming {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.name-row {
  display: flex;
  align-items: center;
  gap: 6px;
}

.apple-icon {
  font-size: 16px;
  color: #1e293b;
}

.device-title {
  margin: 0;
  font-size: 15px;
  font-weight: 700;
  color: var(--c-text, #0f172a);
}

.device-model-sub {
  font-size: 12px;
  color: var(--c-text-secondary, #64748b);
}

.card-status-badge {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 3px 8px;
  border-radius: 12px;
  background: var(--c-bg-subtle, #f8fafc);
  border: 1px solid var(--c-border-subtle, #e2e8f0);
}

.status-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
}

.dot-online {
  background: #52c41a;
  box-shadow: 0 0 6px #52c41a;
}

.dot-busy {
  background: #fa8c16;
  box-shadow: 0 0 6px #fa8c16;
}

.dot-wda_unhealthy {
  background: #ff4d4f;
  box-shadow: 0 0 6px #ff4d4f;
}

.dot-offline {
  background: #94a3b8;
}

.status-text {
  font-size: 11px;
  font-weight: 600;
}

/* 机身卡片主体 */
.card-body {
  display: grid;
  grid-template-columns: 80px 1fr;
  gap: 14px;
  align-items: center;
  margin-bottom: 12px;
}

.mini-iphone-mockup {
  position: relative;
  width: 76px;
  height: 148px;
  background: #18181b;
  border-radius: 18px;
  padding: 4px;
  box-shadow: 0 4px 10px rgba(0, 0, 0, 0.2);
  display: flex;
  flex-direction: column;
  align-items: center;
}

.mini-notch {
  position: absolute;
  top: 5px;
  width: 24px;
  height: 6px;
  background: #000;
  border-radius: 3px;
  z-index: 2;
}

.mini-screen {
  width: 100%;
  height: 100%;
  border-radius: 14px;
  background: #09090b;
  overflow: hidden;
  display: flex;
  align-items: center;
  justify-content: center;
}

.mini-screen-online {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
  padding: 8px 2px;
  color: #ffffff;
}

.mini-screen-text {
  font-size: 9px;
  font-weight: 600;
  color: #38bdf8;
  text-align: center;
}

.mini-screen-port {
  font-size: 8px;
  color: #94a3b8;
  font-family: monospace;
}

.mini-screen-offline {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
  color: #71717a;
}

.offline-icon {
  font-size: 16px;
}

.offline-lbl {
  font-size: 8px;
}

.mini-home-bar {
  position: absolute;
  bottom: 5px;
  width: 32px;
  height: 2px;
  background: rgba(255, 255, 255, 0.7);
  border-radius: 1px;
}

/* 参数规格表格 */
.specs-grid {
  display: flex;
  flex-direction: column;
  gap: 5px;
}

.spec-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 12px;
}

.spec-label {
  color: var(--c-text-secondary, #64748b);
}

.spec-val {
  color: var(--c-text, #0f172a);
  font-weight: 500;
  display: flex;
  align-items: center;
  gap: 4px;
}

.battery-spec-val {
  display: flex;
  align-items: center;
  gap: 4px;
}

.charging-icon {
  color: #52c41a;
  font-size: 11px;
}

.copy-btn {
  font-size: 11px;
  color: #94a3b8;
  cursor: pointer;
}

.copy-btn:hover {
  color: var(--c-primary, #1677ff);
}

.text-primary { color: var(--c-primary, #1677ff) !important; }
.text-success { color: #52c41a !important; }
.text-warning { color: #fa8c16 !important; }
.text-danger { color: #ff4d4f !important; }
.text-muted { color: #94a3b8 !important; }
.font-semibold { font-weight: 600; }

/* 底部操作区 */
.card-footer-actions {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding-top: 10px;
  border-top: 1px solid var(--c-border-subtle, #f1f5f9);
}

.mini-pill-tag {
  font-size: 10px;
  line-height: 18px;
  padding: 0 6px;
  border-radius: 4px;
}
</style>
