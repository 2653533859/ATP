import { describe, expect, it } from 'vitest'
import { buildAndroidRecordedClickParams, buildAndroidRecordedSwipeParams } from './androidRecording'

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

  it('stores the recording screen size with a swipe', () => {
    expect(buildAndroidRecordedSwipeParams(
      { x: 120, y: 240 },
      { x: 120, y: 980 },
      { width: 1080, height: 2400 },
    )).toEqual({
      direction: undefined,
      x1: 120,
      y1: 240,
      x2: 120,
      y2: 980,
      duration: 300,
      screenWidth: 1080,
      screenHeight: 2400,
    })
  })
})
