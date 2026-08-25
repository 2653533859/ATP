import { describe, expect, it } from 'vitest'
import { generateAndroidPythonScript, generateWebPythonScript } from './pythonScriptGenerator'

describe('python script generators', () => {
  it('generates a Playwright pytest script from Web steps', () => {
    const script = generateWebPythonScript([
      { action: 'goto', name: '打开首页', params: { url: 'https://example.test' } },
      { action: 'fill', name: '填写账号', params: { selector: '#username', value: '{{ACCOUNT}}' } },
      { action: 'click', name: '点击登录', params: { selector: '#login' } },
      { action: 'assert_visible', name: '显示首页', params: { selector: '.home' } },
      { action: 'screenshot', name: '保存截图', params: {} },
    ])

    expect(script).toContain('from playwright.sync_api import Page, expect')
    expect(script).toContain('page.goto("https://example.test")')
    expect(script).toContain('page.locator("#username").fill(os.getenv("ACCOUNT", ""))')
    expect(script).toContain('expect(page.locator(".home")).to_be_visible()')
    expect(script).toContain('page.screenshot(path="screenshots/step_5.png")')
  })

  it('generates an Android uiautomator2 pytest script from low-code steps', () => {
    const script = generateAndroidPythonScript([
      { action: 'start_app', name: '启动应用', params: { package: 'com.example.app' } },
      { action: 'click', name: '点击登录', params: { resourceId: 'com.example:id/login' } },
      { action: 'input', name: '输入账号', params: { resourceId: 'com.example:id/username', text: 'tester', clear: true } },
      { action: 'press_key', name: '返回', params: { key: 'BACK' } },
    ])

    expect(script).toContain('import uiautomator2 as u2')
    expect(script).toContain('device.app_start("com.example.app")')
    expect(script).toContain('device(resourceId="com.example:id/login").click()')
    expect(script).toContain('input_target.clear_text()')
    expect(script).toContain('device.press("back")')
  })

  it('uses content-desc when a recorded control has no text or resource id', () => {
    const script = generateAndroidPythonScript([
      { action: 'click', name: '打开菜单', params: { contentDesc: '打开菜单' } },
    ])

    expect(script).toContain('device(description="打开菜单").click()')
  })

  it('does not use input content as the input control locator', () => {
    const script = generateAndroidPythonScript([
      { action: 'input', name: '输入账号', params: { text: 'tester', targetText: '账号', contentDesc: '账号输入框' } },
    ])

    expect(script).toContain('input_target = device(text="账号")')
    expect(script).not.toContain('input_target = device(text="tester")')
    expect(script).toContain('input_target.set_text("tester")')
  })

  it('scales recorded Android swipes to the replay device size', () => {
    const script = generateAndroidPythonScript([
      { action: 'swipe', name: '滑动列表', params: {
        x1: 100,
        y1: 200,
        x2: 100,
        y2: 1000,
        screenWidth: 1080,
        screenHeight: 2400,
      } },
    ])

    expect(script).toContain('current_width, current_height = device.window_size()')
    expect(script).toContain('100 * current_width / 1080')
    expect(script).toContain('200 * current_height / 2400')
  })

  it('uses the replay device size for direction swipes', () => {
    const script = generateAndroidPythonScript([
      { action: 'swipe', name: '上滑', params: { direction: 'up' } },
    ])

    expect(script).toContain('device.window_size()')
    expect(script).toContain('current_height * 5 / 6')
  })

  it('generates Android device control steps and fails explicitly for unknown actions', () => {
    const script = generateAndroidPythonScript([
      { action: 'rotate', name: '切换横屏', params: { orientation: 'landscape' } },
      { action: 'grant_permission', name: '授予权限', params: { package: 'com.example.app', permission: 'android.permission.CAMERA' } },
      { action: 'network_profile', name: '关闭 Wi-Fi', params: { profile: 'wifi_off' } },
      { action: 'background', name: '切换后台', params: {} },
      { action: 'unknown_action', name: '未知步骤', params: {} },
    ])

    expect(script).toContain('device.set_orientation("left")')
    expect(script).toContain('device.shell("pm", "grant", "com.example.app", "android.permission.CAMERA")')
    expect(script).toContain('device.shell("svc", "wifi", "disable")')
    expect(script).toContain('device.press("home")')
    expect(script).toContain('pytest.fail("未支持的低代码动作：unknown_action")')
  })

  it('generates runnable Web file and visual assertion steps', () => {
    const script = generateWebPythonScript([
      { action: 'upload', name: '上传文件', params: { selector: '#file' } },
      { action: 'download', name: '下载报告', params: { selector: '#download' } },
      { action: 'visual_assert', name: '校验页面', params: { threshold: 0.02, pixel_threshold: 12 } },
    ])

    expect(script).toContain('ATP_WEB_UPLOAD_1')
    expect(script).toContain('page.locator("#file").set_input_files(upload_path)')
    expect(script).toContain('with page.expect_download() as download_info:')
    expect(script).toContain('ATP_WEB_DOWNLOAD_2')
    expect(script).toContain('assert_visual(page, baseline_path, 0.02, 12')
    expect(script).toContain('from PIL import Image, ImageChops')
  })

  it('expands page objects and element assets when generating Web Python', () => {
    const script = generateWebPythonScript(
      [
        { action: 'page_object', name: '登录对象', params: { page_object_id: 7 } },
        { action: 'click', name: '资产按钮', params: { element_asset_id: 11 } },
      ],
      {
        elementAssets: [{ id: 11, locator: { strategy: 'css', value: '#login' } }],
        pageObjects: [{
          id: 7,
          element_refs: [{ alias: 'submit', asset_id: 11 }],
          actions: [{ name: '点击提交', step: 'click', alias: 'submit', params: {} }],
        }],
      },
    )

    expect(script).toContain('page.locator("#login").click()')
    expect(script).not.toContain('页面对象步骤需要')
    expect(script).not.toContain('未支持的低代码动作')
  })

  it('fails explicitly instead of silently dropping unknown Web actions', () => {
    const script = generateWebPythonScript([{ action: 'unknown_action', name: '未知步骤', params: {} }])

    expect(script).toContain('pytest.fail("未支持的低代码动作：unknown_action")')
  })
})
