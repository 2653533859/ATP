import { mount, flushPromises } from '@vue/test-utils'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import ContractChangeImpactDrawer from './ContractChangeImpactDrawer.vue'
import { assetGraphApi } from '@/api/assetGraph'

const mockImpactReport = {
  method: 'POST',
  path: '/api/v1/orders',
  has_breaking_changes: true,
  diff_summary: {
    breaking_count: 2,
    warning_count: 1,
    compatible_count: 1,
  },
  breaking_changes: [
    {
      change_type: 'breaking' as const,
      field_path: 'order_id',
      rule: 'removed_required_field',
      description: '必填字段 order_id 已从契约中删除',
      baseline_value: 'string',
      current_value: null,
    },
    {
      change_type: 'breaking' as const,
      field_path: 'amount',
      rule: 'type_mismatched',
      description: '字段类型由 number 破坏性变更为 string',
      baseline_value: 'number',
      current_value: 'string',
    },
  ],
  warnings: [
    {
      change_type: 'warning' as const,
      field_path: 'currency',
      rule: 'enum_restricted',
      description: '字段枚举范围被缩减',
    },
  ],
  compatible_changes: [
    {
      change_type: 'compatible' as const,
      field_path: 'discount_code',
      rule: 'added_optional_field',
      description: '新增非必填字段 discount_code',
    },
  ],
  impacted_cases: [
    {
      case_id: 101,
      case_name: '提交普通订单测试用例',
      severity: 'breaking' as const,
      affected_steps: ['step_1: POST /api/v1/orders'],
      reasons: ['接口必填字段 order_id 缺失', '字段 amount 类型不匹配'],
      actionable_remediation: '修改用例入参 Schema，移除 order_id 并转换 amount 为 string',
    },
  ],
  total_impacted_cases_count: 1,
  impacted_plans_count: 1,
  impacted_suites_count: 1,
}

vi.mock('@/api/assetGraph', () => ({
  assetGraphApi: {
    analyzeContractImpact: vi.fn(),
  },
}))

vi.mock('ant-design-vue', () => ({
  message: {
    success: vi.fn(),
    warning: vi.fn(),
    info: vi.fn(),
    error: vi.fn(),
  },
}))

describe('ContractChangeImpactDrawer.vue', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders drawer header, method selector, and schema editors', async () => {
    const wrapper = mount(ContractChangeImpactDrawer, {
      props: {
        open: true,
        defaultProjectId: 1,
      },
      global: {
        stubs: {
          'a-drawer': { template: '<div><slot name="title" /><slot /></div>' },
          'a-card': { template: '<div class="ant-card"><slot /></div>' },
          'a-tag': { template: '<span class="ant-tag"><slot /></span>' },
          'a-space': { template: '<div><slot /></div>' },
          'a-select': { template: '<select><slot /></select>' },
          'a-select-option': { template: '<option><slot /></option>' },
          'a-input': { template: '<input />' },
          'a-textarea': { template: '<textarea />' },
          'a-button': { template: '<button><slot /></button>' },
          'a-row': { template: '<div class="ant-row"><slot /></div>' },
          'a-col': { template: '<div class="ant-col"><slot /></div>' },
        },
      },
    })

    await flushPromises()

    expect(wrapper.text()).toContain('接口契约变更影响面分析与受损用例逆向推导')
    expect(wrapper.text()).toContain('基线契约 (Baseline OpenAPI Schema)')
    expect(wrapper.text()).toContain('当前版本契约 (Current OpenAPI Schema)')
  })

  it('triggers contract impact analysis and displays diff summary and impacted cases', async () => {
    vi.mocked(assetGraphApi.analyzeContractImpact).mockResolvedValue(mockImpactReport)

    const wrapper = mount(ContractChangeImpactDrawer, {
      props: {
        open: true,
        defaultProjectId: 1,
      },
      global: {
        stubs: {
          'a-drawer': { template: '<div><slot name="title" /><slot /></div>' },
          'a-card': { template: '<div class="ant-card"><slot /></div>' },
          'a-tag': { template: '<span class="ant-tag"><slot /></span>' },
          'a-space': { template: '<div><slot /></div>' },
          'a-select': { template: '<select><slot /></select>' },
          'a-select-option': { template: '<option><slot /></option>' },
          'a-input': { template: '<input />' },
          'a-textarea': { template: '<textarea />' },
          'a-button': { template: '<button><slot /></button>' },
          'a-alert': { template: '<div class="ant-alert">{{ message }} {{ description }}</div>', props: ['message', 'description'] },
          'a-row': { template: '<div class="ant-row"><slot /></div>' },
          'a-col': { template: '<div class="ant-col"><slot /></div>' },
          'a-tabs': { template: '<div class="ant-tabs"><slot /></div>' },
          'a-tab-pane': { template: '<div class="ant-tab-pane"><slot /></div>' },
          'a-table': {
            template: `
              <div class="ant-table">
                <div v-for="item in dataSource" :key="item.field_path || item.case_id" class="row">
                  <slot name="bodyCell" :column="{ key: 'change_type' }" :record="item" />
                  <slot name="bodyCell" :column="{ key: 'field_path' }" :record="item" />
                  <slot name="bodyCell" :column="{ key: 'description' }" :record="item" />
                  <slot name="bodyCell" :column="{ key: 'case_name' }" :record="item" />
                  <slot name="bodyCell" :column="{ key: 'severity' }" :record="item" />
                  <slot name="bodyCell" :column="{ key: 'reasons' }" :record="item" />
                  <slot name="bodyCell" :column="{ key: 'remediation' }" :record="item" />
                </div>
              </div>
            `,
            props: ['dataSource'],
          },
        },
      },
    })

    await flushPromises()

    const analyzeBtn = wrapper.findAll('button').find((b) => b.text().includes('开始逆向影响分析'))
    expect(analyzeBtn).toBeDefined()
    await analyzeBtn!.trigger('click')
    await flushPromises()

    expect(assetGraphApi.analyzeContractImpact).toHaveBeenCalledWith({
      method: 'POST',
      path: '/api/v1/orders',
      baseline_schema: expect.any(Object),
      current_schema: expect.any(Object),
      project_id: 1,
    })

    // 验证结果渲染
    expect(wrapper.text()).toContain('2') // breaking count
    expect(wrapper.text()).toContain('1') // warning count
    expect(wrapper.text()).toContain('[契约破坏性风险]')
    expect(wrapper.text()).toContain('必填字段 order_id 已从契约中删除')
    expect(wrapper.text()).toContain('提交普通订单测试用例')
    expect(wrapper.text()).toContain('接口必填字段 order_id 缺失')
  })

  it('emits synthesize-regression event with impacted case IDs', async () => {
    vi.mocked(assetGraphApi.analyzeContractImpact).mockResolvedValue(mockImpactReport)

    const wrapper = mount(ContractChangeImpactDrawer, {
      props: {
        open: true,
        defaultProjectId: 1,
      },
      global: {
        stubs: {
          'a-drawer': { template: '<div><slot name="title" /><slot /></div>' },
          'a-card': { template: '<div class="ant-card"><slot /></div>' },
          'a-tag': { template: '<span class="ant-tag"><slot /></span>' },
          'a-space': { template: '<div><slot /></div>' },
          'a-select': { template: '<select><slot /></select>' },
          'a-select-option': { template: '<option><slot /></option>' },
          'a-input': { template: '<input />' },
          'a-textarea': { template: '<textarea />' },
          'a-button': { template: '<button><slot /></button>' },
          'a-alert': { template: '<div class="ant-alert" />' },
          'a-row': { template: '<div class="ant-row"><slot /></div>' },
          'a-col': { template: '<div class="ant-col"><slot /></div>' },
          'a-tabs': { template: '<div class="ant-tabs"><slot /></div>' },
          'a-tab-pane': { template: '<div class="ant-tab-pane"><slot /></div>' },
          'a-table': { template: '<div class="ant-table" />' },
        },
      },
    })

    await flushPromises()

    // 触发分析
    const analyzeBtn = wrapper.findAll('button').find((b) => b.text().includes('开始逆向影响分析'))
    await analyzeBtn!.trigger('click')
    await flushPromises()

    // 触发合成回归套件按钮
    const synthesizeBtn = wrapper.findAll('button').find((b) => b.text().includes('基于受损用例合成回归套件'))
    expect(synthesizeBtn).toBeDefined()
    await synthesizeBtn!.trigger('click')
    await flushPromises()

    expect(wrapper.emitted('synthesize-regression')).toBeDefined()
    expect(wrapper.emitted('synthesize-regression')![0]).toEqual([[101]])
  })
})
