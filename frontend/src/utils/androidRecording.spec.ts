import { describe, expect, it } from 'vitest'
import { buildAndroidRecordedClickParams } from './androidRecording'

describe('buildAndroidRecordedClickParams', () => {
  it('keeps semantic properties and coordinate fallback together', () => {
    expect(buildAndroidRecordedClickParams(
      { x: 120, y: 240 },
      {
        text: '登录',
        resourceId: 'com.demo:id/login',
        contentDesc: '提交表单',
        className: 'android.widget.Button',
        bounds: { left: 80, top: 200, right: 320, bottom: 280 },
      },
    )).toEqual({
      text: '登录',
      resourceId: 'com.demo:id/login',
      contentDesc: '提交表单',
      x: 120,
      y: 240,
      className: 'android.widget.Button',
      bounds: { left: 80, top: 200, right: 320, bottom: 280 },
    })
  })

  it('keeps coordinates when UIAutomator returns no target', () => {
    expect(buildAndroidRecordedClickParams({ x: 1, y: 2 }, null)).toEqual({
      text: '',
      resourceId: '',
      contentDesc: '',
      x: 1,
      y: 2,
    })
  })
})
