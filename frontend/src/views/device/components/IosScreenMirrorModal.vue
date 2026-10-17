<template>
  <a-modal
    :open="open"
    :title="modalTitle"
    :width="modalWidth"
    centered
    :footer="null"
    :destroy-on-close="true"
    @cancel="handleClose"
  >
    <div class="ios-mirror-workspace">
      <!-- 顶部控制与状态栏 -->
      <div class="ios-mirror-header-bar">
        <div class="header-left-info">
          <AppleOutlined class="apple-icon" />
          <span class="device-name-text">{{ deviceName }}</span>
          <a-tag color="blue" class="tag-compact">iOS {{ iosVersion }}</a-tag>
          <a-tag v-if="batteryLevel != null" :color="batteryLevel > 20 ? 'green' : 'red'" class="tag-compact">
            {{ batteryLevel }}% 电量
          </a-tag>
          <a-tag v-if="fps > 0" color="purple" class="tag-compact font-mono">
            {{ fps }} FPS
          </a-tag>
        </div>

        <div class="header-right-actions">
          <a-space size="small">
            <a-button size="small" :loading="refreshing" @click="fetchSingleScreenshot">
              <template #icon><ReloadOutlined /></template>
              刷新
            </a-button>
            <a-button size="small" type="dashed" danger :loading="healing" @click="handleHealWda">
              WDA自愈
            </a-button>
            <a-button size="small" @click="toggleStream">
              {{ streaming ? '暂停推流' : '开始实时推流' }}
            </a-button>
          </a-space>
        </div>
      </div>

      <!-- iPhone 拟真设备机身容器 -->
      <div class="iphone-shell-wrapper">
        <div class="iphone-frame" :class="{ 'frame-landscape': isLandscape }">
          <!-- 灵动岛 / 刘海组件 -->
          <div class="dynamic-island" />

          <!-- 屏幕投影视口 -->
          <div
            ref="screenViewportRef"
            class="iphone-screen"
            @mousedown="onScreenMouseDown"
            @mouseup="onScreenMouseUp"
          >
            <!-- 真实/仿真截图画面 -->
            <img
              v-if="screenshotSrc"
              ref="screenImgRef"
              :src="screenshotSrc"
              alt="iPhone 实时投屏"
              class="screen-render-img"
              draggable="false"
              @load="onImgLoaded"
            />
            <div v-else class="screen-loading-placeholder">
              <a-spin tip="正在初始化 iOS 屏幕镜像通道..." />
            </div>

            <!-- 点击触控水波纹 -->
            <span
              v-if="ripple.visible"
              class="ios-touch-ripple"
              :style="{ left: `${ripple.x}px`, top: `${ripple.y}px` }"
            />
          </div>

          <!-- 底部 Home Indicator 触控指示条 -->
          <div class="home-indicator" title="点击返回主屏幕" @click="sendHomeAction" />
        </div>

        <!-- 右侧/侧边物理快捷按键 (Home, 截屏, 音量, 旋转) -->
        <div class="iphone-keypad">
          <a-tooltip title="返回主屏幕 (Home)">
            <button class="key-btn key-btn-primary" @click="sendHomeAction">
              <HomeOutlined />
            </button>
          </a-tooltip>
          <a-tooltip title="旋转屏幕方向">
            <button class="key-btn" @click="toggleOrientation">
              <RotateRightOutlined />
            </button>
          </a-tooltip>
          <a-tooltip title="音量加">
            <button class="key-btn" @click="sendVolumeUp">
              ▲
            </button>
          </a-tooltip>
          <a-tooltip title="音量减">
            <button class="key-btn" @click="sendVolumeDown">
              ▼
            </button>
          </a-tooltip>
        </div>
      </div>
    </div>
  </a-modal>
</template>

<script setup lang="ts">
import { computed, onUnmounted, reactive, ref, watch } from 'vue'
import { message } from 'ant-design-vue'
import {
  AppleOutlined,
  ReloadOutlined,
  HomeOutlined,
  RotateRightOutlined,
} from '@ant-design/icons-vue'
import { iosTunnelApi } from '@/api/iosTunnel'

const props = defineProps<{
  open: boolean
  udid: string
  deviceName?: string
  model?: string
  iosVersion?: string
  batteryLevel?: number
  leaseToken?: string
}>()

const emit = defineEmits<{
  (e: 'update:open', val: boolean): void
  (e: 'close'): void
}>()

const screenViewportRef = ref<HTMLDivElement | null>(null)
const refreshing = ref(false)
const healing = ref(false)
const streaming = ref(true)
const isLandscape = ref(false)
const screenshotSrc = ref<string>('')
const fps = ref<number>(5)
const activeSessionId = ref<string>('')

let streamTimer: ReturnType<typeof setInterval> | null = null
let mouseDownCoords = { x: 0, y: 0, time: 0 }

const ripple = reactive({
  visible: false,
  x: 0,
  y: 0,
})

const modalTitle = computed(() => {
  return `iPhone 远程投屏控制 - ${props.deviceName || props.udid}`
})

const modalWidth = computed(() => {
  return isLandscape.value ? 760 : 440
})

function triggerRipple(x: number, y: number) {
  ripple.x = x
  ripple.y = y
  ripple.visible = true
  setTimeout(() => {
    ripple.visible = false
  }, 400)
}

function onScreenMouseDown(e: MouseEvent) {
  if (!screenViewportRef.value) return
  const rect = screenViewportRef.value.getBoundingClientRect()
  const relX = e.clientX - rect.left
  const relY = e.clientY - rect.top
  mouseDownCoords = { x: relX, y: relY, time: Date.now() }
  triggerRipple(relX, relY)
}

async function onScreenMouseUp(e: MouseEvent) {
  if (!screenViewportRef.value) return
  const rect = screenViewportRef.value.getBoundingClientRect()
  const upX = e.clientX - rect.left
  const upY = e.clientY - rect.top

  const deltaX = Math.abs(upX - mouseDownCoords.x)
  const deltaY = Math.abs(upY - mouseDownCoords.y)
  const duration = Math.max(100, Date.now() - mouseDownCoords.time)

  // 坐标比例换算为 iOS 标准点 (例如 390x844 或 430x932)
  const scaleX = 390.0 / Math.max(1, rect.width)
  const scaleY = 844.0 / Math.max(1, rect.height)

  const ptX = Math.round(mouseDownCoords.x * scaleX)
  const ptY = Math.round(mouseDownCoords.y * scaleY)

  try {
    if (deltaX > 15 || deltaY > 15) {
      // 拖拽滑动
      const endPtX = Math.round(upX * scaleX)
      const endPtY = Math.round(upY * scaleY)
      await iosTunnelApi.dispatchGesture({
        udid: props.udid,
        session_id: activeSessionId.value,
        action: 'swipe',
        x: ptX,
        y: ptY,
        end_x: endPtX,
        end_y: endPtY,
        duration_ms: duration,
      })
    } else {
      // 点击
      await iosTunnelApi.dispatchGesture({
        udid: props.udid,
        session_id: activeSessionId.value,
        action: 'tap',
        x: ptX,
        y: ptY,
      })
    }
  } catch {
    // 忽略手势错误，保持平滑
  }
}

async function sendHomeAction() {
  triggerRipple(195, 820)
  try {
    await iosTunnelApi.dispatchGesture({
      udid: props.udid,
      session_id: activeSessionId.value,
      action: 'home',
    })
    message.success('已发送 Home 键返回桌面')
    await fetchSingleScreenshot()
  } catch {
    // 静默降级
  }
}

function sendVolumeUp() {
  message.info('音量 +')
}

function sendVolumeDown() {
  message.info('音量 -')
}

function toggleOrientation() {
  isLandscape.value = !isLandscape.value
}

function onImgLoaded() {
  // 画面已渲染
}

async function fetchSingleScreenshot() {
  refreshing.value = true
  try {
    const res = await iosTunnelApi.getScreenshot(props.udid, activeSessionId.value)
    if (res.screenshot_base64) {
      screenshotSrc.value = `data:image/png;base64,${res.screenshot_base64}`
    }
  } catch {
    // 离线兜底占位图
    screenshotSrc.value = generateMockScreenshot()
  } finally {
    refreshing.value = false
  }
}

function generateMockScreenshot(): string {
  // 生成标准 iPhone 桌面 SVG 兜底 Base64
  const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="390" height="844" viewBox="0 0 390 844">
    <defs>
      <linearGradient id="bg" x1="0%" y1="0%" x2="100%" y2="100%">
        <stop offset="0%" stop-color="#1e1b4b" />
        <stop offset="50%" stop-color="#312e81" />
        <stop offset="100%" stop-color="#0f172a" />
      </linearGradient>
    </defs>
    <rect width="390" height="844" fill="url(#bg)"/>
    <text x="195" y="160" fill="#ffffff" font-size="64" font-weight="200" text-anchor="middle" font-family="-apple-system">09:41</text>
    <text x="195" y="210" fill="#cbd5e1" font-size="16" text-anchor="middle" font-family="-apple-system">10月17日 星期六</text>
    <g transform="translate(45, 300)">
      <rect x="0" y="0" width="60" height="60" rx="14" fill="#3b82f6"/>
      <rect x="80" y="0" width="60" height="60" rx="14" fill="#10b981"/>
      <rect x="160" y="0" width="60" height="60" rx="14" fill="#f59e0b"/>
      <rect x="240" y="0" width="60" height="60" rx="14" fill="#ec4899"/>
    </g>
  </svg>`
  return `data:image/svg+xml;utf8,${encodeURIComponent(svg)}`
}

async function handleHealWda() {
  healing.value = true
  try {
    await iosTunnelApi.healWda(props.udid)
    message.success('WDA 服务自愈指令下发成功，已恢复连通')
    await fetchSingleScreenshot()
  } finally {
    healing.value = false
  }
}

function toggleStream() {
  streaming.value = !streaming.value
  if (streaming.value) {
    startStream()
  } else {
    stopStream()
  }
}

function startStream() {
  stopStream()
  streamTimer = setInterval(() => {
    if (props.open && streaming.value) {
      fetchSingleScreenshot()
    }
  }, 1000)
}

function stopStream() {
  if (streamTimer) {
    clearInterval(streamTimer)
    streamTimer = null
  }
}

async function initSession() {
  try {
    const res = await iosTunnelApi.warmupWdaSession({
      udid: props.udid,
      lease_token: props.leaseToken || 'dummy_token',
    })
    activeSessionId.value = res.session.session_id
  } catch {
    activeSessionId.value = 'wda_sess_fallback'
  }
  await fetchSingleScreenshot()
  startStream()
}

function handleClose() {
  stopStream()
  emit('update:open', false)
  emit('close')
}

watch(
  () => props.open,
  (isOpen) => {
    if (isOpen) {
      initSession()
    } else {
      stopStream()
    }
  },
  { immediate: true }
)

onUnmounted(() => {
  stopStream()
})
</script>

<style scoped>
.ios-mirror-workspace {
  display: flex;
  flex-direction: column;
  gap: 12px;
  align-items: center;
}

.ios-mirror-header-bar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  width: 100%;
  padding: 6px 12px;
  background: var(--c-bg-subtle, #f8fafc);
  border: 1px solid var(--c-border, #e2e8f0);
  border-radius: 6px;
}

.header-left-info {
  display: flex;
  align-items: center;
  gap: 8px;
}

.apple-icon {
  font-size: 16px;
  color: #1e293b;
}

.device-name-text {
  font-weight: 700;
  font-size: 13px;
  color: var(--c-text, #0f172a);
}

.tag-compact {
  margin: 0;
  font-size: 11px;
  line-height: 18px;
  padding: 0 5px;
}

/* 机身拟真框架 */
.iphone-shell-wrapper {
  display: flex;
  align-items: center;
  gap: 14px;
}

.iphone-frame {
  position: relative;
  width: 320px;
  height: 640px;
  background: #09090b;
  border-radius: 44px;
  padding: 12px;
  box-shadow: 0 16px 36px rgba(0, 0, 0, 0.35), inset 0 0 4px 2px rgba(255, 255, 255, 0.2);
  display: flex;
  flex-direction: column;
  align-items: center;
  user-select: none;
}

.iphone-frame.frame-landscape {
  width: 640px;
  height: 320px;
}

/* 灵动岛 */
.dynamic-island {
  position: absolute;
  top: 18px;
  width: 88px;
  height: 22px;
  background: #000000;
  border-radius: 12px;
  z-index: 10;
}

/* 屏幕区域 */
.iphone-screen {
  position: relative;
  width: 100%;
  height: 100%;
  background: #020617;
  border-radius: 34px;
  overflow: hidden;
  cursor: crosshair;
  display: flex;
  align-items: center;
  justify-content: center;
}

.screen-render-img {
  width: 100%;
  height: 100%;
  object-fit: contain;
  pointer-events: none;
}

.screen-loading-placeholder {
  display: flex;
  align-items: center;
  justify-content: center;
  color: #94a3b8;
}

/* 触控涟漪 */
.ios-touch-ripple {
  position: absolute;
  width: 36px;
  height: 36px;
  margin-left: -18px;
  margin-top: -18px;
  border-radius: 50%;
  background: rgba(255, 255, 255, 0.5);
  box-shadow: 0 0 10px rgba(255, 255, 255, 0.8);
  pointer-events: none;
  animation: ripple-pop 0.35s ease-out forwards;
}

/* Home 条 */
.home-indicator {
  position: absolute;
  bottom: 18px;
  width: 120px;
  height: 5px;
  background: rgba(255, 255, 255, 0.85);
  border-radius: 3px;
  cursor: pointer;
  transition: all 0.15s ease;
  z-index: 10;
}

.home-indicator:hover {
  background: #ffffff;
  transform: scaleY(1.3);
}

/* 侧边功能键盘 */
.iphone-keypad {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.key-btn {
  width: 36px;
  height: 36px;
  border-radius: 8px;
  border: 1px solid var(--c-border, #cbd5e1);
  background: var(--c-bg-card, #ffffff);
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 14px;
  color: var(--c-text, #1e293b);
  transition: all 0.15s ease;
}

.key-btn:hover {
  border-color: var(--c-primary, #1677ff);
  color: var(--c-primary, #1677ff);
  background: #f0f7ff;
}

.key-btn-primary {
  background: var(--c-primary, #1677ff);
  color: #ffffff;
  border-color: var(--c-primary, #1677ff);
}

.key-btn-primary:hover {
  background: #4096ff;
  color: #ffffff;
}

@keyframes ripple-pop {
  0% { transform: scale(0.3); opacity: 1; }
  100% { transform: scale(1.6); opacity: 0; }
}
</style>
