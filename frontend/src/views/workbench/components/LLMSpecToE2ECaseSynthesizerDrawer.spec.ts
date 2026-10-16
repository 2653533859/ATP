import { mount, flushPromises } from '@vue/test-utils'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import LLMSpecToE2ECaseSynthesizerDrawer from './LLMSpecToE2ECaseSynthesizerDrawer.vue'
import { llmSpecCaseSynthesizerApi } from '@/api/cloudNativeCluster'

const mockCase = {
  case_id: 'e2e_ecom_flow_1001',
  spec_title: '电商交易闭环测试',
  description: '用户先登录认证获取凭据与用户标识，随后创建交易订单，最后调用收银台完成支付结算。',
  steps_count: 3,
  steps: [
    {
      step_index: 1,
      step_name: '用户认证登录',
      endpoint: '/api/v1/auth/login',
      method: 'POST',
      request_payload: { username: 'test_user', password: 'password123' },
      extracted_variables: { LOGIN_TOKEN: '$.data.token', LOGIN_USER_ID: '$.data.user_id' },
      assertions: [{ type: 'status_code', expected: 200 }],
    },
    {
      step_index: 2,
      step_name: '创建交易订单',
      endpoint: '/api/v1/orders/create',
      method: 'POST',
      request_payload: { user_id: '${LOGIN_USER_ID}', amount: 99.9 },
      extracted_variables: { ORDER_ID: '$.data.order_id' },
      assertions: [{ type: 'status_code', expected: 200 }],
    },
    {
      step_index: 3,
      step_name: '收银台支付确认',
      endpoint: '/api/v1/payments/checkout',
      method: 'POST',
      request_payload: { order_id: '${ORDER_ID}' },
      extracted_variables: {},
      assertions: [{ type: 'status_code', expected: 200 }],
    },
  ],
  generated_python_script: 'import pytest\nimport httpx\n\n@pytest.mark.asyncio\nasync def test_e2e_ecom():\n    pass',
  flow_completeness_score_pct: 95.0,
  created_at: '2026-10-17T12:00:00Z',
}

vi.mock('@/api/cloudNativeCluster', () => ({
  llmSpecCaseSynthesizerApi: {
    generate: vi.fn(),
    listCases: vi.fn(),
  },
}))

vi.mock('ant-design-vue', () => ({
  message: {
    success: vi.fn(),
    warning: vi.fn(),
    error: vi.fn(),
    info: vi.fn(),
  },
}))

vi.mock('@ant-design/icons-vue', () => ({
  RobotOutlined: { template: '<span>Robot</span>' },
  ThunderboltOutlined: { template: '<span>Thunderbolt</span>' },
  ApartmentOutlined: { template: '<span>Apartment</span>' },
  CodeOutlined: { template: '<span>Code</span>' },
  CopyOutlined: { template: '<span>Copy</span>' },
}))

describe('LLMSpecToE2ECaseSynthesizerDrawer.vue', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(llmSpecCaseSynthesizerApi.generate).mockResolvedValue({
      message: '用例生成完成',
      case: mockCase as any,
    })
  })

  it('renders header, KPI cards, DAG steps, and Python script', async () => {
    const wrapper = mount(LLMSpecToE2ECaseSynthesizerDrawer, {
      props: {
        open: true,
      },
      global: {
        stubs: {
          'a-drawer': { template: '<div class="ant-drawer"><slot /></div>' },
          'a-button': { template: '<button><slot /></button>' },
          'a-radio-group': { template: '<div><slot /></div>' },
          'a-radio-button': { template: '<button><slot /></button>' },
          'a-row': { template: '<div><slot /></div>' },
          'a-col': { template: '<div><slot /></div>' },
          'a-input': { template: '<input />' },
          'a-tag': { template: '<span class="ant-tag"><slot /></span>' },
          'a-empty': { template: '<div><slot /></div>' },
        },
      },
    })

    await flushPromises()

    expect(llmSpecCaseSynthesizerApi.generate).toHaveBeenCalled()

    // 检查标题与 KPI
    expect(wrapper.text()).toContain('LLM 驱动的时序依赖 DAG 自动推导与代码级用例合成引擎')
    expect(wrapper.text()).toContain('3 步')
    expect(wrapper.text()).toContain('95%')

    // 检查时序步骤与端点
    expect(wrapper.text()).toContain('/api/v1/auth/login')
    expect(wrapper.text()).toContain('/api/v1/orders/create')
    expect(wrapper.text()).toContain('/api/v1/payments/checkout')

    // 检查变量提取
    expect(wrapper.text()).toContain('$LOGIN_TOKEN')
    expect(wrapper.text()).toContain('$ORDER_ID')

    // 检查 Python 脚本渲染
    expect(wrapper.text()).toContain('async def test_e2e_ecom')

    // 切换预设
    const vm = wrapper.vm as any
    vm.selectedPreset = 'account_flow'
    await vm.handlePresetChange()
    await flushPromises()

    expect(llmSpecCaseSynthesizerApi.generate).toHaveBeenCalledTimes(2)
  })
})
