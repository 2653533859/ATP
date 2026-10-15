/**
 * h264.ts - H.264 Annex-B 码流解析纯函数
 *
 * 服务于 ScrcpyPlayer 的 WebCodecs 解码路径：
 * 后端 `WS /ws/scrcpy/{serial}` 每条二进制消息是一个裸 Annex-B H.264 包
 * （带 00 00 01 / 00 00 00 01 start code，SPS/PPS 为独立 config 包）。
 * 这里提供 NAL 拆分、类型判定、codec 串推导与 Annex-B 重组的无副作用工具。
 */

export const NAL_TYPE = {
  SLICE_NON_IDR: 1,
  PARTITION_A: 2,
  PARTITION_B: 3,
  PARTITION_C: 4,
  SLICE_IDR: 5,
  SEI: 6,
  SPS: 7,
  PPS: 8,
  AUD: 9,
} as const

export function getNalType(nal: Uint8Array): number {
  if (!nal || nal.length === 0) return -1
  return nal[0] & 0x1f
}

export function splitAnnexBNalUnits(bytes: Uint8Array): Uint8Array[] {
  const units: Uint8Array[] = []
  if (!bytes || bytes.length < 4) return units

  const len = bytes.length
  let nalStart = -1

  for (let i = 0; i + 2 < len; i++) {
    if (bytes[i] !== 0x00 || bytes[i + 1] !== 0x00 || bytes[i + 2] !== 0x01) continue
    if (nalStart >= 0) {
      let nalEnd = i
      if (nalEnd > nalStart && bytes[nalEnd - 1] === 0x00) nalEnd--
      if (nalEnd > nalStart) units.push(bytes.subarray(nalStart, nalEnd))
    }
    nalStart = i + 3
    i += 2
  }

  if (nalStart >= 0 && nalStart < len) {
    units.push(bytes.subarray(nalStart, len))
  }
  return units
}

export function codecStringFromSps(spsNal: Uint8Array): string | null {
  if (!spsNal || spsNal.length < 4 || getNalType(spsNal) !== NAL_TYPE.SPS) return null
  const hex = (byte: number) => byte.toString(16).padStart(2, '0')
  return `avc1.${hex(spsNal[1])}${hex(spsNal[2])}${hex(spsNal[3])}`
}

export interface AnnexBPacketClassification {
  sps: Uint8Array | null
  pps: Uint8Array | null
  hasIdr: boolean
  hasSlice: boolean
  frameNalUnits: Uint8Array[]
}

export function classifyAnnexBPacket(bytes: Uint8Array): AnnexBPacketClassification {
  const nalUnits = splitAnnexBNalUnits(bytes)
  let sps: Uint8Array | null = null
  let pps: Uint8Array | null = null
  let hasIdr = false
  let hasSlice = false
  const frameNalUnits: Uint8Array[] = []

  for (const nal of nalUnits) {
    const type = getNalType(nal)
    if (type === NAL_TYPE.SPS) {
      sps = nal
      continue
    }
    if (type === NAL_TYPE.PPS) {
      pps = nal
      continue
    }
    if (type === NAL_TYPE.SLICE_IDR) {
      hasIdr = true
      hasSlice = true
    } else if (type >= NAL_TYPE.SLICE_NON_IDR && type <= NAL_TYPE.PARTITION_C) {
      hasSlice = true
    }
    frameNalUnits.push(nal)
  }

  return { sps, pps, hasIdr, hasSlice, frameNalUnits }
}

export function buildAnnexBStream(nalUnits: Uint8Array[]): Uint8Array {
  let total = 0
  for (const nal of nalUnits) total += 4 + nal.length

  const out = new Uint8Array(total)
  let offset = 0
  for (const nal of nalUnits) {
    out[offset] = 0x00
    out[offset + 1] = 0x00
    out[offset + 2] = 0x00
    out[offset + 3] = 0x01
    out.set(nal, offset + 4)
    offset += 4 + nal.length
  }
  return out
}

export function bytesEqual(a: Uint8Array | null, b: Uint8Array | null): boolean {
  if (a === b) return true
  if (!a || !b || a.length !== b.length) return false
  for (let i = 0; i < a.length; i++) {
    if (a[i] !== b[i]) return false
  }
  return true
}
