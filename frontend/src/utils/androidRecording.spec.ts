import { describe, expect, it } from 'vitest'
import {
  buildAndroidAssertionStepFromTarget,
  buildAndroidAutoAssertionSteps,
  buildAndroidBestAssertionStepFromTarget,
  buildAndroidRecordedClickParams,
  buildAndroidRecordedSwipeParams,
} from './androidRecording'

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

describe('android assertion builders', () => {
  it('builds assert_element and assert_text from screen anchors and avoids trailing duplicates', () => {
    const anchors = {
      text: '首页',
      resourceId: 'com.demo:id/home_title',
      contentDesc: '主页标识',
      packageName: 'com.demo',
    }
    const created = buildAndroidAutoAssertionSteps(anchors, [
      { action: 'click', params: { text: '登录' } },
    ])
    expect(created).toEqual([
      {
        action: 'assert_element',
        name: '断言元素 com.demo:id/home_title',
        params: { resourceId: 'com.demo:id/home_title' },
      },
      {
        action: 'assert_text',
        name: '断言文本 首页',
        params: { text: '首页' },
      },
    ])

    expect(buildAndroidAutoAssertionSteps(anchors, created)).toEqual([])
  })

  it('falls back to contentDesc text only when neither resourceId nor text exists', () => {
    expect(buildAndroidAutoAssertionSteps({ contentDesc: '播放按钮' }, [])).toEqual([
      {
        action: 'assert_text',
        name: '断言文本 播放按钮',
        params: { text: '播放按钮' },
      },
    ])
    expect(buildAndroidAutoAssertionSteps(null, [])).toEqual([])
  })

  it('enforces precheck requirements when building explicit assertions from a tapped target', () => {
    expect(buildAndroidAssertionStepFromTarget('assert_element', { text: '仅有文本' })).toBeNull()
    expect(
      buildAndroidAssertionStepFromTarget('assert_element', {
        text: '提交',
        resourceId: 'com.demo:id/btn_submit',
      }),
    ).toEqual({
      action: 'assert_element',
      name: '断言元素 com.demo:id/btn_submit',
      params: { resourceId: 'com.demo:id/btn_submit' },
    })

    expect(
      buildAndroidAssertionStepFromTarget('assert_text', { contentDesc: '搜索图标' }),
    ).toEqual({
      action: 'assert_text',
      name: '断言文本 搜索图标',
      params: { text: '搜索图标' },
    })
    expect(buildAndroidAssertionStepFromTarget('assert_text', {})).toBeNull()
  })

  it('prefers text, then resourceId, then contentDesc in best-effort pick-assert mode', () => {
    expect(
      buildAndroidBestAssertionStepFromTarget({
        text: '欢迎登录',
        resourceId: 'com.demo:id/title',
      }),
    ).toEqual({
      action: 'assert_text',
      name: '断言文本 欢迎登录',
      params: { text: '欢迎登录' },
    })
    expect(
      buildAndroidBestAssertionStepFromTarget({
        resourceId: 'com.demo:id/avatar',
        contentDesc: '头像',
      }),
    ).toEqual({
      action: 'assert_element',
      name: '断言元素 com.demo:id/avatar',
      params: { resourceId: 'com.demo:id/avatar' },
    })
    expect(buildAndroidBestAssertionStepFromTarget({ contentDesc: '设置' })).toEqual({
      action: 'assert_text',
      name: '断言文本 设置',
      params: { text: '设置' },
    })
    expect(buildAndroidBestAssertionStepFromTarget(null)).toBeNull()
  })
})
