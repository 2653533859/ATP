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
})
