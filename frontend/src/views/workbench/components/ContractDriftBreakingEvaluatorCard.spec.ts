import { mount, flushPromises } from '@vue/test-utils'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import ContractDriftBreakingEvaluatorCard from './ContractDriftBreakingEvaluatorCard.vue'
import { contractBreakingApi } from '@/api/trafficGateway'

const mockBreakingReport = {
  evaluation_id: 'ev_test_101',
  endpoint: 'POST /api/v1/orders/checkout',
  overall_breaking_level: 'BREAKING',
  is_breaking: true,
  compatibility_score_pct: 50.0,
  breaking_changes_count: 2,
  warning_changes_count: 0,
  compatible_changes_count: 0,
  drift_items: [
    {
      field_path: '$.request.coupon_id',
      target: 'REQUEST_BODY',
      change_type: 'REQUIRED_ADDED',
      breaking_level: 'BREAKING',
      design_value: undefined,
      live_value: { type: 'string' },
      description: '请求体新增必填字段',
      impact_summary: '旧版客户端未传此字段将导致 HTTP 400 校验拒绝',
    },
    {
      field_path: '$.response.200.pay_token',
      target: 'RESPONSE_BODY',
      change_type: 'FIELD_REMOVED',
      breaking_level: 'BREAKING',
      design_value: { type: 'string' },
      live_value: undefined,
      description: '响应体删除了既有属性',
      impact_summary: '下游调用方若反序列化此字段将发生 KeyError 或空指针崩溃',
    },
  ],
  verdict_summary: '检测到 2 处严重破坏性变更 (Breaking Change)，严禁直接发布！',
  evaluated_at: '2026-10-16T12:00:00Z',
}

const mockCompatibleReport = {
  evaluation_id: 'ev_test_102',
  endpoint: 'GET /api/v1/users/profile',
  overall_breaking_level: 'COMPATIBLE',
  is_breaking: false,
  compatibility_score_pct: 100.0,
  breaking_changes_count: 0,
  warning_changes_count: 0,
  compatible_changes_count: 1,
  drift_items: [
    {
      field_path: '$.response.200.avatar_url',
      target: 'RESPONSE_BODY',
      change_type: 'FIELD_ADDED',
      breaking_level: 'COMPATIBLE',
      design_value: undefined,
      live_value: { type: 'string' },
      description: '响应体扩展新属性',
      impact_summary: '符合伯斯塔尔健壮性法则，向下兼容',
    },
  ],
  verdict_summary: '契约完全向前兼容，无阻断性变更。',
  evaluated_at: '2026-10-16T12:05:00Z',
}

vi.mock('@/api/trafficGateway', () => ({
  contractBreakingApi: {
    compare: vi.fn(),
    compareByIds: vi.fn(),
    listReports: vi.fn(),
    getReport: vi.fn(),
    clearReports: vi.fn(),
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
  SafetyCertificateOutlined: { template: '<span>SafetyCertificate</span>' },
  ThunderboltOutlined: { template: '<span>Thunderbolt</span>' },
}))

describe('ContractDriftBreakingEvaluatorCard.vue', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(contractBreakingApi.compare).mockResolvedValue({
      message: '契约兼容性评估完成',
      report: mockBreakingReport as any,
    })
  })

  it('renders verdict banner with BREAKING status, compatibility score, and action recommendations', async () => {
    const wrapper = mount(ContractDriftBreakingEvaluatorCard, {
      global: {
        stubs: {
          'a-button': { template: '<button><slot /></button>' },
          'a-space': { template: '<div><slot /></div>' },
          'a-input': { template: '<input />' },
          'a-tag': { template: '<span class="ant-tag"><slot /></span>' },
          'a-table': {
            props: ['dataSource'],
            template: `
              <div class="ant-table-stub">
                <div v-for="item in dataSource" :key="item.field_path" class="row">
                  <span class="field-path">{{ item.field_path }}</span>
                  <span class="change-type">{{ item.change_type }}</span>
                  <span class="breaking-level">{{ item.breaking_level }}</span>
                </div>
              </div>
            `,
          },
        },
      },
    })

    await flushPromises()

    // 检查调用与标题
    expect(contractBreakingApi.compare).toHaveBeenCalled()
    expect(wrapper.text()).toContain('接口契约非对称破坏性变更 Breaking 评级仲裁引擎')

    // 检查裁决大横幅
    expect(wrapper.text()).toContain('BREAKING')
    expect(wrapper.text()).toContain('50%')
    expect(wrapper.text()).toContain('2') // breaking_changes_count

    // 检查字段路径
    expect(wrapper.text()).toContain('$.request.coupon_id')
    expect(wrapper.text()).toContain('$.response.200.pay_token')

    // 检查阻断修复行动指引
    expect(wrapper.text()).toContain('生产发布阻断与修复指引')
  })

  it('switches to compatible preset and updates verdict banner', async () => {
    vi.mocked(contractBreakingApi.compare).mockResolvedValueOnce({
      message: '契约兼容性评估完成',
      report: mockBreakingReport as any,
    }).mockResolvedValueOnce({
      message: '契约兼容性评估完成',
      report: mockCompatibleReport as any,
    })

    const wrapper = mount(ContractDriftBreakingEvaluatorCard, {
      global: {
        stubs: {
          'a-button': { template: '<button><slot /></button>' },
          'a-space': { template: '<div><slot /></div>' },
          'a-input': { template: '<input />' },
          'a-tag': { template: '<span class="ant-tag"><slot /></span>' },
          'a-table': { template: '<div class="ant-table-stub" />' },
        },
      },
    })

    await flushPromises()

    const vm = wrapper.vm as any
    await vm.applyPreset('compatible')
    await flushPromises()

    expect(contractBreakingApi.compare).toHaveBeenCalledTimes(2)
    expect(wrapper.text()).toContain('COMPATIBLE')
    expect(wrapper.text()).toContain('100%')
  })
})
