import { mount, flushPromises } from '@vue/test-utils'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import CodeToTestDependencyGraphView from './CodeToTestDependencyGraphView.vue'
import { ciImpactApi } from '@/api/ciImpact'

const mockStats = {
  total_indexed_cases: 5,
  total_indexed_symbols: 8,
  total_indexed_routes: 4,
  total_indexed_files: 3,
}

const mockQueriedCases = [
  {
    case_id: 101,
    case_name: '订单结算优惠抵扣用例',
    case_type: 'api',
    priority: 'P1',
    target_endpoints: ['POST /api/v1/orders/create'],
    target_symbols: ['app/api/orders.py:calculate_discount'],
  },
]

vi.mock('@/api/ciImpact', () => ({
  ciImpactApi: {
    getMappingStats: vi.fn(),
    queryAffectedCases: vi.fn(),
    bindTestCase: vi.fn(),
  },
}))

vi.mock('ant-design-vue', () => ({
  message: {
    success: vi.fn(),
    error: vi.fn(),
    warning: vi.fn(),
  },
}))

vi.mock('@ant-design/icons-vue', () => ({
  ApartmentOutlined: { template: '<span>Apartment</span>' },
  ReloadOutlined: { template: '<span>Reload</span>' },
  PlusOutlined: { template: '<span>Plus</span>' },
}))

vi.mock('@/utils/chartTheme', () => ({
  useChartTheme: () => ({ chartTheme: 'atp-light' }),
}))

vi.mock('vue-echarts', () => ({
  default: {
    name: 'VChart',
    props: ['option'],
    template: '<div class="v-chart-graph-stub" />',
  },
}))

describe('CodeToTestDependencyGraphView.vue', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(ciImpactApi.getMappingStats).mockResolvedValue(mockStats)
    vi.mocked(ciImpactApi.queryAffectedCases).mockResolvedValue({
      total: 1,
      cases: mockQueriedCases,
    })
    vi.mocked(ciImpactApi.bindTestCase).mockResolvedValue({
      message: '血缘依赖绑定成功',
      case: mockQueriedCases[0],
    })
  })

  it('renders page hero, metrics cards, and graph legend', async () => {
    const wrapper = mount(CodeToTestDependencyGraphView, {
      global: {
        stubs: {
          'a-spin': { template: '<div><slot /></div>' },
          'a-tag': { template: '<span class="ant-tag"><slot /></span>' },
          'a-space': { template: '<div><slot /></div>' },
          'a-card': { template: '<div class="ant-card"><slot name="title" /><slot /></div>' },
          'a-input-number': { template: '<input type="number" />' },
          'a-select': { template: '<select><slot /></select>' },
          'a-select-option': { template: '<option><slot /></option>' },
          'a-modal': { template: '<div><slot /></div>' },
          'a-form': { template: '<form><slot /></form>' },
          'a-form-item': { template: '<div><slot /></div>' },
          'a-empty': { template: '<div class="ant-empty" />' },
        },
      },
    })

    await flushPromises()

    // 验证页面标题与统计指标
    expect(wrapper.text()).toContain('代码符号与自动化测试用例双向血缘图谱')
    expect(wrapper.text()).toContain('5')
    expect(wrapper.text()).toContain('8')
    expect(wrapper.text()).toContain('4')
    expect(wrapper.text()).toContain('3')

    // 验证图例渲染
    expect(wrapper.text()).toContain('代码文件')
    expect(wrapper.text()).toContain('函数/类符号')
    expect(wrapper.text()).toContain('API 端点')
    expect(wrapper.text()).toContain('自动化用例')

    expect(ciImpactApi.getMappingStats).toHaveBeenCalled()
  })

  it('triggers impact query and renders matched cases', async () => {
    const wrapper = mount(CodeToTestDependencyGraphView, {
      global: {
        stubs: {
          'a-spin': { template: '<div><slot /></div>' },
          'a-tag': { template: '<span class="ant-tag"><slot /></span>' },
          'a-space': { template: '<div><slot /></div>' },
          'a-button': { template: '<button><slot /></button>' },
          'a-card': { template: '<div class="ant-card"><slot name="title" /><slot /></div>' },
          'a-input': { template: '<input />' },
          'a-input-number': { template: '<input type="number" />' },
          'a-select': { template: '<select><slot /></select>' },
          'a-select-option': { template: '<option><slot /></option>' },
          'a-modal': { template: '<div><slot /></div>' },
          'a-form': { template: '<form><slot /></form>' },
          'a-form-item': { template: '<div><slot /></div>' },
          'a-empty': { template: '<div class="ant-empty" />' },
        },
      },
    })

    await flushPromises()

    const vm = wrapper.vm as any
    vm.queryTarget = 'POST /api/v1/orders/create'
    await vm.handleTraceImpact()

    expect(ciImpactApi.queryAffectedCases).toHaveBeenCalledWith(expect.objectContaining({
      routes: ['POST /api/v1/orders/create'],
    }))

    await flushPromises()

    expect(wrapper.text()).toContain('订单结算优惠抵扣用例')
  })
})
