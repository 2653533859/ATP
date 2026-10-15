/**
 * useWebCodecsDecoder.ts - 基于 WebCodecs VideoDecoder 的 scrcpy H.264 解码管线
 *
 * 输入：push() 喂入来自 WebSocket 的裸 Annex-B H.264 包
 * 输出：硬件加速解码后经 requestAnimationFrame 绘制到传入的 <canvas>，低延迟、高帧率（30~60 FPS）。
 */
import {
  classifyAnnexBPacket,
  codecStringFromSps,
  buildAnnexBStream,
  bytesEqual,
} from '@/utils/h264'

const MICROS_PER_SECOND = 1e6
const MAX_PENDING_PACKETS = 300
const STABLE_OUTPUTS_TO_RESET_ERRORS = 30

const codecSupportCache = new Map<string, boolean>()

export interface WebCodecsDecoderOptions {
  canvas: HTMLCanvasElement | null
  fpsHint?: number
  maxConsecutiveErrors?: number
  maxQueuedDecodes?: number
  onFrameDecoded?: (() => void) | null
  onFallback?: ((reason: string) => void) | null
  debug?: boolean
}

export function useWebCodecsDecoder({
  canvas,
  fpsHint = 60,
  maxConsecutiveErrors = 3,
  maxQueuedDecodes = 60,
  onFrameDecoded = null,
  onFallback = null,
  debug = false,
}: WebCodecsDecoderOptions) {
  const frameDurationUs = Math.max(1, Math.round(MICROS_PER_SECOND / fpsHint))
  const ctx = canvas ? canvas.getContext('2d', { alpha: false, desynchronized: true }) : null

  let destroyed = false
  let fellBack = false
  let decoder: VideoDecoder | null = null

  let spsNal: Uint8Array | null = null
  let ppsNal: Uint8Array | null = null
  let needsConfigure = true
  let awaitingKeyFrame = true

  let checkingSupport = false
  let pendingPackets: Uint8Array[] = []

  let timestampUs = 0
  let consecutiveErrors = 0
  let outputsSinceError = 0

  let pendingFrame: VideoFrame | null = null
  let rafId: number | null = null

  function fallback(reason: string) {
    if (destroyed || fellBack) return
    fellBack = true
    pendingPackets = []
    teardownDecoder()
    if (typeof onFallback === 'function') onFallback(reason)
  }

  function teardownDecoder() {
    if (decoder && decoder.state !== 'closed') {
      try {
        decoder.close()
      } catch {
        // ignore
      }
    }
    decoder = null
  }

  function handleDecodeFailure(err: any) {
    if (destroyed || fellBack) return
    consecutiveErrors++
    outputsSinceError = 0
    teardownDecoder()
    needsConfigure = true
    awaitingKeyFrame = true
    if (debug) console.debug('[scrcpy-webcodecs] 解码错误:', err?.message || err)
    if (consecutiveErrors >= maxConsecutiveErrors) {
      fallback(`decode-errors:${consecutiveErrors}`)
    }
  }

  function handleOutput(frame: VideoFrame) {
    if (destroyed) {
      frame.close()
      return
    }
    outputsSinceError++
    if (outputsSinceError >= STABLE_OUTPUTS_TO_RESET_ERRORS) consecutiveErrors = 0
    if (typeof onFrameDecoded === 'function') onFrameDecoded()

    if (!ctx || !canvas) {
      frame.close()
      return
    }
    if (pendingFrame) {
      pendingFrame.close()
    }
    pendingFrame = frame
    if (rafId === null) rafId = requestAnimationFrame(paintPendingFrame)
  }

  function paintPendingFrame() {
    rafId = null
    const frame = pendingFrame
    pendingFrame = null
    if (!frame) return
    try {
      if (!destroyed && canvas && ctx) {
        const width = frame.displayWidth || frame.codedWidth
        const height = frame.displayHeight || frame.codedHeight
        if (width > 0 && height > 0) {
          if (canvas.width !== width) canvas.width = width
          if (canvas.height !== height) canvas.height = height
          ctx.drawImage(frame, 0, 0, width, height)
        }
      }
    } finally {
      frame.close()
    }
  }

  function configureDecoder(codec: string) {
    if (!decoder || decoder.state === 'closed') {
      decoder = new (window as any).VideoDecoder({ output: handleOutput, error: handleDecodeFailure })
    } else if (decoder.state === 'configured') {
      decoder.reset()
    }
    if (decoder) {
      decoder.configure({ codec, optimizeForLatency: true } as any)
      needsConfigure = false
      awaitingKeyFrame = true
    }
  }

  function beginSupportCheck(codec: string) {
    checkingSupport = true
    ;(window as any).VideoDecoder.isConfigSupported({ codec, optimizeForLatency: true })
      .then((result: any) => Boolean(result && result.supported))
      .catch(() => false)
      .then((supported: boolean) => {
        codecSupportCache.set(codec, supported)
        checkingSupport = false
        if (destroyed || fellBack) return
        if (!supported) {
          fallback(`codec-unsupported:${codec}`)
          return
        }
        drainPendingPackets()
      })
  }

  function drainPendingPackets() {
    while (pendingPackets.length > 0 && !destroyed && !fellBack && !checkingSupport) {
      const pkt = pendingPackets.shift()
      if (pkt) processPacket(pkt)
    }
  }

  function processPacket(bytes: Uint8Array) {
    const packet = classifyAnnexBPacket(bytes)

    let configChanged = false
    if (packet.sps && !bytesEqual(packet.sps, spsNal)) {
      spsNal = packet.sps.slice()
      configChanged = true
    }
    if (packet.pps && !bytesEqual(packet.pps, ppsNal)) {
      ppsNal = packet.pps.slice()
      configChanged = true
    }
    if (configChanged) needsConfigure = true

    if (!packet.hasSlice || packet.frameNalUnits.length === 0) return

    if (
      decoder &&
      decoder.state === 'configured' &&
      decoder.decodeQueueSize > maxQueuedDecodes &&
      !needsConfigure
    ) {
      needsConfigure = true
      awaitingKeyFrame = true
    }

    if (needsConfigure || !decoder || decoder.state === 'closed') {
      if (!packet.hasIdr) return
      if (!spsNal || !ppsNal) return
      const codec = codecStringFromSps(spsNal)
      if (!codec) {
        fallback('sps-parse-failed')
        return
      }
      const supported = codecSupportCache.get(codec)
      if (supported === undefined) {
        if (pendingPackets.length >= MAX_PENDING_PACKETS) pendingPackets.shift()
        pendingPackets.push(bytes)
        beginSupportCheck(codec)
        return
      }
      if (!supported) {
        fallback(`codec-unsupported:${codec}`)
        return
      }
      try {
        configureDecoder(codec)
      } catch (err) {
        handleDecodeFailure(err)
        return
      }
    }

    if (awaitingKeyFrame && !packet.hasIdr) return

    let data: Uint8Array
    if (packet.hasIdr) {
      data = buildAnnexBStream([spsNal!, ppsNal!, ...packet.frameNalUnits])
    } else if (!packet.sps && !packet.pps) {
      data = bytes
    } else {
      data = buildAnnexBStream(packet.frameNalUnits)
    }

    const chunk = new (window as any).EncodedVideoChunk({
      type: packet.hasIdr ? 'key' : 'delta',
      timestamp: timestampUs,
      duration: frameDurationUs,
      data,
    })
    timestampUs += frameDurationUs

    try {
      if (decoder && decoder.state === 'configured') {
        decoder.decode(chunk)
        if (packet.hasIdr) awaitingKeyFrame = false
      }
    } catch (err) {
      handleDecodeFailure(err)
    }
  }

  function push(bytes: Uint8Array) {
    if (destroyed || fellBack || !bytes || bytes.length === 0) return
    if (checkingSupport) {
      if (pendingPackets.length >= MAX_PENDING_PACKETS) pendingPackets.shift()
      pendingPackets.push(bytes)
      return
    }
    processPacket(bytes)
  }

  function destroy() {
    if (destroyed) return
    destroyed = true
    if (rafId !== null) {
      cancelAnimationFrame(rafId)
      rafId = null
    }
    if (pendingFrame) {
      pendingFrame.close()
      pendingFrame = null
    }
    pendingPackets = []
    teardownDecoder()
  }

  return { push, destroy }
}

export function isWebCodecsSupported(): boolean {
  return (
    typeof window !== 'undefined' &&
    'VideoDecoder' in window &&
    typeof (window as any).VideoDecoder.isConfigSupported === 'function' &&
    typeof (window as any).EncodedVideoChunk === 'function'
  )
}
