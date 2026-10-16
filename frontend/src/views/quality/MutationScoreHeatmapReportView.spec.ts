import { mount, flushPromises } from '@vue/test-utils'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import MutationScoreHeatmapReportView from './MutationScoreHeatmapReportView.vue'
import { ciImpactApi } from '@/api/ciImpact'

const mockScoreReport = {
  score_id: 'score_test_888',
  execution_run_id: 'run_mut_test_999',
  mutation_score_pct: 87.5,
  adequacy_level: 'EXCELLENT',
  total_mutants: 8,
  killed_count: 7,
  survived_count: 1,
  timed_out_count: 0,
  operator_breakdowns: {
    ROR: { operator_type: 'ROR', total_mutants: 3, killed_mutants: 3, survived_mutants: 0, operator_mutation_score_pct: 100.0 },
    LCR: { operator_type: 'LCR', total_mutants: 2, killed_mutants: 2, survived_mutants: 0, operator_mutation_score_pct: 100.0 },
    AOR: { operator_type: 'AOR', total_mutants: 2, killed_mutants: 1, survived_mutants: 1, operator_mutation_score_pct: 50.0 },
    RVO: { operator_type: 'RVO', total_mutants: 1, killed_mutants: 1, survived_mutants: 0, operator_mutation_score_pct: 100.0 },
  },
  blindspots: [
    {
      mutant_id: 'mut_aor_survived_01',
      file_path: 'discount_service.py',
      line_number: 6,
      operator_type: 'AOR',
      original_line: '    discount = price * 0.20',
      mutated_line: '    discount = price / 0.20',
      description: '将第 6 行的算术运算符 * 替换为 /',
      suggested_assertion_fix: '当前用例断言仅校验了 discount > 0，未显式 assert discount == 20.0，建议补充精确数值断言',
    },
  ],
  summary_verdict: '测试用例集变异得分为 87.50% (7/8 击毙)，达到 EXCELLENT 卓越充分度级别。针对存活变异体补充精确数值断言即可实现 100% 盲区覆盖。',
  calculated_at: '2026-10-16T13:00:00Z',
}

vi.mock('@/api/ciImpact', () => ({
  ciImpactApi: {
    listMutationScoreReports: vi.fn(),
    calculateMutationScore: vi.fn(),
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
  FireOutlined: { template: '<span>Fire</span>' },
  ReloadOutlined: { template: '<span>Reload</span>' },
  CalculatorOutlined: { template: '<span>Calculator</span>' },
  SafetyCertificateOutlined: { template: '<span>Safety</span>' },
  ExclamationCircleOutlined: { template: '<span>Exclamation</span>' },
  CheckCircleOutlined: { template: '<span>Check</span>' },
  CopyOutlined: { template: '<span>Copy</span>' },
}))
vi.mock('@/utils/chartTheme', () => ({
  useChartTheme: () => ({ chartTheme: 'atp-light' }),
}))


vi.mock('vue-echarts', () => ({
  default: {
    name: 'VChart',
    props: ['option'],
    template: '<div class="v-chart-stub" />',
  },
}))

describe('MutationScoreHeatmapReportView.vue', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(ciImpactApi.listMutationScoreReports).mockResolvedValue({
      total: 1,
      reports: [mockScoreReport as any],
    })
  })

  it('renders hero title, verdict banner with score 87.5%, and blindspots table', async () => {
    const wrapper = mount(MutationScoreHeatmapReportView, {
      global: {
        stubs: {
          'a-tag': { template: '<span class="ant-tag"><slot /></span>' },
          'a-button': { template: '<button><slot /></button>' },
          'a-space': { template: '<div><slot /></div>' },
          'a-spin': { template: '<div><slot /></div>' },
          'a-radio-group': { template: '<div><slot /></div>' },
          'a-radio-button': { template: '<button><slot /></button>' },
          'a-progress': { template: '<div class="ant-progress" />' },
          'a-modal': { template: '<div><slot /></div>' },
          'a-form': { template: '<form><slot /></form>' },
          'a-form-item': { template: '<div><slot /></div>' },
          'a-input': { template: '<input />' },
          'a-table': {
            props: ['dataSource'],
            template: `
              <div class="ant-table-stub">
                <div v-for="item in dataSource" :key="item.mutant_id" class="row">
                  <span class="file-name">{{ item.file_path }}</span>
                  <span class="fix-text">{{ item.suggested_assertion_fix }}</span>
                </div>
              </div>
            `,
          },
        },
      },
    })

    await flushPromises()

    // 验证标题
    expect(wrapper.text()).toContain('用例变异得分 (Mutation Score) 与断言盲区热力大盘')

    // 验证 API 调用
    expect(ciImpactApi.listMutationScoreReports).toHaveBeenCalled()

    // 验证综合变异得分与充分性评级
    expect(wrapper.text()).toContain('87.5%')
    expect(wrapper.text()).toContain('卓越断言 (EXCELLENT)')
    expect(wrapper.text()).toContain('通过准入门禁 (≥85%)')

    // 验证 KPI 指标
    expect(wrapper.text()).toContain('8') // total
    expect(wrapper.text()).toContain('7') // killed
    expect(wrapper.text()).toContain('1') // survived
    expect(wrapper.text()).toContain('0') // timed out

    // 验证断言盲区热力表格
    expect(wrapper.text()).toContain('discount_service.py')
    expect(wrapper.text()).toContain('当前用例断言仅校验了 discount > 0')
  })

  it('supports applying preset data', async () => {
    const wrapper = mount(MutationScoreHeatmapReportView, {
      global: {
        stubs: {
          'a-tag': { template: '<span class="ant-tag"><slot /></span>' },
          'a-button': { template: '<button><slot /></button>' },
          'a-space': { template: '<div><slot /></div>' },
          'a-spin': { template: '<div><slot /></div>' },
          'a-radio-group': { template: '<div><slot /></div>' },
          'a-radio-button': { template: '<button><slot /></button>' },
          'a-progress': { template: '<div class="ant-progress" />' },
          'a-modal': { template: '<div><slot /></div>' },
          'a-form': { template: '<form><slot /></form>' },
          'a-form-item': { template: '<div><slot /></div>' },
          'a-input': { template: '<input />' },
          'a-table': { template: '<div class="ant-table-stub" />' },
        },
      },
    })

    await flushPromises()

    const vm = wrapper.vm as any
    vm.applyPreset('insufficient')
    await wrapper.vm.$nextTick()

    expect(wrapper.text()).toContain('50.0%')
    expect(wrapper.text()).toContain('欠缺改进 (INSUFFICIENT)')
    expect(wrapper.text()).toContain('门禁告警 (50% ~ 69.9%)')
  })
})
