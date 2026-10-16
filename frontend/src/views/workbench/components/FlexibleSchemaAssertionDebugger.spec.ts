import { mount, flushPromises } from '@vue/test-utils'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import FlexibleSchemaAssertionDebugger from './FlexibleSchemaAssertionDebugger.vue'
import { flexibleAssertionApi } from '@/api/aiHealing'

const mockAssertionPassedResult = {
  audit_id: 'drift_audit_001',
  passed: true,
  tolerance_mode: 'compatible' as const,
  total_drifts_count: 2,
  drifts: [
    {
      field_path: 'coupon_code',
      drift_type: 'extra_field' as const,
      expected: null,
      actual: 'string',
      is_breaking: false,
      description: '检测到未声明的冗余字段 [coupon_code]，兼容模式已放行',
      suggested_autofix: { type: 'string' },
    },
    {
      field_path: 'discount_pct',
      drift_type: 'extra_field' as const,
      expected: null,
      actual: 'number',
      is_breaking: false,
      description: '检测到未声明的冗余字段 [discount_pct]，兼容模式已放行',
      suggested_autofix: { type: 'number' },
    },
  ],
  autofixed_schema: {
    type: 'object',
    required: ['order_id', 'amount', 'currency'],
    properties: {
      order_id: { type: 'string' },
      amount: { type: 'number' },
      currency: { type: 'string' },
      coupon_code: { type: 'string' },
      discount_pct: { type: 'number' },
    },
  },
  evaluated_at: '2026-10-16T12:00:00Z',
  summary: '柔性断言 PASS (模式: compatible)，共检测到 2 处 Schema 响应漂移 (其中破坏性 0 处)。',
}

vi.mock('@/api/aiHealing', () => ({
  flexibleAssertionApi: {
    evaluate: vi.fn(),
    autofix: vi.fn(),
    listHistory: vi.fn(),
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

describe('FlexibleSchemaAssertionDebugger.vue', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders drawer header, tolerance mode radio buttons, and editors', async () => {
    const wrapper = mount(FlexibleSchemaAssertionDebugger, {
      props: {
        open: true,
      },
      global: {
        stubs: {
          'a-drawer': { template: '<div><slot name="title" /><slot /></div>' },
          'a-card': { template: '<div class="ant-card">{{ title }}<slot name="title" /><slot name="extra" /><slot /></div>', props: ['title'] },
          'a-tag': { template: '<span class="ant-tag"><slot /></span>' },
          'a-space': { template: '<div><slot /></div>' },
          'a-radio-group': { template: '<div><slot /></div>' },
          'a-radio-button': { template: '<button><slot /></button>' },
          'a-checkbox': { template: '<label><input type="checkbox" /><slot /></label>' },
          'a-input': { template: '<input />' },
          'a-textarea': { template: '<textarea />' },
          'a-button': { template: '<button><slot /></button>' },
          'a-row': { template: '<div class="ant-row"><slot /></div>' },
          'a-col': { template: '<div class="ant-col"><slot /></div>' },
        },
      },
    })

    await flushPromises()

    expect(wrapper.text()).toContain('接口响应 Schema 动态漂移自适应修正与柔性断言调试器')
    expect(wrapper.text()).toContain('多级契约容差策略与漂移自愈模式配置')
    expect(wrapper.text()).toContain('预期 JSON Schema (Expected Schema)')
    expect(wrapper.text()).toContain('接口实际响应数据 (Actual Payload)')
  })

  it('triggers flexible schema assertion and renders passed alert and drifts', async () => {
    vi.mocked(flexibleAssertionApi.evaluate).mockResolvedValue(mockAssertionPassedResult)

    const wrapper = mount(FlexibleSchemaAssertionDebugger, {
      props: {
        open: true,
      },
      global: {
        stubs: {
          'a-drawer': { template: '<div><slot name="title" /><slot /></div>' },
          'a-card': { template: '<div class="ant-card">{{ title }}<slot name="title" /><slot name="extra" /><slot /></div>', props: ['title'] },
          'a-tag': { template: '<span class="ant-tag"><slot /></span>' },
          'a-space': { template: '<div><slot /></div>' },
          'a-radio-group': { template: '<div><slot /></div>' },
          'a-radio-button': { template: '<button><slot /></button>' },
          'a-checkbox': { template: '<label><slot /></label>' },
          'a-textarea': { template: '<textarea />' },
          'a-button': { template: '<button><slot /></button>' },
          'a-alert': { template: '<div class="ant-alert">{{ message }} {{ description }}</div>', props: ['message', 'description'] },
          'a-row': { template: '<div class="ant-row"><slot /></div>' },
          'a-col': { template: '<div class="ant-col"><slot /></div>' },
          'a-table': {
            template: `
              <div class="ant-table">
                <div v-for="item in dataSource" :key="item.field_path" class="row">
                  <slot name="bodyCell" :column="{ key: 'field_path' }" :record="item" />
                  <slot name="bodyCell" :column="{ key: 'drift_type' }" :record="item" />
                  <slot name="bodyCell" :column="{ key: 'breaking' }" :record="item" />
                </div>
              </div>
            `,
            props: ['dataSource'],
          },
        },
      },
    })

    await flushPromises()

    const evalBtn = wrapper.findAll('button').find((b) => b.text().includes('执行柔性断言'))
    expect(evalBtn).toBeDefined()
    await evalBtn!.trigger('click')
    await flushPromises()

    expect(flexibleAssertionApi.evaluate).toHaveBeenCalledWith({
      expected_schema: expect.any(Object),
      actual_payload: expect.any(Object),
      mode: 'compatible',
      ignore_extra_fields: true,
      allow_numeric_string_coercion: true,
      autofix_schema: true,
    })

    // 验证断言结果渲染
    expect(wrapper.text()).toContain('[柔性断言通过 PASS]')
    expect(wrapper.text()).toContain('响应漂移总数')
    expect(wrapper.text()).toContain('2') // drifts count
    expect(wrapper.text()).toContain('coupon_code')
    expect(wrapper.text()).toContain('良性放行')

    // 验证自愈版 Schema 预览
    expect(wrapper.text()).toContain('AI 自愈修正版 Schema 建议')
  })
})
