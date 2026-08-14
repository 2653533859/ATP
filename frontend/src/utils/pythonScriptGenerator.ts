export type ScriptStep = {
  action: string
  name?: string | null
  params?: Record<string, unknown> | null
}

export type WebScriptElementAsset = {
  id: number
  locator?: Record<string, unknown> | null
  fallback_locators?: Array<Record<string, unknown>> | null
}

export type WebScriptPageObject = {
  id: number
  element_refs?: Array<Record<string, unknown>> | null
  actions?: Array<Record<string, unknown>> | null
}

export type WebScriptGenerationOptions = {
  elementAssets?: WebScriptElementAsset[]
  pageObjects?: WebScriptPageObject[]
}

function paramsOf(step: ScriptStep) {
  return step.params ?? {}
}

function recordOf(value: unknown): Record<string, unknown> {
  return value && typeof value === 'object' && !Array.isArray(value) ? value as Record<string, unknown> : {}
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

function requiredWebSelector(params: Record<string, unknown>, action: string) {
  const selector = stringValue(params.selector).trim()
  return selector ? null : [`    pytest.fail(${pythonString(`${action} 步骤缺少元素定位器`)})`]
}

function locatorValue(locator: Record<string, unknown> | null | undefined) {
  if (!locator) return ''
  const strategy = stringValue(locator.strategy, 'css').trim().toLowerCase()
  const value = stringValue(locator.value).trim()
  if (!value) return ''
  if (strategy === 'xpath') return `xpath=${value}`
  if (strategy === 'test_id' || strategy === 'testid') {
    return `[data-testid="${value.replace(/\\/g, '\\\\').replace(/"/g, '\\"')}"]`
  }
  if (strategy === 'css' || strategy === 'locator') return value
  if (strategy === 'role') {
    const name = stringValue(locator.name).trim()
    return name ? `role=${value}[name="${name.replace(/"/g, '\\"')}"]` : `role=${value}`
  }
  return `${strategy}=${value}`
}

function assetSelector(assetId: unknown, assets: WebScriptElementAsset[]) {
  const id = Number(assetId)
  if (!Number.isInteger(id) || id <= 0) return ''
  const asset = assets.find((item) => item.id === id)
  if (!asset) return ''
  return [asset.locator, ...(asset.fallback_locators ?? [])]
    .map((locator) => locatorValue(locator))
    .find(Boolean) ?? ''
}

function resolveStepParams(params: Record<string, unknown>, assets: WebScriptElementAsset[]) {
  const resolved = { ...params }
  if (!stringValue(resolved.selector).trim() && resolved.element_asset_id != null) {
    const selector = assetSelector(resolved.element_asset_id, assets)
    if (selector) resolved.selector = selector
  }
  return resolved
}

function expandWebSteps(steps: ScriptStep[], options: WebScriptGenerationOptions) {
  const assets = options.elementAssets ?? []
  const pageObjects = options.pageObjects ?? []
  const expanded: ScriptStep[] = []

  for (const step of steps) {
    if (step.action !== 'page_object') {
      expanded.push({ ...step, params: resolveStepParams(paramsOf(step), assets) })
      continue
    }

    const pageObjectId = Number(paramsOf(step).page_object_id)
    const pageObject = pageObjects.find((item) => item.id === pageObjectId)
    if (!pageObject) {
      expanded.push({
        action: '__unsupported__',
        name: step.name ?? `页面对象 ${pageObjectId || ''}`,
        params: { message: `页面对象 ${pageObjectId || '未知'} 未加载，无法生成独立 Python 脚本` },
      })
      continue
    }

    const refs = new Map<string, unknown>()
    for (const ref of pageObject.element_refs ?? []) {
      if (ref.alias != null) refs.set(String(ref.alias), ref.asset_id)
    }
    const actions = pageObject.actions ?? []
    if (!actions.length) {
      expanded.push({
        action: '__unsupported__',
        name: step.name ?? `页面对象 ${pageObjectId || ''}`,
        params: { message: `页面对象 ${pageObjectId || '未知'} 未配置公共动作` },
      })
      continue
    }
    for (const [index, actionDef] of actions.entries()) {
      const action = stringValue(actionDef.step ?? actionDef.action).trim()
      if (!action || action === 'page_object') {
        expanded.push({
          action: '__unsupported__',
          name: `${step.name ?? '页面对象'} / 动作 ${index + 1}`,
          params: { message: '页面对象包含无效公共动作' },
        })
        continue
      }
      const params = resolveStepParams(
        recordOf(actionDef.params),
        assets,
      )
      const alias = actionDef.alias ?? actionDef.element
      const assetId = actionDef.asset_id ?? (alias == null ? undefined : refs.get(String(alias)))
      if (!stringValue(params.selector).trim() && assetId != null) {
        const selector = assetSelector(assetId, assets)
        if (selector) params.selector = selector
      }
      expanded.push({
        action,
        name: `${step.name ?? '页面对象'} / ${stringValue(actionDef.name, `动作 ${index + 1}`)}`,
        params,
      })
    }
  }
  return expanded
}

function visualAssertionHelper() {
  return [
    'def assert_visual(page: Page, baseline_path: str, threshold: float, pixel_threshold: int, diff_path: str):',
    '    baseline_file = Path(baseline_path)',
    '    if not baseline_file.exists():',
    '        pytest.fail(f"视觉基线不存在: {baseline_file}")',
    '    baseline = Image.open(baseline_file).convert("RGBA")',
    '    actual = Image.open(BytesIO(page.screenshot(type="png"))).convert("RGBA")',
    '    if actual.size != baseline.size:',
    '        pytest.fail(f"视觉基线尺寸不一致: {baseline.size} != {actual.size}")',
    '    diff = ImageChops.difference(baseline, actual)',
    '    changed = sum(1 for pixel in diff.getdata() if max(pixel) > pixel_threshold)',
    '    ratio = changed / max(1, baseline.width * baseline.height)',
    '    if ratio > threshold:',
    '        diff_file = Path(diff_path)',
    '        diff_file.parent.mkdir(parents=True, exist_ok=True)',
    '        diff.save(diff_file)',
    '        pytest.fail(f"视觉差异超过阈值: {ratio:.4f} > {threshold:.4f}; 差异图: {diff_file}")',
  ]
}

function androidTarget(params: Record<string, unknown>) {
  const resourceId = stringValue(params.resourceId ?? params.resource_id).trim()
  if (resourceId) return `device(resourceId=${pythonString(resourceId)})`

  const text = stringValue(params.text).trim()
  if (text) return `device(text=${pythonString(text)})`

  const contentDesc = stringValue(params.contentDesc ?? params.content_desc).trim()
  if (contentDesc) return `device(description=${pythonString(contentDesc)})`

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
    case 'click': {
      const missing = requiredWebSelector(params, 'click')
      if (missing) return missing
      return [`    ${webLocator(params.selector)}.click()`]
    }
    case 'fill': {
      const missing = requiredWebSelector(params, 'fill')
      if (missing) return missing
      return [`    ${webLocator(params.selector)}.fill(${pythonString(params.value)})`]
    }
    case 'assert_text':
      return [`    expect(page.locator("body")).to_contain_text(${pythonString(params.text)})`]
    case 'assert_visible': {
      const missing = requiredWebSelector(params, 'assert_visible')
      if (missing) return missing
      return [`    expect(${webLocator(params.selector)}).to_be_visible()`]
    }
    case 'wait':
      return [`    page.wait_for_timeout(${pythonNumber(params.ms, 1000)})`]
    case 'screenshot':
      return [`    page.screenshot(path="screenshots/step_${index + 1}.png")`]
    case 'select': {
      const missing = requiredWebSelector(params, 'select')
      if (missing) return missing
      return [`    ${webLocator(params.selector)}.select_option(${pythonString(params.value)})`]
    }
    case 'press': {
      const selector = stringValue(params.selector).trim()
      return selector
        ? [`    ${webLocator(selector)}.press(${pythonString(params.key ?? 'Enter')})`]
        : [`    page.keyboard.press(${pythonString(params.key ?? 'Enter')})`]
    }
    case 'hover': {
      const missing = requiredWebSelector(params, 'hover')
      if (missing) return missing
      return [`    ${webLocator(params.selector)}.hover()`]
    }
    case 'upload': {
      const missing = requiredWebSelector(params, 'upload')
      if (missing) return missing
      return [
        `    upload_path = os.getenv("ATP_WEB_UPLOAD_${index + 1}", "")`,
        `    if not upload_path: pytest.fail("请设置 ATP_WEB_UPLOAD_${index + 1} 指向待上传文件")`,
        `    ${webLocator(params.selector)}.set_input_files(upload_path)`,
      ]
    }
    case 'download': {
      const missing = requiredWebSelector(params, 'download')
      if (missing) return missing
      return [
        `    download_path = Path(os.getenv("ATP_WEB_DOWNLOAD_${index + 1}", "downloads/step_${index + 1}.bin"))`,
        '    download_path.parent.mkdir(parents=True, exist_ok=True)',
        '    with page.expect_download() as download_info:',
        `        ${webLocator(params.selector)}.click()`,
        '    download_info.value.save_as(str(download_path))',
      ]
    }
    case 'visual_assert':
      return [
        `    baseline_path = os.getenv("ATP_VISUAL_BASELINE_${index + 1}", "baseline_${index + 1}.png")`,
        `    assert_visual(page, baseline_path, ${pythonNumber(params.threshold, 0.01)}, ${pythonNumber(params.pixel_threshold, 10)}, "visual-diffs/step_${index + 1}.png")`,
      ]
    case '__unsupported__':
      return [`    pytest.fail(${pythonString(params.message || '当前步骤无法生成独立 Python 脚本')})`]
    default:
      return [`    pytest.fail(${pythonString(`未支持的低代码动作：${step.action || `步骤 ${index + 1}`}`)})`]
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
    case 'rotate': {
      const orientation = stringValue(params.orientation, 'portrait').trim().toLowerCase()
      const orientationMap: Record<string, string> = {
        portrait: 'natural',
        landscape: 'left',
        reverse_portrait: 'upsidedown',
        reverse_landscape: 'right',
      }
      const value = orientationMap[orientation]
      return value
        ? [`    device.set_orientation(${pythonString(value)})`]
        : [`    pytest.fail(${pythonString(`未知屏幕方向：${orientation || '未配置'}`)})`]
    }
    case 'grant_permission':
    case 'revoke_permission': {
      const packageName = stringValue(params.package).trim()
      const permission = stringValue(params.permission).trim()
      if (!packageName || !permission) {
        return [`    pytest.fail(${pythonString(`${step.action} 步骤需要 package 和 permission`)})`]
      }
      const command = step.action === 'grant_permission' ? 'grant' : 'revoke'
      return [
        `    permission_result = device.shell("pm", "${command}", ${pythonString(packageName)}, ${pythonString(permission)})`,
        '    assert permission_result.exit_code == 0, permission_result.stderr',
      ]
    }
    case 'network_profile': {
      const profile = stringValue(params.profile, 'normal').trim().toLowerCase()
      const commands: Record<string, string[][]> = {
        normal: [['svc', 'wifi', 'enable'], ['svc', 'data', 'enable']],
        wifi_off: [['svc', 'wifi', 'disable']],
        data_off: [['svc', 'data', 'disable']],
        offline: [['svc', 'wifi', 'disable'], ['svc', 'data', 'disable']],
      }
      const profileCommands = commands[profile]
      if (!profileCommands) {
        return [`    pytest.fail(${pythonString(`未知网络配置：${profile || '未配置'}`)})`]
      }
      return profileCommands.flatMap((command, commandIndex) => [
        `    network_result_${commandIndex + 1} = device.shell(${command.map((part) => pythonString(part)).join(', ')})`,
        `    assert network_result_${commandIndex + 1}.exit_code == 0, network_result_${commandIndex + 1}.stderr`,
      ])
    }
    case 'background':
      return [`    device.press("home")`]
    case 'foreground': {
      const packageName = stringValue(params.package).trim()
      return packageName
        ? [`    device.app_start(${pythonString(packageName)})`]
        : [`    pytest.fail("前台步骤需要 package")`]
    }
    default:
      return [`    pytest.fail(${pythonString(`未支持的低代码动作：${step.action || `步骤 ${index + 1}`}`)})`]
  }
}

export function generateWebPythonScript(steps: ScriptStep[], options: WebScriptGenerationOptions = {}) {
  const expandedSteps = expandWebSteps(steps, options)
  const body = expandedSteps.flatMap((step, index) => [commentFor(step, index), ...webStepLines(step, index)])
  if (!body.length) body.push('    pass')

  const hasVisualAssertion = expandedSteps.some((step) => step.action === 'visual_assert')

  return [
    '"""由 ATP Web 低代码步骤生成，可按需调整。"""',
    'import os',
    'from pathlib import Path',
    'import pytest',
    ...(hasVisualAssertion ? ['from io import BytesIO', 'from PIL import Image, ImageChops'] : []),
    '',
    'from playwright.sync_api import Page, expect',
    '',
    ...(hasVisualAssertion ? [...visualAssertionHelper(), ''] : []),
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
