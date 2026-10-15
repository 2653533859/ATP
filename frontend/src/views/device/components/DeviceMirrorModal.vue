<template>
  <a-modal
    v-model:open="visible"
    :title="title"
    :width="mirrorModalWidth"
    centered
    :footer="null"
    :destroy-on-close="true"
    @cancel="handleClose"
  >
    <div class="mirror-workspace">
      <div
        class="mirror-container"
        :class="{
          'mirror-container-ready': isScrcpyLive || Boolean(mirrorSrc),
          'mirror-container-landscape': isLandscapeMirror,
        }"
      >
        <div class="mirror-screen-wrapper" :class="{ 'wrapper-landscape': isLandscapeMirror }">
          <canvas
            ref="scrcpyCanvasRef"
            v-show="isScrcpyLive"
            class="mirror-canvas"
            :style="mirrorScreenStyle"
            draggable="false"
            @mousedown="onCanvasMouseDown"
          ></canvas>
          <img
            v-if="!isScrcpyLive && mirrorSrc"
            ref="screenImgRef"
            :src="mirrorSrc"
            alt="Android 设备画面"
            class="mirror-img"
            :style="mirrorScreenStyle"
            draggable="false"
            @load="onImgLoaded"
            @mousedown="onScreenMouseDown"
            @mouseup="onScreenMouseUp"
            @error="onMirrorError"
          />
          <span
            v-if="ripple.visible"
            class="touch-ripple"
            :style="{ left: `${ripple.x}px`, top: `${ripple.y}px` }"
          ></span>
        </div>
        <div v-if="!isScrcpyLive && !mirrorSrc" class="mirror-placeholder">
          <a-spin tip="正在连接设备画面..." />
        </div>
      </div>

      <!-- 快捷导航栏 (Back, Home, Recents, Power, Vol+, Vol-) -->
      <div class="mirror-nav-bar">
        <a-tooltip title="返回键 (Back)">
          <button class="nav-key-btn" @click="sendKeyEvent(4)">
            <LeftOutlined />
          </button>
        </a-tooltip>
        <a-tooltip title="主屏幕 (Home)">
          <button class="nav-key-btn" @click="sendKeyEvent(3)">
            <HomeOutlined />
          </button>
        </a-tooltip>
        <a-tooltip title="多任务 (Recent Apps)">
          <button class="nav-key-btn" @click="sendKeyEvent(187)">
            <AppstoreOutlined />
          </button>
        </a-tooltip>
        <a-tooltip title="电源键 (Power)">
          <button class="nav-key-btn" @click="sendKeyEvent(26)">
            <PoweroffOutlined />
          </button>
        </a-tooltip>
        <a-tooltip title="音量加">
          <button class="nav-key-btn" @click="sendKeyEvent(24)">
            <PlusOutlined />
          </button>
        </a-tooltip>
        <a-tooltip title="音量减">
          <button class="nav-key-btn" @click="sendKeyEvent(25)">
            <MinusOutlined />
          </button>
        </a-tooltip>
      </div>

      <!-- 快捷文本输入行 -->
      <div class="mirror-text-bar">
        <a-input
          v-model:value="quickInputText"
          placeholder="输入文字按回车发送到手机"
          size="small"
          allow-clear
          @pressEnter="sendQuickText"
        >
          <template #suffix>
            <a-button type="link" size="small" style="padding: 0" @click="sendQuickText">
              <SendOutlined />
            </a-button>
          </template>
        </a-input>
      </div>

      <!-- 底部状态栏 -->
      <div class="mirror-footer">
        <div class="mirror-footer-left">
          <a-button
            size="small"
            :type="isScrcpyLive ? 'default' : 'primary'"
            :ghost="!isScrcpyLive"
            :disabled="!props.device"
            @click="handleReconnectStream"
          >
            <ReloadOutlined /> 重连极速流
          </a-button>
          <a-button
            v-if="!isScrcpyLive"
            size="small"
            :disabled="!props.device"
            @click="() => refreshMirror()"
          >
            刷新截图
          </a-button>
          <a-radio-group v-model:value="mirrorScaleMode" size="small" button-style="solid">
            <a-radio-button value="auto">标准</a-radio-button>
            <a-radio-button value="large">大屏</a-radio-button>
            <a-radio-button value="max">超宽</a-radio-button>
          </a-radio-group>
          <span class="res-info" v-if="realResolution.w">
            {{ realResolution.w }}×{{ realResolution.h }}
          </span>
        </div>
        <span style="color: var(--c-text-tertiary); font-size: 12px">
          <template v-if="isScrcpyLive">
            <span style="color: #52c41a; font-weight: bold">● scrcpy 极速实时流 ({{ currentFps }} FPS)</span> · 原生零延迟触控
          </template>
          <template v-else-if="mirrorSrc">
            <span style="color: #faad14; font-weight: 500">● 截图降级模式</span> · 点击「重连极速流」恢复
          </template>
          <template v-else>
            {{ isInteracting ? '正在执行触控...' : '正在建立 scrcpy 极速流通道...' }}
          </template>
        </span>
      </div>
    </div>
  </a-modal>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { message } from 'ant-design-vue'
import {
  AppstoreOutlined,
  HomeOutlined,
  LeftOutlined,
  MinusOutlined,
  PlusOutlined,
  PoweroffOutlined,
  ReloadOutlined,
  SendOutlined,
} from '@ant-design/icons-vue'
import { deviceApi, type DeviceItem } from '@/api'
import { isWebCodecsSupported, useWebCodecsDecoder } from '@/composables/useWebCodecsDecoder'

const props = withDefaults(
  defineProps<{
    open: boolean
    device: DeviceItem | null
    canModify?: boolean
  }>(),
  {
    canModify: true,
  },
)

const emit = defineEmits<{
  (e: 'update:open', val: boolean): void
  (e: 'close'): void
}>()

const visible = computed({
  get: () => props.open,
  set: (val: boolean) => emit('update:open', val),
})

const title = computed(() => {
  const d = props.device
  if (!d) return '设备投屏'
  const brandModel = `${d.brand ?? ''} ${d.model ?? d.name ?? ''}`.trim()
  return brandModel ? `设备投屏 · ${brandModel}` : `设备投屏 · ${d.serial}`
})

const screenImgRef = ref<HTMLImageElement | null>(null)
const scrcpyCanvasRef = ref<HTMLCanvasElement | null>(null)
const mirrorSrc = ref<string | null>(null)
let mirrorObjectUrl: string | null = null
let mirrorTimer: ReturnType<typeof setInterval> | null = null
let mirrorSession = 0
let mirrorRefreshing = false

const realResolution = ref({ w: 0, h: 0 })
const mirrorScaleMode = ref<'auto' | 'large' | 'max'>('large')

const isLandscapeMirror = computed(
  () => realResolution.value.w > realResolution.value.h && realResolution.value.h > 0,
)

const mirrorModalWidth = computed(() => {
  if (isLandscapeMirror.value) {
    if (mirrorScaleMode.value === 'max') return 'min(96vw, 1440px)'
    if (mirrorScaleMode.value === 'large') return 'min(92vw, 1160px)'
    return 'min(88vw, 920px)'
  }
  if (mirrorScaleMode.value === 'max') return 'min(94vw, 760px)'
  if (mirrorScaleMode.value === 'large') return 'min(90vw, 620px)'
  return 'min(88vw, 500px)'
})

const mirrorScreenStyle = computed(() => {
  const maxVh =
    mirrorScaleMode.value === 'max' ? 82 : mirrorScaleMode.value === 'large' ? 74 : 64
  const w = realResolution.value.w || (isLandscapeMirror.value ? 1280 : 720)
  const h = realResolution.value.h || (isLandscapeMirror.value ? 800 : 1280)
  const ratio = (w / h).toFixed(4)
  return {
    width: `min(100%, calc(${maxVh}vh * ${ratio}))`,
    height: 'auto',
    maxHeight: `${maxVh}vh`,
  }
})

const quickInputText = ref('')
const isInteracting = ref(false)
const ripple = ref({ visible: false, x: 0, y: 0 })
let dragStartPos = { x: 0, y: 0, time: 0 }

const isScrcpyLive = ref(false)
const currentFps = ref(0)
let scrcpyDecoder: ReturnType<typeof useWebCodecsDecoder> | null = null
let scrcpyWs: WebSocket | null = null
let isMouseDown = false
let lastMoveSentAt = 0
let fpsCount = 0
let fpsTimer: ReturnType<typeof setInterval> | null = null
let scrcpyFallbackTimer: ReturnType<typeof setTimeout> | null = null
let scrcpyInitTimer: ReturnType<typeof setTimeout> | null = null
let rippleTimer: ReturnType<typeof setTimeout> | null = null

function triggerScreenshotFallback(session: number) {
  if (!props.open || session !== mirrorSession || isScrcpyLive.value) return
  refreshMirror(session)
  startMirrorPolling()
}

function initScrcpyStream(serial: string) {
  closeScrcpyStream()
  const activeSession = mirrorSession
  if (!isWebCodecsSupported() || !scrcpyCanvasRef.value) {
    triggerScreenshotFallback(activeSession)
    return
  }

  scrcpyDecoder = useWebCodecsDecoder({
    canvas: scrcpyCanvasRef.value,
    fpsHint: 60,
    onFrameDecoded: () => {
      fpsCount++
      if (!isScrcpyLive.value) {
        isScrcpyLive.value = true
        stopMirrorPolling()
        if (scrcpyFallbackTimer) {
          clearTimeout(scrcpyFallbackTimer)
          scrcpyFallbackTimer = null
        }
      }
      if (scrcpyCanvasRef.value?.width && scrcpyCanvasRef.value?.height) {
        const w = scrcpyCanvasRef.value.width
        const h = scrcpyCanvasRef.value.height
        if ((w > 300 || h > 150) && (realResolution.value.w !== w || realResolution.value.h !== h)) {
          realResolution.value = { w, h }
        }
      }
    },
    onFallback: () => {
      closeScrcpyStream()
      triggerScreenshotFallback(activeSession)
    },
  })

  fpsTimer = setInterval(() => {
    currentFps.value = fpsCount
    fpsCount = 0
  }, 1000)

  // 如果 5 秒内未收到首帧，自动启用截图轮询兜底
  scrcpyFallbackTimer = setTimeout(() => {
    if (!isScrcpyLive.value) {
      triggerScreenshotFallback(activeSession)
    }
  }, 5000)

  const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
  const wsUrl = `${proto}//${window.location.host}/ws/scrcpy/${encodeURIComponent(serial)}`

  scrcpyWs = new WebSocket(wsUrl)
  scrcpyWs.binaryType = 'arraybuffer'

  scrcpyWs.onmessage = (event) => {
    if (event.data instanceof ArrayBuffer) {
      scrcpyDecoder?.push(new Uint8Array(event.data))
    }
  }

  scrcpyWs.onclose = () => {
    closeScrcpyStream()
    triggerScreenshotFallback(activeSession)
  }

  scrcpyWs.onerror = () => {
    closeScrcpyStream()
    triggerScreenshotFallback(activeSession)
  }
}

function closeScrcpyStream() {
  if (scrcpyInitTimer) {
    clearTimeout(scrcpyInitTimer)
    scrcpyInitTimer = null
  }
  if (scrcpyFallbackTimer) {
    clearTimeout(scrcpyFallbackTimer)
    scrcpyFallbackTimer = null
  }
  if (fpsTimer) {
    clearInterval(fpsTimer)
    fpsTimer = null
  }
  if (scrcpyWs) {
    try {
      scrcpyWs.onclose = null
      scrcpyWs.onerror = null
      scrcpyWs.close()
    } catch {}
    scrcpyWs = null
  }
  if (scrcpyDecoder) {
    scrcpyDecoder.destroy()
    scrcpyDecoder = null
  }
  removeWindowMouseListeners()
  isScrcpyLive.value = false
  currentFps.value = 0
}

function handleReconnectStream() {
  if (!props.device) return
  stopMirrorPolling()
  initScrcpyStream(props.device.serial)
}

function getCanvasCoords(e: MouseEvent) {
  const canvas = scrcpyCanvasRef.value
  if (!canvas) return { x: 0, y: 0, w: 600, h: 960 }
  const rect = canvas.getBoundingClientRect()
  const w = canvas.width || realResolution.value.w || 600
  const h = canvas.height || realResolution.value.h || 960
  const clientX = Math.min(Math.max(0, e.clientX - rect.left), rect.width)
  const clientY = Math.min(Math.max(0, e.clientY - rect.top), rect.height)
  const scaleX = w / Math.max(1, rect.width)
  const scaleY = h / Math.max(1, rect.height)
  return {
    x: Math.round(clientX * scaleX),
    y: Math.round(clientY * scaleY),
    w,
    h,
  }
}

function sendWsTouch(action: 0 | 1 | 2, coords: { x: number; y: number; w: number; h: number }) {
  if (scrcpyWs && scrcpyWs.readyState === WebSocket.OPEN) {
    scrcpyWs.send(
      JSON.stringify({
        type: 'touch',
        action,
        x: coords.x,
        y: coords.y,
        w: coords.w,
        h: coords.h,
      }),
    )
    return true
  }
  return false
}

function onCanvasMouseDown(e: MouseEvent) {
  if (e.button !== 0 || !props.device) return
  isMouseDown = true
  const coords = getCanvasCoords(e)
  showRipple(e.clientX, e.clientY)
  sendWsTouch(0, coords)
  window.addEventListener('mousemove', onWindowMouseMove)
  window.addEventListener('mouseup', onWindowMouseUp)
}

function onWindowMouseMove(e: MouseEvent) {
  if (!props.device || !isMouseDown) return
  const now = performance.now()
  if (now - lastMoveSentAt < 14) return
  lastMoveSentAt = now
  const coords = getCanvasCoords(e)
  sendWsTouch(2, coords)
}

function onWindowMouseUp(e: MouseEvent) {
  if (!isMouseDown) return
  isMouseDown = false
  window.removeEventListener('mousemove', onWindowMouseMove)
  window.removeEventListener('mouseup', onWindowMouseUp)
  if (!props.device) return
  const coords = getCanvasCoords(e)
  sendWsTouch(1, coords)
}

function removeWindowMouseListeners() {
  if (isMouseDown) {
    isMouseDown = false
  }
  window.removeEventListener('mousemove', onWindowMouseMove)
  window.removeEventListener('mouseup', onWindowMouseUp)
}

function onImgLoaded() {
  if (screenImgRef.value) {
    const naturalW = screenImgRef.value.naturalWidth
    const naturalH = screenImgRef.value.naturalHeight
    if (naturalW && naturalH) {
      realResolution.value = { w: naturalW, h: naturalH }
    }
  }
}

function showRipple(clientX: number, clientY: number) {
  const surface = isScrcpyLive.value ? scrcpyCanvasRef.value : screenImgRef.value
  if (!surface) return
  const rect = (surface.parentElement ?? surface).getBoundingClientRect()
  if (rippleTimer) {
    clearTimeout(rippleTimer)
  }
  ripple.value = {
    visible: true,
    x: clientX - rect.left,
    y: clientY - rect.top,
  }
  rippleTimer = setTimeout(() => {
    ripple.value.visible = false
    rippleTimer = null
  }, 350)
}

function onScreenMouseDown(e: MouseEvent) {
  if (!screenImgRef.value || !props.device) return
  const rect = screenImgRef.value.getBoundingClientRect()
  dragStartPos = {
    x: e.clientX - rect.left,
    y: e.clientY - rect.top,
    time: Date.now(),
  }
}

async function onScreenMouseUp(e: MouseEvent) {
  if (!screenImgRef.value || !props.device) return
  const rect = screenImgRef.value.getBoundingClientRect()
  const endX = e.clientX - rect.left
  const endY = e.clientY - rect.top
  const duration = Math.max(100, Math.min(Date.now() - dragStartPos.time, 1500))

  const devW = realResolution.value.w || screenImgRef.value.naturalWidth || 1080
  const devH = realResolution.value.h || screenImgRef.value.naturalHeight || 1920

  const scaleX = devW / rect.width
  const scaleY = devH / rect.height

  const dx = endX - dragStartPos.x
  const dy = endY - dragStartPos.y
  const distance = Math.hypot(dx, dy)

  const realStartX = Math.round(dragStartPos.x * scaleX)
  const realStartY = Math.round(dragStartPos.y * scaleY)
  const realEndX = Math.round(endX * scaleX)
  const realEndY = Math.round(endY * scaleY)

  showRipple(e.clientX, e.clientY)

  isInteracting.value = true
  try {
    if (distance < 10) {
      await deviceApi.tap(props.device.id, { x: realStartX, y: realStartY })
    } else {
      await deviceApi.swipe(props.device.id, {
        x1: realStartX,
        y1: realStartY,
        x2: realEndX,
        y2: realEndY,
        duration_ms: duration,
      })
    }
    setTimeout(() => {
      refreshMirror(mirrorSession)
    }, 150)
  } catch (err: unknown) {
    const messageText = err && typeof err === 'object' && 'message' in err ? String(err.message) : '请检查设备'
    message.warning(`操作未生效: ${messageText}`)
  } finally {
    isInteracting.value = false
  }
}

async function sendKeyEvent(keycode: number | string) {
  if (!props.device) return
  if (isScrcpyLive.value && scrcpyWs && scrcpyWs.readyState === WebSocket.OPEN) {
    scrcpyWs.send(JSON.stringify({ type: 'key', keycode: Number(keycode) }))
    return
  }
  try {
    await deviceApi.keyevent(props.device.id, keycode)
    if (!isScrcpyLive.value) {
      setTimeout(() => {
        refreshMirror(mirrorSession)
      }, 150)
    }
  } catch (err: unknown) {
    const msg = err && typeof err === 'object' && 'message' in err ? String(err.message) : String(err)
    message.warning(`按键未响应: ${msg}`)
  }
}

async function sendQuickText() {
  const text = quickInputText.value.trim()
  if (!text || !props.device) return
  if (isScrcpyLive.value && scrcpyWs && scrcpyWs.readyState === WebSocket.OPEN) {
    scrcpyWs.send(JSON.stringify({ type: 'text', text }))
    quickInputText.value = ''
    return
  }
  try {
    await deviceApi.inputText(props.device.id, text)
    quickInputText.value = ''
    if (!isScrcpyLive.value) {
      setTimeout(() => {
        refreshMirror(mirrorSession)
      }, 200)
    }
  } catch (err: unknown) {
    const msg = err && typeof err === 'object' && 'message' in err ? String(err.message) : String(err)
    message.warning(`文字发送失败: ${msg}`)
  }
}

function startMirror() {
  if (!props.device) return
  cleanupMirror()
  mirrorSession += 1
  if (props.device.resolution) {
    const match = props.device.resolution.match(/(\d+)x(\d+)/)
    if (match) {
      realResolution.value = { w: parseInt(match[1]), h: parseInt(match[2]) }
    }
  } else {
    realResolution.value = { w: 0, h: 0 }
  }
  const activeSession = mirrorSession
  scrcpyInitTimer = setTimeout(() => {
    scrcpyInitTimer = null
    if (!props.open || activeSession !== mirrorSession || !props.device) return
    initScrcpyStream(props.device.serial)
  }, 60)
}

function cleanupMirror() {
  mirrorSession += 1
  realResolution.value = { w: 0, h: 0 }
  closeScrcpyStream()
  stopMirrorPolling()
  revokeMirrorUrl()
}

function revokeMirrorUrl() {
  if (mirrorObjectUrl) {
    URL.revokeObjectURL(mirrorObjectUrl)
    mirrorObjectUrl = null
  }
  mirrorSrc.value = null
}

async function refreshMirror(session = mirrorSession) {
  if (!props.device || mirrorRefreshing || session !== mirrorSession) return
  mirrorRefreshing = true
  try {
    const blob = await deviceApi.screenshot(props.device.id)
    if (session !== mirrorSession) return
    const nextUrl = URL.createObjectURL(blob)
    const prevUrl = mirrorObjectUrl
    mirrorObjectUrl = nextUrl
    mirrorSrc.value = nextUrl
    if (prevUrl) URL.revokeObjectURL(prevUrl)
  } catch {
    // 忽略 ADB 偶尔抖动
  } finally {
    mirrorRefreshing = false
  }
}

function onMirrorError() {
  revokeMirrorUrl()
}

function startMirrorPolling() {
  stopMirrorPolling()
  const activeSession = mirrorSession
  mirrorTimer = setInterval(() => {
    refreshMirror(activeSession)
  }, 350)
}

function stopMirrorPolling() {
  if (mirrorTimer !== null) {
    clearInterval(mirrorTimer)
    mirrorTimer = null
  }
}

function handleClose() {
  cleanupMirror()
  emit('update:open', false)
  emit('close')
}

watch(
  () => props.open,
  (val) => {
    if (val && props.device) {
      startMirror()
    } else {
      cleanupMirror()
    }
  },
  { immediate: true },
)

watch(
  () => props.device?.id,
  (newId, oldId) => {
    if (props.open && newId && newId !== oldId && props.device) {
      startMirror()
    }
  },
)

onBeforeUnmount(() => {
  cleanupMirror()
})
</script>

<style scoped>
.mirror-workspace {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 10px;
}
.mirror-container {
  display: flex;
  justify-content: center;
  align-items: center;
  min-height: 360px;
  background: #0d0d12;
  border-radius: 10px;
  overflow: hidden;
  user-select: none;
  border: 1px solid var(--c-border);
  width: 100%;
  transition: all 0.2s ease;
}
.mirror-container.mirror-container-ready {
  min-height: 0;
}
.mirror-screen-wrapper {
  position: relative;
  display: inline-flex;
  justify-content: center;
  align-items: center;
  cursor: crosshair;
  line-height: 0;
  width: 100%;
}
.mirror-img {
  max-width: 100%;
  object-fit: contain;
  display: block;
}
.mirror-canvas {
  max-width: 100%;
  object-fit: contain;
  display: block;
  cursor: crosshair;
}
.touch-ripple {
  position: absolute;
  width: 24px;
  height: 24px;
  border-radius: 50%;
  background: rgba(22, 119, 255, 0.45);
  border: 2px solid #fff;
  transform: translate(-50%, -50%) scale(1);
  pointer-events: none;
  animation: ripple-anim 0.35s ease-out forwards;
}
@keyframes ripple-anim {
  0% { transform: translate(-50%, -50%) scale(0.6); opacity: 0.9; }
  100% { transform: translate(-50%, -50%) scale(1.6); opacity: 0; }
}
.mirror-nav-bar {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 10px;
  width: 100%;
  padding: 6px 12px;
  background: var(--c-bg-elevated);
  border-radius: 8px;
  border: 1px solid var(--c-border);
}
.nav-key-btn {
  background: transparent;
  border: none;
  cursor: pointer;
  font-size: 15px;
  color: var(--c-text);
  padding: 6px 12px;
  border-radius: 6px;
  transition: all 0.2s;
  display: flex;
  align-items: center;
  justify-content: center;
}
.nav-key-btn:hover {
  background: var(--c-bg-hover, rgba(0, 0, 0, 0.06));
  color: var(--c-primary);
}
.mirror-text-bar {
  width: 100%;
}
.mirror-placeholder {
  display: flex;
  justify-content: center;
  align-items: center;
  height: 480px;
  color: var(--c-text-tertiary);
}
.mirror-footer {
  width: 100%;
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-top: 4px;
}
.mirror-footer-left {
  display: flex;
  align-items: center;
  gap: 8px;
}
.res-info {
  font-size: 11px;
  color: var(--c-text-tertiary);
}
</style>
