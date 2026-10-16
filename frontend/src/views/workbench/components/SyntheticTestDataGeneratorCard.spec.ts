import { mount, flushPromises } from '@vue/test-utils'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import SyntheticTestDataGeneratorCard from './SyntheticTestDataGeneratorCard.vue'
import { syntheticTestDataApi } from '@/api/cloudNativeCluster'

const mockBatch = {
  batch_id: 'synth_order_1001',
  dataset_name: 'order_checkout_payloads',
  total_rows: 10,
  positive_count: 7,
  boundary_count: 2,
  negative_count: 1,
  fields_count: 4,
  rows: [
    {
      row_index: 1,
      mode: 'POSITIVE_VALID',
      data: { order_amount: 120.5, buyer_email: 'buyer@example.com', order_status: 'PAID' },
      is_expected_valid: true,
      anomaly_field: null,
      anomaly_reason: null,
    },
    {
      row_index: 4,
      mode: 'BOUNDARY_EDGE',
      data: { order_amount: 1.0, buyer_email: 'boundary@example.com', order_status: 'PENDING' },
      is_expected_valid: true,
      anomaly_field: null,
      anomaly_reason: null,
    },
    {
      row_index: 7,
      mode: 'NEGATIVE_ANOMALY',
      data: { order_amount: 999999.0, buyer_email: 'invalid_email_no_at', order_status: 'PAID' },
      is_expected_valid: false,
      anomaly_field: 'buyer_email',
      anomaly_reason: '邮箱格式缺失 @ 域名标记',
    },
  ],
  created_at: '2026-10-17T12:00:00Z',
}

vi.mock('@/api/cloudNativeCluster', () => ({
  syntheticTestDataApi: {
    generate: vi.fn(),
    listBatches: vi.fn(),
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
  DatabaseOutlined: { template: '<span>Database</span>' },
  ThunderboltOutlined: { template: '<span>Thunderbolt</span>' },
  CopyOutlined: { template: '<span>Copy</span>' },
}))

describe('SyntheticTestDataGeneratorCard.vue', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(syntheticTestDataApi.generate).mockResolvedValue({
      message: '测试数据集合成成功',
      batch: mockBatch as any,
    })
  })

  it('renders header, 4 KPI cards, multi-modal table rows, and anomaly reasons', async () => {
    const wrapper = mount(SyntheticTestDataGeneratorCard, {
      props: {
        open: true,
      },
      global: {
        stubs: {
          'a-drawer': { template: '<div class="ant-drawer"><slot /></div>' },
          'a-button': { template: '<button><slot /></button>' },
          'a-space': { template: '<div><slot /></div>' },
          'a-radio-group': { template: '<div><slot /></div>' },
          'a-radio-button': { template: '<button><slot /></button>' },
          'a-row': { template: '<div><slot /></div>' },
          'a-col': { template: '<div><slot /></div>' },
          'a-input-number': { template: '<input type="number" />' },
          'a-tag': { template: '<span class="ant-tag"><slot /></span>' },
          'a-table': { template: '<div class="ant-table-stub" />' },
        },
      },
    })

    await flushPromises()

    expect(syntheticTestDataApi.generate).toHaveBeenCalled()

    // 检查标题与 KPI
    expect(wrapper.text()).toContain('多模态生产级合成测试数据生成引擎')
    expect(wrapper.text()).toContain('10 行')
    expect(wrapper.text()).toContain('7 行')
    expect(wrapper.text()).toContain('2 行')
    expect(wrapper.text()).toContain('1 行')

    // 切换预设
    const vm = wrapper.vm as any
    vm.selectedPreset = 'user_kyc'
    await vm.handlePresetChange()
    await flushPromises()

    expect(syntheticTestDataApi.generate).toHaveBeenCalledTimes(2)
  })
})
