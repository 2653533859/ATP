<template>
  <a-modal
    v-model:open="visible"
    :width="mirrorModalWidth"
    centered
    :footer="null"
    :destroy-on-close="true"
    :mask-closable="false"
    :keyboard="false"
    class="device-mirror-dialog"
    @cancel="handleClose"
  >
    <template #title>
      <div class="mirror-modal-header">
        <div class="header-device-info">
          <MobileOutlined class="device-icon" />
          <span class="device-title-text">{{ title }}</span>
          <a-tag :color="deviceStatusMeta.color" class="header-status-tag">
            {{ deviceStatusMeta.label }}
          </a-tag>
        </div>
        <div class="header-lease-info">
          <a-tooltip :title="leaseTooltip">
            <a-tag :color="hasControlLease ? 'success' : 'warning'" class="header-lease-tag">
              <CheckCircleOutlined v-if="hasControlLease" />
              <LockOutlined v-else />
              {{ hasControlLease ? t('device.mirror_modal.lease_active', { remaining: leaseRemainingText }) : t('device.mirror_modal.lease_readonly') }}
            </a-tag>
          </a-tooltip>
          <a-button
            v-if="!hasControlLease"
            size="small"
            type="primary"
            ghost
            :loading="leaseAcquiring"
            @click="acquireInteractiveLease(false)"
          >
            {{ t('device.mirror_modal.acquire_control') }}
          </a-button>
        </div>
      </div>
    </template>

    <div class="mirror-workspace">
      <a-alert
        v-if="!hasControlLease && leaseError"
        class="mirror-lease-alert"
        type="warning"
        show-icon
        :message="t('device.mirror_modal.lease_alert_message', { reason: leaseError })"
        :description="t('device.mirror_modal.lease_alert_description')"
      >
        <template #action>
          <a-space direction="vertical" size="small">
            <a-button size="small" :loading="leaseAcquiring" @click="acquireInteractiveLease(false)">
              {{ t('device.mirror_modal.retry_acquire') }}
            </a-button>
            <a-button size="small" type="link" :loading="leaseAcquiring" @click="acquireInteractiveLease(false, true)">
              {{ t('device.mirror_modal.takeover_own') }}
            </a-button>
          </a-space>
        </template>
      </a-alert>
      <!-- 手机外框与屏幕容器 -->
      <div
        class="mirror-phone-frame"
        :class="{
          'phone-frame-ready': isScrcpyLive || Boolean(mirrorSrc),
          'phone-frame-landscape': isLandscapeMirror,
        }"
      >
        <div v-if="!isLandscapeMirror" class="phone-earpiece-notch"></div>
        <div
          class="mirror-screen-wrapper"
          :class="{
            'wrapper-landscape': isLandscapeMirror,
            'wrapper-empty': !isScrcpyLive && !mirrorSrc,
          }"
        >
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
            :alt="t('device.screen_alt')"
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
          <span v-if="mirrorError" role="alert">{{ mirrorError }}</span>
          <a-spin v-else :tip="t('device.connecting')" />
        </div>
      </div>

      <!-- 快捷导航栏 (Back, Home, Recents, Power, Vol+, Vol-) -->
      <div class="mirror-nav-bar">
        <div class="nav-btn-group">
          <a-tooltip :title="hasControlLease ? t('device.mirror_modal.key_back') : t('device.mirror_modal.need_control')">
            <button class="nav-key-btn" :disabled="!hasControlLease" @click="sendKeyEvent(4)">
              <LeftOutlined />
            </button>
          </a-tooltip>
          <a-tooltip :title="hasControlLease ? t('device.mirror_modal.key_home') : t('device.mirror_modal.need_control')">
            <button class="nav-key-btn" :disabled="!hasControlLease" @click="sendKeyEvent(3)">
              <HomeOutlined />
            </button>
          </a-tooltip>
          <a-tooltip :title="hasControlLease ? t('device.mirror_modal.key_recents') : t('device.mirror_modal.need_control')">
            <button class="nav-key-btn" :disabled="!hasControlLease" @click="sendKeyEvent(187)">
              <AppstoreOutlined />
            </button>
          </a-tooltip>
        </div>
        <div class="nav-separator"></div>
        <div class="nav-btn-group">
          <a-tooltip :title="hasControlLease ? t('device.mirror_modal.key_power') : t('device.mirror_modal.need_control')">
            <button class="nav-key-btn nav-power-btn" :disabled="!hasControlLease" @click="sendKeyEvent(26)">
              <PoweroffOutlined />
            </button>
          </a-tooltip>
          <a-tooltip :title="hasControlLease ? t('device.mirror_modal.key_volume_down') : t('device.mirror_modal.need_control')">
            <button class="nav-key-btn" :disabled="!hasControlLease" @click="sendKeyEvent(25)">
              <MinusOutlined />
            </button>
          </a-tooltip>
          <a-tooltip :title="hasControlLease ? t('device.mirror_modal.key_volume_up') : t('device.mirror_modal.need_control')">
            <button class="nav-key-btn" :disabled="!hasControlLease" @click="sendKeyEvent(24)">
              <PlusOutlined />
            </button>
          </a-tooltip>
        </div>
      </div>

      <div v-if="canModify && recordable" class="mirror-record-bar">
        <a-button v-if="!recording" size="small" @click="startRecording">{{ t('device.mirror_modal.start_recording') }}</a-button>
        <template v-else>
          <span>{{ t('device.mirror_modal.recorded_count', { count: recordedSteps.length }) }}</span>
          <a-button
            size="small"
            class="pick-assert-btn"
            :type="pickAssertMode ? 'primary' : 'default'"
            :ghost="pickAssertMode"
            :disabled="isInteracting || finishingRecording"
            @click="pickAssertMode = !pickAssertMode"
          >
            {{ pickAssertMode ? t('device.mirror_modal.exit_pick_assert') : t('device.mirror_modal.pick_assert') }}
          </a-button>
          <a-button
            size="small"
            type="primary"
            :loading="finishingRecording"
            :disabled="!recordedSteps.length"
            @click="finishRecording"
          >
            {{ t('device.mirror_modal.edit_recorded_case') }}
          </a-button>
          <a-button size="small" :disabled="finishingRecording" @click="discardRecording">{{ t('device.mirror_modal.discard_recording') }}</a-button>
        </template>
        <a-tooltip :title="t('device.mirror_modal.auto_assert_tooltip')">
          <label class="mirror-auto-assert-toggle">
            <a-switch v-model:checked="autoAssert" size="small" :disabled="finishingRecording" />
            <span>{{ t('device.mirror_modal.auto_assert') }}</span>
          </label>
        </a-tooltip>
      </div>

      <!-- 快捷文本输入行 -->
      <div class="mirror-text-bar">
        <a-input
          v-model:value="quickInputText"
          :type="quickInputSensitive ? 'password' : 'text'"
          :placeholder="quickInputPlaceholder"
          :disabled="!hasControlLease"
          size="small"
          allow-clear
          @pressEnter="sendQuickText"
        >
          <template #prefix>
            <EditOutlined style="color: var(--c-text-tertiary)" />
          </template>
          <template #suffix>
            <a-button
              type="link"
              size="small"
              :disabled="!hasControlLease || !quickInputText.trim()"
              style="padding: 0"
              @click="sendQuickText"
            >
              <SendOutlined />
            </a-button>
          </template>
        </a-input>
        <a-checkbox
          v-model:checked="quickInputSensitive"
          class="mirror-sensitive-toggle"
          :disabled="!hasControlLease"
        >
          {{ t('device.mirror_modal.sensitive_input') }}
        </a-checkbox>
      </div>

      <!-- 底部状态栏 -->
      <div class="mirror-footer">
        <div class="mirror-footer-left">
          <a-space size="small">
            <a-button
              size="small"
              :type="isScrcpyLive ? 'default' : 'primary'"
              :ghost="!isScrcpyLive"
              :disabled="!props.device"
              @click="handleReconnectStream"
            >
              <ReloadOutlined /> {{ t('device.mirror_modal.reconnect_stream') }}
            </a-button>
            <a-button
              v-if="!isScrcpyLive"
              size="small"
              :disabled="!props.device"
              @click="retryScreenshot"
            >
              {{ t('device.refresh_screenshot') }}
            </a-button>
            <a-radio-group v-model:value="mirrorScaleMode" size="small" button-style="solid">
              <a-radio-button value="auto">{{ t('device.mirror_modal.scale_auto') }}</a-radio-button>
              <a-radio-button value="large">{{ t('device.mirror_modal.scale_large') }}</a-radio-button>
              <a-radio-button value="max">{{ t('device.mirror_modal.scale_max') }}</a-radio-button>
            </a-radio-group>
          </a-space>
        </div>
        <div class="mirror-footer-right">
          <a-space size="small">
            <span class="res-info" v-if="realResolution.w">
              {{ realResolution.w }}×{{ realResolution.h }}
            </span>
            <span class="stream-status-pill">
              <template v-if="isScrcpyLive">
                <span class="status-dot dot-live">●</span> {{ t('device.mirror_modal.stream_live', { fps: currentFps }) }}
              </template>
              <template v-else-if="mirrorSrc">
                <span class="status-dot dot-fallback">●</span> {{ t('device.mirror_modal.stream_fallback') }}
                <span v-if="streamFallbackReason" class="fallback-reason">· {{ streamFallbackReason }}</span>
              </template>
              <template v-else-if="mirrorError">
                <span class="status-dot dot-error">●</span> {{ t('device.mirror_modal.stream_failed') }}
              </template>
              <template v-else>
                <span class="status-dot dot-connecting">●</span> {{ t('device.mirror_modal.stream_connecting') }}
              </template>
            </span>
          </a-space>
        </div>
      </div>
    </div>
  </a-modal>
</template>
<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { message } from 'ant-design-vue'
import {
  AppstoreOutlined,
  CheckCircleOutlined,
  EditOutlined,
  HomeOutlined,
  LeftOutlined,
  LockOutlined,
  MinusOutlined,
  MobileOutlined,
  PlusOutlined,
  PoweroffOutlined,
  ReloadOutlined,
  SendOutlined,
} from '@ant-design/icons-vue'
import { deviceApi, type DeviceItem } from '@/api'
import { isWebCodecsSupported, useWebCodecsDecoder } from '@/composables/useWebCodecsDecoder'
import { getRuntimeMode } from '@/runtimeMode'
import {
  buildAndroidAutoAssertionSteps,
  buildAndroidBestAssertionStepFromTarget,
  buildAndroidRecordedClickParams,
  buildAndroidRecordedSwipeParams,
  type AndroidRecordedStepDraft,
} from '@/utils/androidRecording'

const props = withDefaults(
  defineProps<{
    open: boolean
    device: DeviceItem | null
    canModify?: boolean
    recordable?: boolean
    leaseToken?: string | null
  }>(),
  {
    canModify: true,
    recordable: false,
  },
)

const emit = defineEmits<{
  (e: 'update:open', val: boolean): void
  (e: 'close'): void
  (e: 'recorded', steps: AndroidRecordedStepDraft[]): void
  (e: 'draft-captured', steps: AndroidRecordedStepDraft[], device: DeviceItem | null): void
}>()

const { t } = useI18n()

const visible = computed({
  get: () => props.open,
  set: (val: boolean) => emit('update:open', val),
})

const title = computed(() => {
  const d = props.device
  if (!d) return t('device.mirror_modal.title_fallback')
  const model = (d.model || d.name || '').trim()
  const brand = (d.brand || '').trim()
  const brandModel = model.toLowerCase().startsWith(brand.toLowerCase()) ? model : `${brand} ${model}`.trim()
  return t('device.mirror_title', { name: brandModel || d.serial })
})

const deviceStatusMeta = computed(() => {
  const status = props.device?.status
  if (status === 'online') return { label: t('device.statuses.online'), color: 'success' }
  if (status === 'busy') return { label: t('device.statuses.busy'), color: 'processing' }
  if (status === 'offline') return { label: t('device.statuses.offline'), color: 'default' }
  return { label: status ?? t('device.statuses.offline'), color: 'default' }
})

const internalLeaseToken = ref<string | null>(null)
const leaseAcquiring = ref(false)
const leaseError = ref('')
const leaseExpiresAt = ref<number | null>(null)
const leaseRemainingSeconds = ref(0)
let leaseCountdownTimer: ReturnType<typeof setInterval> | null = null
let leaseHeartbeatTimer: ReturnType<typeof setInterval> | null = null
let leaseRequestInFlight = false
// 内部租约所属的设备 id：释放/续期必须针对申请时的设备，而不是当前 props.device。
let leaseDeviceId: number | null = null
let disposed = false
// 心跳每 25s 续期；TTL 取 90s，标签页被关闭或休眠时设备最多被占用约 1.5 分钟。
const LEASE_TTL_SECONDS = 90

const effectiveLeaseToken = computed(() => {
  return props.leaseToken || internalLeaseToken.value || null
})

const hasControlLease = computed(() => {
  return Boolean(effectiveLeaseToken.value)
})

const leaseRemainingText = computed(() => {
  if (leaseRemainingSeconds.value <= 0) return t('device.mirror_modal.lease_valid')
  const mins = Math.floor(leaseRemainingSeconds.value / 60)
  const secs = leaseRemainingSeconds.value % 60
  return `${mins}:${secs < 10 ? '0' : ''}${secs}`
})

const leaseTooltip = computed(() => {
  if (hasControlLease.value) {
    return t('device.mirror_modal.lease_tooltip_active')
  }
  return t('device.mirror_modal.lease_tooltip_readonly')
})

/** http 拦截器以字符串拒绝（detail）或抛 axios 错误，两种形态都要取出可展示的原因。 */
function leaseErrorText(err: unknown): string {
  if (typeof err === 'string' && err.trim()) return err.trim()
  const detail = (err as { response?: { data?: { detail?: unknown } } })?.response?.data?.detail
  if (typeof detail === 'string' && detail.trim()) return detail.trim()
  const message = (err as { message?: unknown })?.message
  if (typeof message === 'string' && message.trim()) return message.trim()
  return t('device.mirror_modal.lease_default_reason')
}

/** 申请租约的请求返回时，弹窗是否仍为同一设备打开着。 */
function isLeaseTargetCurrent(deviceId: number) {
  return !disposed && props.open && props.device?.id === deviceId
}

async function acquireInteractiveLease(silent = false, takeoverOwn = false) {
  if (!props.device || hasControlLease.value || leaseRequestInFlight) return
  const deviceId = props.device.id
  let stale = false
  leaseRequestInFlight = true
  leaseAcquiring.value = true
  leaseError.value = ''
  try {
    const res = await deviceApi.acquireLease(deviceId, {
      ttl_seconds: LEASE_TTL_SECONDS,
      owner_label: '投屏控制',
      ...(takeoverOwn ? { takeover_own: true } : {}),
    })
    const token = res.lease_token || null
    if (!isLeaseTargetCurrent(deviceId)) {
      // 请求在途时弹窗已关闭或已切换设备：立即归还刚拿到的租约，不写入 token、不启动倒计时/心跳。
      stale = true
      if (token) void deviceApi.releaseLease(deviceId, token).catch(() => {})
      return
    }
    internalLeaseToken.value = token
    leaseDeviceId = token ? deviceId : null
    if (token) startLeaseHeartbeat(LEASE_TTL_SECONDS)
    if (!silent) {
      message.success(t('device.mirror_modal.acquire_success'))
    }
  } catch (err: unknown) {
    if (!isLeaseTargetCurrent(deviceId)) {
      stale = true
      return
    }
    leaseError.value = leaseErrorText(err)
    if (!silent) {
      message.warning(t('device.mirror_modal.acquire_failed', { reason: leaseError.value }))
    }
  } finally {
    leaseRequestInFlight = false
    leaseAcquiring.value = false
    // 在途期间切到了另一台设备：那次申请被 leaseRequestInFlight 挡掉了，这里为当前设备补申请。
    if (stale && !disposed && props.open && props.device && !props.leaseToken) {
      void acquireInteractiveLease(true)
    }
  }
}

function startLeaseHeartbeat(ttl = LEASE_TTL_SECONDS) {
  stopLeaseHeartbeat()
  leaseExpiresAt.value = Date.now() + ttl * 1000
  leaseRemainingSeconds.value = ttl

  leaseCountdownTimer = setInterval(() => {
    if (!leaseExpiresAt.value) return
    const diff = Math.max(0, Math.round((leaseExpiresAt.value - Date.now()) / 1000))
    leaseRemainingSeconds.value = diff
    if (diff <= 0) {
      stopLeaseHeartbeat()
      internalLeaseToken.value = null
      leaseDeviceId = null
    }
  }, 1000)

  leaseHeartbeatTimer = setInterval(async () => {
    const token = internalLeaseToken.value
    const deviceId = leaseDeviceId
    if (deviceId === null || !token) return
    try {
      await deviceApi.heartbeatLease(deviceId, token, LEASE_TTL_SECONDS)
      // 续期在途时租约已被释放或换成了另一台设备的租约：结果作废。
      if (internalLeaseToken.value !== token) return
      leaseExpiresAt.value = Date.now() + LEASE_TTL_SECONDS * 1000
      leaseRemainingSeconds.value = LEASE_TTL_SECONDS
    } catch {
      if (internalLeaseToken.value !== token) return
      stopLeaseHeartbeat()
      internalLeaseToken.value = null
      leaseDeviceId = null
      leaseError.value = t('device.mirror_modal.lease_renew_failed')
    }
  }, 25000)
}

function stopLeaseHeartbeat() {
  if (leaseCountdownTimer) {
    clearInterval(leaseCountdownTimer)
    leaseCountdownTimer = null
  }
  if (leaseHeartbeatTimer) {
    clearInterval(leaseHeartbeatTimer)
    leaseHeartbeatTimer = null
  }
  leaseExpiresAt.value = null
  leaseRemainingSeconds.value = 0
}

async function releaseInteractiveLease() {
  const token = internalLeaseToken.value
  const deviceId = leaseDeviceId
  internalLeaseToken.value = null
  leaseDeviceId = null
  stopLeaseHeartbeat()
  if (deviceId === null || !token) return
  try {
    await deviceApi.releaseLease(deviceId, token)
  } catch {}
}

function releaseLeaseOnPageHide() {
  const token = internalLeaseToken.value
  const deviceId = leaseDeviceId
  if (deviceId === null || !token) return
  internalLeaseToken.value = null
  leaseDeviceId = null
  stopLeaseHeartbeat()
  if (typeof fetch === 'function') {
    void fetch(`/api/v1/devices/${deviceId}/lease`, {
      method: 'DELETE',
      headers: {
        'Content-Type': 'application/json',
        'X-Requested-With': 'XMLHttpRequest',
      },
      body: JSON.stringify({ lease_token: token }),
      credentials: 'include',
      keepalive: true,
    }).catch(() => {})
  }
}

const screenImgRef = ref<HTMLImageElement | null>(null)
const scrcpyCanvasRef = ref<HTMLCanvasElement | null>(null)
const mirrorSrc = ref<string | null>(null)
const mirrorError = ref('')
const streamFallbackReason = ref('')

function describeStreamFallback(): string {
  if (typeof window === 'undefined') return ''
  if (!window.isSecureContext) return t('device.mirror_modal.fallback_insecure')
  return t('device.mirror_modal.fallback_no_webcodecs')
}
let mirrorObjectUrl: string | null = null
let mirrorTimer: ReturnType<typeof setInterval> | null = null
let mirrorSession = 0
let mirrorRefreshingSession: number | null = null

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
const quickInputPlaceholder = computed(() => {
  if (!hasControlLease.value) return t('device.mirror_modal.input_placeholder_readonly')
  return quickInputSensitive.value
    ? t('device.mirror_modal.input_placeholder_sensitive')
    : t('device.mirror_modal.input_placeholder')
})
const quickInputSensitive = ref(false)
const recording = ref(false)
const autoAssert = ref(true)
const pickAssertMode = ref(false)
const finishingRecording = ref(false)
const recordedSteps = ref<AndroidRecordedStepDraft[]>([])

function startRecording() {
  if (!props.canModify || !props.recordable || !props.device) return
  recordedSteps.value = []
  pickAssertMode.value = false
  recording.value = true
}

function discardRecording() {
  recording.value = false
  pickAssertMode.value = false
  recordedSteps.value = []
  quickInputSensitive.value = false
}

async function finishRecording() {
  if (!recording.value || !recordedSteps.value.length || finishingRecording.value) return
  const nextSteps = recordedSteps.value.map((step) => ({ ...step, params: { ...step.params } }))
  if (autoAssert.value && props.device) {
    finishingRecording.value = true
    try {
      const result = await deviceApi.uiAnchors(props.device.id)
      const assertions = buildAndroidAutoAssertionSteps(result.anchors, nextSteps)
      nextSteps.push(...assertions)
    } catch {
      // 自动提取失败时不阻塞保存已录制的交互步骤。
    } finally {
      finishingRecording.value = false
    }
  }
  emit('recorded', nextSteps)
  discardRecording()
  handleClose()
}

async function pickAssertionAtPoint(point: { x: number; y: number }) {
  if (!props.device || !recording.value) return
  isInteracting.value = true
  try {
    const response = await deviceApi.uiTarget(props.device.id, point)
    const step = buildAndroidBestAssertionStepFromTarget(response.target)
    if (!step) {
      message.warning(t('device.mirror_modal.assert_target_missing'))
      return
    }
    appendRecordedStep(step.action, step.name, step.params)
    message.success(t('device.mirror_modal.assert_added', { name: step.name }))
  } catch {
    message.warning(t('device.mirror_modal.assert_fetch_failed'))
  } finally {
    isInteracting.value = false
  }
}

function appendRecordedStep(action: string, name: string, params: Record<string, unknown>) {
  if (recording.value) recordedSteps.value.push({ action, name, params })
}
const isInteracting = ref(false)
const ripple = ref({ visible: false, x: 0, y: 0 })
let dragStartPos = { x: 0, y: 0, time: 0 }

const isScrcpyLive = ref(false)
const currentFps = ref(0)
let scrcpyDecoder: ReturnType<typeof useWebCodecsDecoder> | null = null
let scrcpyWs: WebSocket | null = null
let isMouseDown = false
let canvasDragStart: { x: number; y: number; w: number; h: number; time: number; sent: boolean } | null = null
let lastMoveSentAt = 0
let fpsCount = 0
let fpsTimer: ReturnType<typeof setInterval> | null = null
let scrcpyFallbackTimer: ReturnType<typeof setTimeout> | null = null
let scrcpyInitTimer: ReturnType<typeof setTimeout> | null = null
let rippleTimer: ReturnType<typeof setTimeout> | null = null
let actionRefreshTimer: ReturnType<typeof setTimeout> | null = null

function scheduleActionRefresh(delay = 150) {
  if (actionRefreshTimer) {
    clearTimeout(actionRefreshTimer)
    actionRefreshTimer = null
  }
  const session = mirrorSession
  actionRefreshTimer = setTimeout(() => {
    actionRefreshTimer = null
    if (!props.open || session !== mirrorSession || !props.device) return
    refreshMirror(session)
  }, delay)
}

function triggerScreenshotFallback(session: number) {
  if (!props.open || session !== mirrorSession || isScrcpyLive.value) return
  refreshMirror(session)
  startMirrorPolling()
}

function initScrcpyStream(serial: string, forceReconnect = false) {
  closeScrcpyStream()
  const activeSession = mirrorSession
  const runtime = getRuntimeMode()
  const deviceWorkerId = props.device?.worker_id?.trim()
  const useDeviceScopedScrcpy = Boolean(
    props.device?.id &&
    (runtime?.android_multi_node_enabled ||
      runtime?.adb_scan_mode === 'worker' ||
      (deviceWorkerId && deviceWorkerId !== 'local')),
  )
  if (!isWebCodecsSupported() || !scrcpyCanvasRef.value) {
    streamFallbackReason.value = describeStreamFallback()
    triggerScreenshotFallback(activeSession)
    return
  }
  streamFallbackReason.value = ''

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
      if (activeSession !== mirrorSession) return
      closeScrcpyStream()
      triggerScreenshotFallback(activeSession)
    },
  })

  fpsTimer = setInterval(() => {
    currentFps.value = fpsCount
    fpsCount = 0
  }, 1000)

  // 若在首帧超时窗口内仍未解码出画面，自动启用截图轮询兜底（收到首帧后会自动停止轮询）
  const fallbackWaitMs = useDeviceScopedScrcpy ? 10000 : 5000
  scrcpyFallbackTimer = setTimeout(() => {
    if (activeSession === mirrorSession && !isScrcpyLive.value) {
      triggerScreenshotFallback(activeSession)
    }
  }, fallbackWaitMs)

  const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
  // WebSocket 握手自动携带同源 HttpOnly Cookie，JWT 不进 URL。
  let wsUrl: string
  if (useDeviceScopedScrcpy && props.device?.id) {
    const params = new URLSearchParams()
    if (effectiveLeaseToken.value) params.set('lease_token', effectiveLeaseToken.value)
    if (forceReconnect) params.set('reconnect', '1')
    const query = params.toString()
    wsUrl = `${proto}//${window.location.host}/ws/scrcpy/devices/${props.device.id}${query ? `?${query}` : ''}`
  } else {
    wsUrl = `${proto}//${window.location.host}/ws/scrcpy/${encodeURIComponent(serial)}`
  }
  scrcpyWs = new WebSocket(wsUrl)
  scrcpyWs.binaryType = 'arraybuffer'

  scrcpyWs.onmessage = (event) => {
    if (event.data instanceof ArrayBuffer) {
      scrcpyDecoder?.push(new Uint8Array(event.data))
      return
    }
    if (typeof event.data === 'string') {
      try {
        const msg = JSON.parse(event.data) as {
          type?: string
          width?: number
          height?: number
          code?: string
          message?: string
        }
        if (msg.type === 'metadata' && msg.width && msg.height) {
          realResolution.value = { w: Number(msg.width), h: Number(msg.height) }
        } else if (msg.type === 'error') {
          if (msg.code === 'control_denied') {
            if (msg.message) message.warning(msg.message)
          } else if (msg.message) {
            streamFallbackReason.value = msg.message
          }
        }
      } catch {
        // 忽略非 JSON 文本消息
      }
    }
  }

  scrcpyWs.onclose = () => {
    if (activeSession !== mirrorSession) return
    closeScrcpyStream()
    triggerScreenshotFallback(activeSession)
  }

  scrcpyWs.onerror = () => {
    if (activeSession !== mirrorSession) return
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

async function handleReconnectStream() {
  if (!props.device) return
  const activeDevice = props.device
  const activeSession = mirrorSession
  mirrorError.value = ''
  streamFallbackReason.value = ''
  stopMirrorPolling()
  closeScrcpyStream()
  if (!isWebCodecsSupported() || !scrcpyCanvasRef.value) {
    initScrcpyStream(activeDevice.serial, false)
    return
  }
  if (props.canModify !== false && typeof deviceApi.reconnectStream === 'function') {
    try {
      await deviceApi.reconnectStream(activeDevice.id, true)
    } catch {
      // REST 预热失败时仍继续尝试 WebSocket，由服务端返回详细 error 原因或回退截图
    }
  }
  if (!props.open || activeSession !== mirrorSession || props.device?.id !== activeDevice.id) return
  initScrcpyStream(activeDevice.serial, false)
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
  if (!hasControlLease.value) return false
  if (scrcpyWs && scrcpyWs.readyState === WebSocket.OPEN) {
    scrcpyWs.send(
      JSON.stringify({
        type: 'touch',
        action,
        x: coords.x,
        y: coords.y,
        w: coords.w,
        h: coords.h,
        ...(effectiveLeaseToken.value ? { lease_token: effectiveLeaseToken.value } : {}),
      }),
    )
    return true
  }
  return false
}

function onCanvasMouseDown(e: MouseEvent) {
  if (e.button !== 0 || !props.device) return
  if (!(recording.value && pickAssertMode.value) && !hasControlLease.value) {
    message.warning(t('device.mirror_modal.readonly_warning'))
    return
  }
  isMouseDown = true
  const coords = getCanvasCoords(e)
  showRipple(e.clientX, e.clientY)
  const sent = recording.value && pickAssertMode.value ? false : sendWsTouch(0, coords)
  canvasDragStart = { ...coords, time: Date.now(), sent }
  window.addEventListener('mousemove', onWindowMouseMove)
  window.addEventListener('mouseup', onWindowMouseUp)
}

function onWindowMouseMove(e: MouseEvent) {
  if (!props.device || !isMouseDown) return
  if (recording.value && pickAssertMode.value) return
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
  const start = canvasDragStart
  canvasDragStart = null
  if (recording.value && pickAssertMode.value && start) {
    void pickAssertionAtPoint({ x: start.x, y: start.y })
    return
  }
  const sent = sendWsTouch(1, coords)
  if (!recording.value || !start || !start.sent || !sent) return
  if (Math.hypot(coords.x - start.x, coords.y - start.y) < 12) {
    appendRecordedStep('click', '镜像点击', buildAndroidRecordedClickParams(start, null))
  } else {
    appendRecordedStep('swipe', '镜像滑动', buildAndroidRecordedSwipeParams(
      start, coords, { width: start.w, height: start.h }, Math.max(100, Math.min(Date.now() - start.time, 1500)),
    ))
  }
}

function removeWindowMouseListeners() {
  if (isMouseDown) {
    isMouseDown = false
  }
  canvasDragStart = null
  window.removeEventListener('mousemove', onWindowMouseMove)
  window.removeEventListener('mouseup', onWindowMouseUp)
}

function onImgLoaded() {
  // 预览图可能被服务端降采样（JPEG/540 宽），设备真实分辨率优先取设备档案，避免点击坐标被缩小。
  if (realResolution.value.w && realResolution.value.h) return
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

  if (recording.value && pickAssertMode.value) {
    if (distance < 10) {
      await pickAssertionAtPoint({ x: realStartX, y: realStartY })
    } else {
      message.warning(t('device.mirror_modal.pick_assert_no_swipe'))
    }
    return
  }

  isInteracting.value = true
  try {
    if (!hasControlLease.value) {
      message.warning(t('device.mirror_modal.readonly_warning'))
      return
    }
    if (distance < 10) {
      const target = recording.value
        ? await deviceApi.uiTarget(props.device.id, { x: realStartX, y: realStartY }).then((result) => result.target).catch(() => null)
        : null
      await deviceApi.tap(props.device.id, { x: realStartX, y: realStartY }, effectiveLeaseToken.value)
      appendRecordedStep('click', '镜像点击', buildAndroidRecordedClickParams({ x: realStartX, y: realStartY }, target))
    } else {
      await deviceApi.swipe(props.device.id, {
        x1: realStartX,
        y1: realStartY,
        x2: realEndX,
        y2: realEndY,
        duration_ms: duration,
      }, effectiveLeaseToken.value)
      appendRecordedStep('swipe', '镜像滑动', buildAndroidRecordedSwipeParams(
        { x: realStartX, y: realStartY }, { x: realEndX, y: realEndY },
        { width: devW, height: devH }, duration,
      ))
    }
    scheduleActionRefresh(150)
  } catch (err: unknown) {
    const messageText = err && typeof err === 'object' && 'message' in err ? String(err.message) : t('device.mirror_modal.check_device')
    message.warning(t('device.mirror_modal.action_failed', { reason: messageText }))
  } finally {
    isInteracting.value = false
  }
}

async function sendKeyEvent(keycode: number | string) {
  if (!props.device) return
  if (!hasControlLease.value) {
    message.warning(t('device.mirror_modal.readonly_warning'))
    return
  }
  if (isScrcpyLive.value && scrcpyWs && scrcpyWs.readyState === WebSocket.OPEN) {
    scrcpyWs.send(
      JSON.stringify({
        type: 'key',
        keycode: Number(keycode),
        ...(effectiveLeaseToken.value ? { lease_token: effectiveLeaseToken.value } : {}),
      }),
    )
    recordKeyEvent(Number(keycode))
    return
  }
  try {
    await deviceApi.keyevent(props.device.id, keycode, effectiveLeaseToken.value)
    recordKeyEvent(Number(keycode))
    if (!isScrcpyLive.value) {
      scheduleActionRefresh(150)
    }
  } catch (err: unknown) {
    const msg = err && typeof err === 'object' && 'message' in err ? String(err.message) : String(err)
    message.warning(t('device.mirror_modal.key_failed', { reason: msg }))
  }
}

function recordKeyEvent(keycode: number) {
  const names: Record<number, string> = {
    3: 'HOME', 4: 'BACK', 187: 'RECENT', 26: 'POWER', 24: 'VOLUME_UP', 25: 'VOLUME_DOWN',
  }
  const key = names[keycode]
  if (key) appendRecordedStep('press_key', `按键 ${key}`, { key })
}

async function sendQuickText() {
  const text = quickInputText.value.trim()
  if (!text || !props.device) return
  if (!hasControlLease.value) {
    message.warning(t('device.mirror_modal.readonly_warning'))
    return
  }
  const recordQuickStep = () => {
    if (quickInputSensitive.value) {
      appendRecordedStep('input', '输入敏感值（请手动填写）', { text: '', sensitive: true })
    } else {
      appendRecordedStep('input', '镜像输入文字', { text })
    }
  }
  if (isScrcpyLive.value && scrcpyWs && scrcpyWs.readyState === WebSocket.OPEN) {
    scrcpyWs.send(
      JSON.stringify({
        type: 'text',
        text,
        ...(effectiveLeaseToken.value ? { lease_token: effectiveLeaseToken.value } : {}),
      }),
    )
    recordQuickStep()
    quickInputText.value = ''
    return
  }
  try {
    await deviceApi.inputText(props.device.id, text, effectiveLeaseToken.value)
    recordQuickStep()
    quickInputText.value = ''
    if (!isScrcpyLive.value) {
      scheduleActionRefresh(200)
    }
  } catch (err: unknown) {
    const msg = err && typeof err === 'object' && 'message' in err ? String(err.message) : String(err)
    message.warning(t('device.mirror_modal.text_failed', { reason: msg }))
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
  mirrorError.value = ''
  realResolution.value = { w: 0, h: 0 }
  if (actionRefreshTimer) {
    clearTimeout(actionRefreshTimer)
    actionRefreshTimer = null
  }
  if (rippleTimer) {
    clearTimeout(rippleTimer)
    rippleTimer = null
  }
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
  if (!props.device || mirrorRefreshingSession === session || session !== mirrorSession) return false
  mirrorRefreshingSession = session
  try {
    const blob = await deviceApi.screenshot(props.device.id, { maxWidth: 540, format: 'jpeg' })
    if (session !== mirrorSession) return
    const nextUrl = URL.createObjectURL(blob)
    const prevUrl = mirrorObjectUrl
    mirrorObjectUrl = nextUrl
    mirrorSrc.value = nextUrl
    mirrorError.value = ''
    if (prevUrl) URL.revokeObjectURL(prevUrl)
    return true
  } catch {
    if (session === mirrorSession && !isScrcpyLive.value) {
      mirrorError.value = t('device.mirror_modal.screenshot_failed')
      stopMirrorPolling()
    }
    return false
  } finally {
    if (mirrorRefreshingSession === session) mirrorRefreshingSession = null
  }
}

async function retryScreenshot() {
  const session = mirrorSession
  mirrorError.value = ''
  if (await refreshMirror(session) && session === mirrorSession && !isScrcpyLive.value) {
    startMirrorPolling()
  }
}

function onMirrorError() {
  revokeMirrorUrl()
  mirrorError.value = t('device.mirror_modal.display_failed')
  stopMirrorPolling()
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
  if (recording.value && recordedSteps.value.length > 0) {
    emit(
      'draft-captured',
      recordedSteps.value.map((step) => ({ ...step, params: { ...step.params } })),
      props.device ?? null,
    )
  }
  discardRecording()
  cleanupMirror()
  releaseInteractiveLease()
  emit('update:open', false)
  emit('close')
}

watch(
  () => props.open,
  (val) => {
    if (val && props.device) {
      startMirror()
      if (!props.leaseToken) {
        acquireInteractiveLease(true)
      }
    } else {
      cleanupMirror()
      releaseInteractiveLease()
    }
  },
  { immediate: true },
)

watch(
  () => props.device?.id,
  (newId, oldId) => {
    if (newId === oldId) return
    // 打开状态下切换设备：旧设备的租约按旧设备 id 归还（连同心跳/倒计时），再为新设备申请。
    void releaseInteractiveLease()
    leaseError.value = ''
    if (props.open && newId && props.device) {
      startMirror()
      if (!props.leaseToken) {
        acquireInteractiveLease(true)
      }
    }
  },
)

onMounted(() => {
  window.addEventListener('pagehide', releaseLeaseOnPageHide)
})

onBeforeUnmount(() => {
  disposed = true
  window.removeEventListener('pagehide', releaseLeaseOnPageHide)
  cleanupMirror()
  releaseInteractiveLease()
})
</script>

<style scoped>
.mirror-modal-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  width: 100%;
  padding-right: 32px;
}
.header-device-info {
  display: flex;
  align-items: center;
  gap: 8px;
}
.device-icon {
  font-size: 16px;
  color: #1677ff;
}
.device-title-text {
  font-size: 15px;
  font-weight: 600;
  color: var(--c-text);
}
.header-status-tag {
  margin: 0;
  font-size: 11px;
  border-radius: 10px;
  padding: 0 6px;
  line-height: 18px;
}
.header-lease-info {
  display: flex;
  align-items: center;
  gap: 8px;
}
.header-lease-tag {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  font-size: 12px;
  border-radius: 4px;
  padding: 1px 8px;
}
.mirror-workspace {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 12px;
}
.mirror-phone-frame {
  position: relative;
  display: inline-flex;
  flex-direction: column;
  align-items: center;
  background: #121319;
  border-radius: 28px;
  padding: 8px 8px 6px;
  box-shadow: 0 16px 48px rgba(0, 0, 0, 0.28), 0 0 0 2px rgba(255, 255, 255, 0.08);
  margin: 0 auto;
  user-select: none;
  max-width: 100%;
  transition: all 0.25s cubic-bezier(0.4, 0, 0.2, 1);
}
.phone-earpiece-notch {
  width: 48px;
  height: 4px;
  border-radius: 2px;
  background: rgba(255, 255, 255, 0.2);
  margin: 2px auto 6px;
  flex-shrink: 0;
}
.mirror-screen-wrapper {
  position: relative;
  display: inline-flex;
  justify-content: center;
  align-items: center;
  cursor: crosshair;
  line-height: 0;
  border-radius: 18px;
  overflow: hidden;
  background: #000;
}
.mirror-screen-wrapper.wrapper-empty {
  width: min(300px, 60vw);
  aspect-ratio: 9 / 16;
  max-height: 44vh;
}
.mirror-screen-wrapper.wrapper-empty.wrapper-landscape {
  width: min(420px, 72vw);
  aspect-ratio: 16 / 9;
  max-height: 40vh;
}
.mirror-lease-alert {
  width: 100%;
  text-align: left;
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
  gap: 6px;
  width: auto;
  padding: 3px 12px;
  background: var(--c-bg-elevated, #f5f5f7);
  border-radius: 20px;
  border: 1px solid var(--c-border, #e8e8e8);
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.04);
}
.nav-btn-group {
  display: flex;
  align-items: center;
  gap: 4px;
}
.nav-separator {
  width: 1px;
  height: 14px;
  background: var(--c-border, #d9d9d9);
  margin: 0 4px;
}
.nav-key-btn {
  background: transparent;
  border: none;
  cursor: pointer;
  font-size: 14px;
  color: var(--c-text, #262626);
  width: 34px;
  height: 28px;
  border-radius: 6px;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.15s ease;
}
.nav-key-btn:not(:disabled):hover {
  background: var(--c-bg-hover, rgba(0, 0, 0, 0.08));
  color: #1677ff;
  transform: translateY(-1px);
}
.nav-key-btn:not(:disabled):active {
  transform: scale(0.92);
}
.nav-key-btn:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}
.nav-power-btn:not(:disabled):hover {
  color: #ff4d4f;
  background: rgba(255, 77, 79, 0.1);
}
.mirror-record-bar {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
  width: 100%;
  justify-content: center;
}
.mirror-auto-assert-toggle {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  color: var(--c-text-secondary, #595959);
  cursor: pointer;
}
.mirror-text-bar {
  display: flex;
  align-items: center;
  gap: 8px;
  width: 100%;
  max-width: 520px;
}
.mirror-sensitive-toggle {
  white-space: nowrap;
  flex-shrink: 0;
  font-size: 12px;
}
.mirror-placeholder {
  position: absolute;
  inset: 0;
  display: flex;
  justify-content: center;
  align-items: center;
  color: var(--c-text-tertiary, #8c8c8c);
  padding: 24px;
  text-align: center;
}
.mirror-footer {
  width: 100%;
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-wrap: wrap;
  gap: 12px;
  margin-top: 4px;
  padding-top: 6px;
  border-top: 1px solid var(--c-border-subtle, rgba(0, 0, 0, 0.06));
}
.mirror-footer-left {
  display: flex;
  align-items: center;
  gap: 8px;
}
.mirror-footer-right {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-shrink: 0;
}
.res-info {
  font-size: 11px;
  padding: 1px 6px;
  background: var(--c-bg-elevated, #f0f0f0);
  border-radius: 4px;
  color: var(--c-text-tertiary, #8c8c8c);
}
.stream-status-pill {
  font-size: 12px;
  color: var(--c-text-secondary, #595959);
  display: inline-flex;
  align-items: center;
  gap: 4px;
  white-space: nowrap;
}
.dot-live { color: #52c41a; font-size: 9px; }
.dot-fallback { color: #faad14; font-size: 9px; }
.fallback-reason { color: var(--c-text-tertiary, #8c8c8c); font-size: 11px; }
.dot-error { color: #ff4d4f; font-size: 9px; }
.dot-connecting { color: #1677ff; font-size: 9px; }
</style>
