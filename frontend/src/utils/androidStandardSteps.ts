import type { CaseStepItem } from '@/api'

export type AndroidLowcodeStep = {
  action: string
  name?: string
  params?: Record<string, unknown>
}

export type AndroidStepTranslator = (key: string) => string

function translateOr(t: AndroidStepTranslator, key: string, fallback: string) {
  const translated = t(key)
  return translated === key ? fallback : translated
}

function formatValue(value: unknown) {
  if (typeof value === 'string') return value
  if (typeof value === 'number' || typeof value === 'boolean') return String(value)
  try {
    return JSON.stringify(value)
  } catch {
    return String(value)
  }
}

function addValue(parts: string[], label: string, value: unknown) {
  if (value === undefined || value === null || value === '') return
  parts.push(`${label}：${formatValue(value)}`)
}

function paramsSummary(step: AndroidLowcodeStep, t: AndroidStepTranslator) {
  const params = step.params ?? {}
  const parts: string[] = []
  const label = (key: string, fallback: string) => translateOr(t, `case.android_standard_steps.params.${key}`, fallback)

  switch (step.action) {
    case 'click':
      addValue(parts, label('text', '文本'), params.text)
      addValue(parts, label('resource_id', '资源 ID'), params.resourceId ?? params.resource_id)
      addValue(parts, label('content_desc', '无障碍描述'), params.contentDesc ?? params.content_desc)
      if (params.x !== undefined && params.y !== undefined) {
        addValue(parts, label('coordinates', '坐标'), `(${params.x}, ${params.y})`)
      }
      break
    case 'long_click':
      addValue(parts, label('text', '文本'), params.text)
      addValue(parts, label('resource_id', '资源 ID'), params.resourceId ?? params.resource_id)
      addValue(parts, label('content_desc', '无障碍描述'), params.contentDesc ?? params.content_desc)
      if (params.x !== undefined && params.y !== undefined) {
        addValue(parts, label('coordinates', '坐标'), `(${params.x}, ${params.y})`)
      }
      addValue(parts, label('duration', '持续时间（毫秒）'), params.duration)
      break
    case 'swipe':
      if (params.direction) {
        addValue(
          parts,
          label('direction', '方向'),
          translateOr(t, `case.android_standard_steps.directions.${params.direction}`, String(params.direction)),
        )
      }
      if ([params.x1, params.y1, params.x2, params.y2].every((value) => value !== undefined)) {
        addValue(parts, label('coordinates', '坐标'), `(${params.x1}, ${params.y1}) → (${params.x2}, ${params.y2})`)
      }
      if (params.screenWidth !== undefined && params.screenHeight !== undefined) {
        addValue(parts, label('screen_size', '录制屏幕'), `${params.screenWidth} × ${params.screenHeight}`)
      }
      addValue(parts, label('duration', '持续时间（毫秒）'), params.duration)
      break
    case 'input':
      addValue(parts, label('text', '输入内容'), params.text ?? params.value)
      addValue(parts, label('target_text', '目标文本'), params.targetText ?? params.target_text)
      addValue(parts, label('resource_id', '资源 ID'), params.resourceId ?? params.resource_id)
      addValue(parts, label('content_desc', '无障碍描述'), params.contentDesc ?? params.content_desc)
      if (params.clear) addValue(parts, label('clear', '清空原内容'), '是')
      break
    case 'press_key':
      addValue(parts, label('key', '按键'), params.key)
      break
    case 'start_app':
      addValue(parts, label('package', '应用包名'), params.package)
      addValue(parts, label('activity', 'Activity'), params.activity)
      break
    case 'stop_app':
      addValue(parts, label('package', '应用包名'), params.package)
      break
    case 'assert_text':
      addValue(parts, label('text', '期望文本'), params.text)
      break
    case 'assert_element':
      addValue(parts, label('resource_id', '资源 ID'), params.resourceId ?? params.resource_id)
      break
    case 'wait':
      addValue(parts, label('duration', '等待时间（毫秒）'), params.ms)
      break
    default:
      for (const [key, value] of Object.entries(params)) {
        addValue(parts, key, value)
      }
  }

  return parts.join('；')
}

function standardActionName(step: AndroidLowcodeStep, t: AndroidStepTranslator) {
  const customName = step.name?.trim()
  if (customName && !/^(步骤|Step)\s*#?\d+$/i.test(customName)) return customName
  return translateOr(t, `case.android_standard_steps.actions.${step.action}`, step.action || '自动化操作')
}

export function buildAndroidStandardSteps(
  steps: AndroidLowcodeStep[],
  t: AndroidStepTranslator,
): CaseStepItem[] {
  return steps.map((step, index) => ({
    step_no: index + 1,
    action: standardActionName(step, t),
    test_data: paramsSummary(step, t) || null,
    expected_result: translateOr(
      t,
      `case.android_standard_steps.expected.${step.action}`,
      '步骤执行成功',
    ),
    is_key_step: index === 0,
    remarks: null,
  }))
}
