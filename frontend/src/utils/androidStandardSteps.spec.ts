import { describe, expect, it } from 'vitest'
import { buildAndroidStandardSteps } from './androidStandardSteps'

const translate = (key: string) => ({
  'case.android_standard_steps.actions.click': '点击元素',
  'case.android_standard_steps.actions.input': '输入文本',
  'case.android_standard_steps.expected.click': '元素点击成功',
  'case.android_standard_steps.expected.input': '输入内容正确',
  'case.android_standard_steps.params.text': '文本',
  'case.android_standard_steps.params.resource_id': '资源 ID',
}[key] ?? key)

describe('buildAndroidStandardSteps', () => {
  it('maps low-code actions to readable standard steps', () => {
    const result = buildAndroidStandardSteps([
      { action: 'click', name: '步骤 1', params: { text: '登录', resourceId: 'com.demo:id/login' } },
      { action: 'input', name: '填写账号', params: { text: 'tester', resourceId: 'com.demo:id/account' } },
    ], translate)

    expect(result).toEqual([
      {
        step_no: 1,
        action: '点击元素',
        test_data: '文本：登录；资源 ID：com.demo:id/login',
        expected_result: '元素点击成功',
        is_key_step: true,
        remarks: null,
      },
      {
        step_no: 2,
        action: '填写账号',
        test_data: '文本：tester；资源 ID：com.demo:id/account',
        expected_result: '输入内容正确',
        is_key_step: false,
        remarks: null,
      },
    ])
  })

  it('keeps empty parameters readable and preserves custom names', () => {
    const result = buildAndroidStandardSteps([
      { action: 'wait', name: '等待页面稳定', params: { ms: 1000 } },
      { action: 'screenshot', name: '步骤 2', params: {} },
    ], translate)

    expect(result[0].action).toBe('等待页面稳定')
    expect(result[0].test_data).toBe('等待时间（毫秒）：1000')
    expect(result[1].action).toBe('screenshot')
    expect(result[1].test_data).toBeNull()
  })
})
