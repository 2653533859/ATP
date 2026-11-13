import { beforeEach, describe, expect, it } from 'vitest'

import {
  clearLocalRecordingDraft,
  loadLocalRecordingDraft,
  safeArtifactUrl,
  sanitizeStepsForLocalDraft,
  saveLocalRecordingDraft,
} from './recordingDraft'

describe('recordingDraft', () => {
  beforeEach(() => {
    window.localStorage.clear()
  })

  it('redacts sensitive input values and query parameters before saving locally', () => {
    const saved = saveLocalRecordingDraft({
      kind: 'web',
      projectId: 12,
      recordId: 44,
      targetUrl: 'https://demo.example.com/login?token=secret-jwt&tab=1',
      browser: 'chromium',
      steps: [
        { action: 'goto', name: '打开页面', params: { url: 'https://demo.example.com/login?token=secret-jwt' } },
        { action: 'fill', name: '输入敏感值', params: { selector: '#pwd', value: 'MySecret123!', sensitive: true } },
        { action: 'assert_visible', name: '断言可见', params: { selector: '#submit' } },
      ],
    })

    expect(saved).not.toBeNull()
    expect(saved?.targetUrl).toBe('https://demo.example.com/login')
    expect(saved?.steps[0].params.url).toBe('https://demo.example.com/login')
    expect(saved?.steps[1].params.value).toBe('')

    const loaded = loadLocalRecordingDraft(12, 'web')
    expect(loaded?.recordId).toBe(44)
    expect(loaded?.steps).toHaveLength(3)
    expect(loaded?.steps[1].params.value).toBe('')
  })

  it('clears draft when steps are empty or explicitly cleared', () => {
    saveLocalRecordingDraft({
      kind: 'android',
      projectId: 9,
      deviceSerial: 'emulator-5554',
      steps: [{ action: 'tap', name: '点击', params: { x: 10, y: 20 } }],
    })
    expect(loadLocalRecordingDraft(9, 'android')).not.toBeNull()

    clearLocalRecordingDraft(9, 'android')
    expect(loadLocalRecordingDraft(9, 'android')).toBeNull()

    saveLocalRecordingDraft({ kind: 'android', projectId: 9, steps: [] })
    expect(loadLocalRecordingDraft(9, 'android')).toBeNull()
  })

  it('filters invalid step items gracefully', () => {
    const cleaned = sanitizeStepsForLocalDraft([null, { name: 'no-action' }, { action: 'click', params: {} }])
    expect(cleaned).toEqual([{ action: 'click', name: 'click', params: {} }])
  })

  it('isolates drafts per userId and keeps anonymous scope safe without Pinia', () => {
    saveLocalRecordingDraft(
      { kind: 'web', projectId: 9, steps: [{ action: 'goto', name: 'A', params: { url: 'https://a.test' } }] },
      101,
    )
    saveLocalRecordingDraft(
      { kind: 'web', projectId: 9, steps: [{ action: 'goto', name: 'B', params: { url: 'https://b.test' } }] },
      202,
    )

    expect(loadLocalRecordingDraft(9, 'web', 101)?.steps[0].name).toBe('A')
    expect(loadLocalRecordingDraft(9, 'web', 202)?.steps[0].name).toBe('B')
    expect(loadLocalRecordingDraft(9, 'web', null)).toBeNull()

    clearLocalRecordingDraft(9, 'web', 101)
    expect(loadLocalRecordingDraft(9, 'web', 101)).toBeNull()
    expect(loadLocalRecordingDraft(9, 'web', 202)?.steps[0].name).toBe('B')
  })

  it('allows only http(s) and single-slash relative artifact URLs', () => {
    expect(safeArtifactUrl('https://minio.local/trace.zip?sig=1')).toBe('https://minio.local/trace.zip?sig=1')
    expect(safeArtifactUrl('http://localhost:9000/har.json')).toBe('http://localhost:9000/har.json')
    expect(safeArtifactUrl('/api/v1/files/1')).toBe('/api/v1/files/1')
    expect(safeArtifactUrl('javascript:alert(1)')).toBeNull()
    expect(safeArtifactUrl('data:text/html,<script>alert(1)</script>')).toBeNull()
    expect(safeArtifactUrl('//evil.example/payload')).toBeNull()
    expect(safeArtifactUrl('   ')).toBeNull()
  })
})
