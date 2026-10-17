import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import PrecisionRegressionWorkbenchView from './PrecisionRegressionWorkbenchView.vue'
import { precisionRegressionApi } from '@/api/precisionRegression'

vi.mock('@/api/precisionRegression', () => ({
  precisionRegressionApi: {
    analyzeAndRecommend: vi.fn().mockResolvedValue({
      message: 'ok',
      diff_symbol_report: { changed_symbols_count: 1, symbols: [] },
      precision_recommendation: {
        analysis_id: 'prec_new_001',
        changed_symbols: ['calculate_discount'],
        impacted_endpoints_count: 2,
        impacted_cases_count: 3,
        total_cases_in_suite: 100,
        regression_reduction_ratio: 0.97,
        estimated_time_saved_seconds: 970.0,
        impacted_cases: [],
      },
    }),
  },
}))

const stubs = {
  'a-button': { template: '<button><slot /></button>' },
  'a-tag': { template: '<span class="ant-tag-stub"><slot /></span>' },
  'a-space': { template: '<div class="ant-space-stub"><slot /></div>' },
  'a-input-search': { template: '<input class="ant-input-search-stub" />' },
  'a-drawer': { template: '<div class="ant-drawer-stub"><slot /></div>' },
  'a-table': {
    props: ['dataSource'],
    template: '<div class="ant-table-stub"><div v-for="item in dataSource" :key="item.analysis_id">{{ item.analysis_id }} {{ item.pr_branch }}</div><slot /></div>',
  },
}

describe('PrecisionRegressionWorkbenchView.vue', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders page header and 4 Bento KPI cards', async () => {
    const wrapper = mount(PrecisionRegressionWorkbenchView, {
      global: { stubs },
    })
    await flushPromises()

    expect(wrapper.text()).toContain('智能用例依赖拓扑与增量精准回归编排中台')
    expect(wrapper.text()).toContain('96.8%')
    expect(wrapper.text()).toContain('精准推荐测试覆盖率')
    expect(wrapper.text()).toContain('用例平均裁剪节省率')
    expect(wrapper.text()).toContain('拓扑并发调度加速比')
    expect(wrapper.text()).toContain('级联避免假失败告警')
  })

  it('handles diff analysis button click', async () => {
    const wrapper = mount(PrecisionRegressionWorkbenchView, {
      global: { stubs },
    })
    await flushPromises()

    const analyzeBtn = wrapper.findAll('button').find((b) => b.text().includes('导入 Diff 影响面分析'))
    expect(analyzeBtn).toBeDefined()
    await analyzeBtn!.trigger('click')
    await flushPromises()

    expect(precisionRegressionApi.analyzeAndRecommend).toHaveBeenCalled()
    expect(wrapper.text()).toContain('prec_new_001')
  })

  it('opens DAG drawer and selection modal', async () => {
    const wrapper = mount(PrecisionRegressionWorkbenchView, {
      global: { stubs },
    })
    await flushPromises()

    const vm = wrapper.vm as any
    vm.openDagDrawer()
    expect(vm.dagDrawerOpen).toBe(true)

    vm.openSelectionModal(vm.precisionTasks[0])
    expect(vm.selectionModalOpen).toBe(true)
  })
})
