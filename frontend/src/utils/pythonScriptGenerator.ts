export type ScriptStep = {
  action: string
  name?: string | null
  params?: Record<string, unknown> | null
}

function paramsOf(step: ScriptStep) {
  return step.params ?? {}
}

function stringValue(value: unknown, fallback = '') {
  return typeof value === 'string' ? value : value == null ? fallback : String(value)
}

function pythonString(value: unknown) {
  const text = stringValue(value)
  const variable = /^\{\{([A-Za-z_]\w*)\}\}$/.exec(text)
  if (variable) {
    return `os.getenv(${JSON.stringify(variable[1])}, "")`
  }
  return JSON.stringify(text)
}

function pythonNumber(value: unknown, fallback: number) {
  const number = typeof value === 'number' ? value : Number(value)
  return Number.isFinite(number) ? String(number) : String(fallback)
}

function commentFor(step: ScriptStep, index: number) {
  const name = stringValue(step.name, `步骤 ${index + 1}`).replace(/[\r\n]+/g, ' ').trim()
  return `    # ${String(index + 1).padStart(2, '0')}. ${name}`
}

function webLocator(selector: unknown) {
  const value = stringValue(selector).trim()
  return value ? `page.locator(${pythonString(value)})` : 'page.locator("body")'
}

function androidTarget(params: Record<string, unknown>) {
  const resourceId = stringValue(params.resourceId ?? params.resource_id).trim()
  if (resourceId) return `device(resourceId=${pythonString(resourceId)})`

  const text = stringValue(params.text).trim()
  if (text) return `device(text=${pythonString(text)})`

  return null
}

function androidKey(value: unknown) {
  const key = stringValue(value, 'BACK').toUpperCase()
  const keys: Record<string, string> = {
    HOME: 'home',
    BACK: 'back',
    ENTER: 'enter',
    MENU: 'menu',
    RECENT: 'recent',
    DELETE: 'delete',
    POWER: 'power',
    VOLUME_UP: 'volume_up',
    VOLUME_DOWN: 'volume_down',
  }
  return keys[key] ?? key.toLowerCase()
}

function webStepLines(step: ScriptStep, index: number) {
  const params = paramsOf(step)
  switch (step.action) {
    case 'goto':
      return [`    page.goto(${pythonString(params.url)})`]
    case 'click':
      return [`    ${webLocator(params.selector)}.click()`]
    case 'fill':
      return [`    ${webLocator(params.selector)}.fill(${pythonString(params.value)})`]
    case 'assert_text':
      return [`    expect(page.locator("body")).to_contain_text(${pythonString(params.text)})`]
    case 'assert_visible':
      return [`    expect(${webLocator(params.selector)}).to_be_visible()`]
    case 'wait':
      return [`    page.wait_for_timeout(${pythonNumber(params.ms, 1000)})`]
    case 'screenshot':
      return [`    page.screenshot(path="screenshots/step_${index + 1}.png")`]
    case 'select':
      return [`    ${webLocator(params.selector)}.select_option(${pythonString(params.value)})`]
    case 'press': {
      const selector = stringValue(params.selector).trim()
      return selector
        ? [`    ${webLocator(selector)}.press(${pythonString(params.key ?? 'Enter')})`]
        : [`    page.keyboard.press(${pythonString(params.key ?? 'Enter')})`]
    }
    case 'hover':
      return [`    ${webLocator(params.selector)}.hover()`]
    default:
      return [`    # 未支持的低代码动作：${step.action || `步骤 ${index + 1}`}（请手动补充）`]
  }
}

function androidStepLines(step: ScriptStep, index: number) {
  const params = paramsOf(step)
  const target = androidTarget(params)

  switch (step.action) {
    case 'click':
      return target
        ? [`    ${target}.click()`]
        : params.x != null && params.y != null
          ? [`    device.click(${pythonNumber(params.x, 0)}, ${pythonNumber(params.y, 0)})`]
          : [`    pytest.fail("点击步骤缺少 resourceId、文本或坐标")`]
    case 'long_click':
      return target
        ? [`    ${target}.long_click(duration=${pythonNumber(params.duration, 1000)} / 1000)`]
        : params.x != null && params.y != null
          ? [`    device.long_click(${pythonNumber(params.x, 0)}, ${pythonNumber(params.y, 0)}, duration=${pythonNumber(params.duration, 1000)} / 1000)`]
          : [`    pytest.fail("长按步骤缺少定位信息")`]
    case 'swipe': {
      const direction = stringValue(params.direction).toLowerCase()
      const directionCoordinates: Record<string, [number, number, number, number]> = {
        up: [540, 1600, 540, 400],
        down: [540, 400, 540, 1600],
        left: [900, 960, 100, 960],
        right: [100, 960, 900, 960],
      }
      const coordinates = directionCoordinates[direction] ?? [
        Number(params.x1 ?? params.startX),
        Number(params.y1 ?? params.startY),
        Number(params.x2 ?? params.endX),
        Number(params.y2 ?? params.endY),
      ]
      if (coordinates.every(Number.isFinite)) {
        return [`    device.swipe(${coordinates.join(', ')}, duration=${pythonNumber(params.duration, 300)} / 1000)`]
      }
      return [`    pytest.fail("滑动步骤缺少方向或坐标")`]
    }
    case 'input': {
      const value = pythonString(params.text ?? params.value)
      if (target) {
        const lines = [`    input_target = ${target}`, '    input_target.click()']
        if (params.clear) lines.push('    input_target.clear_text()')
        lines.push(`    input_target.set_text(${value})`)
        return lines
      }
      return [`    device.send_keys(${value}, clear=${params.clear ? 'True' : 'False'})`]
    }
    case 'press_key':
      return [`    device.press(${pythonString(androidKey(params.key))})`]
    case 'start_app': {
      const packageName = pythonString(params.package)
      const activity = stringValue(params.activity).trim()
      return activity
        ? [`    device.app_start(${packageName}, activity=${pythonString(activity)})`]
        : [`    device.app_start(${packageName})`]
    }
    case 'stop_app':
      return [`    device.app_stop(${pythonString(params.package)})`]
    case 'assert_text':
      return [`    assert device(text=${pythonString(params.text)}).exists, ${pythonString(`页面未找到文本：${stringValue(params.text)}`)}`]
    case 'assert_element':
      return [`    assert device(resourceId=${pythonString(params.resourceId ?? params.resource_id)}).exists, ${pythonString(`页面未找到元素：${stringValue(params.resourceId ?? params.resource_id)}`)}`]
    case 'wait':
      return [`    time.sleep(${pythonNumber(params.ms, 1000)} / 1000)`]
    case 'screenshot':
      return [`    device.screenshot("screenshots/step_${index + 1}.png")`]
    default:
      return [`    # 未支持的低代码动作：${step.action || `步骤 ${index + 1}`}（请手动补充）`]
  }
}

export function generateWebPythonScript(steps: ScriptStep[]) {
  const body = steps.flatMap((step, index) => [commentFor(step, index), ...webStepLines(step, index)])
  if (!body.length) body.push('    pass')

  return [
    '"""由 ATP Web 低代码步骤生成，可按需调整。"""',
    'import os',
    '',
    'from playwright.sync_api import Page, expect',
    '',
    '',
    'def test_recorded_case(page: Page):',
    ...body,
    '',
  ].join('\n')
}

export function generateAndroidPythonScript(steps: ScriptStep[]) {
  const body = steps.flatMap((step, index) => [commentFor(step, index), ...androidStepLines(step, index)])
  if (!body.length) body.push('    pass')

  return [
    '"""由 ATP Android 低代码步骤生成，可按需调整。"""',
    'import time',
    '',
    'import pytest',
    'import uiautomator2 as u2',
    '',
    '',
    '@pytest.fixture(scope="session")',
    'def device(device_serial):',
    '    return u2.connect(device_serial)',
    '',
    '',
    'def test_recorded_case(device):',
    ...body,
    '',
  ].join('\n')
}
