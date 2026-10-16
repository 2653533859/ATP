import { mount, flushPromises } from '@vue/test-utils'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import MutationExecutionLiveMonitorDrawer from './MutationExecutionLiveMonitorDrawer.vue'
import { ciImpactApi } from '@/api/ciImpact'

const mockReport = {
  run_id: 'run_mut_test_999',
  total_mutants_tested: 3,
  killed_count: 2,
  survived_count: 1,
  timed_out_count: 0,
  error_count: 0,
  kill_rate_pct: 66.67,
  survived_mutant_ids: ['mut_lcr_02'],
  results: [
    {
      mutant_id: 'mut_ror_01',
      status: 'KILLED',
      killing_test_case_id: 101,
      killing_test_case_name: '正向价格优惠折扣用例',
      execution_duration_ms: 12.5,
      error_message: 'AssertionError: expected 80.0 but got 0.0',
      line_number: 2,
      operator_type: 'ROR',
      description: '将 <= 替换为 >',
    },
    {
      mutant_id: 'mut_lcr_02',
      status: 'SURVIVED',
      killing_test_case_id: null,
      killing_test_case_name: null,
      execution_duration_ms: 8.3,
      error_message: null,
      line_number: 5,
      operator_type: 'LCR',
      description: '将 and 替换为 or',
    },
    {
      mutant_id: 'mut_aor_03',
      status: 'KILLED',
      killing_test_case_id: 103,
      killing_test_case_name: 'VIP 会员阶梯满减计算用例',
      execution_duration_ms: 15.1,
      error_message: 'AssertionError: expected 20.0 but got 500.0',
      line_number: 6,
      operator_type: 'AOR',
      description: '将 * 替换为 /',
    },
  ],
  executed_at: '2026-10-16T12:30:00Z',
}

vi.mock('@/api/ciImpact', () => ({
  ciImpactApi: {
    runMutationExecution: vi.fn(),
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
  BugOutlined: { template: '<span>Bug</span>' },
  PlayCircleOutlined: { template: '<span>Play</span>' },
  CheckCircleOutlined: { template: '<span>Check</span>' },
  ExclamationCircleOutlined: { template: '<span>Exclamation</span>' },
  ClockCircleOutlined: { template: '<span>Clock</span>' },
  CloseCircleOutlined: { template: '<span>Close</span>' },
}))

describe('MutationExecutionLiveMonitorDrawer.vue', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(ciImpactApi.runMutationExecution).mockResolvedValue({
      message: '变异体执行检验完成',
      report: mockReport as any,
    })
  })

  it('renders drawer header, KPI metrics, and results table with killing case info', async () => {
    const wrapper = mount(MutationExecutionLiveMonitorDrawer, {
      props: {
        open: true,
        initialMutantIds: ['mut_ror_01', 'mut_lcr_02', 'mut_aor_03'],
      },
      global: {
        stubs: {
          'a-drawer': { template: '<div class="ant-drawer"><slot /></div>' },
          'a-tag': { template: '<span class="ant-tag"><slot /></span>' },
          'a-button': { template: '<button><slot /></button>' },
          'a-spin': { template: '<div><slot /></div>' },
          'a-input': { template: '<input />' },
          'a-input-number': { template: '<input type="number" />' },
          'a-radio-group': { template: '<div><slot /></div>' },
          'a-radio-button': { template: '<button><slot /></button>' },
          'a-progress': { template: '<div class="ant-progress" />' },
          'a-table': {
            props: ['dataSource'],
            template: `
              <div class="ant-table-stub">
                <div v-for="item in dataSource" :key="item.mutant_id" class="row">
                  <span class="mutant-desc">{{ item.description }}</span>
                  <span class="status-badge">{{ item.status }}</span>
                  <span class="killing-case">{{ item.killing_test_case_name }}</span>
                </div>
              </div>
            `,
          },
        },
      },
    })

    await flushPromises()

    // 验证标题与介绍
    expect(wrapper.text()).toContain('变异体沙箱动态执行与击杀捕获流水线')

    // 验证 API 调用
    expect(ciImpactApi.runMutationExecution).toHaveBeenCalledWith(expect.objectContaining({
      mutant_ids: ['mut_ror_01', 'mut_lcr_02', 'mut_aor_03'],
      timeout_sec_per_mutant: 3.0,
    }))

    // 验证 KPI 指标
    expect(wrapper.text()).toContain('已验证变异体总数')
    expect(wrapper.text()).toContain('3') // total
    expect(wrapper.text()).toContain('2') // killed
    expect(wrapper.text()).toContain('1') // survived
    expect(wrapper.text()).toContain('66.67%') // kill rate

    // 验证表格内容与击毙定位
    expect(wrapper.text()).toContain('将 <= 替换为 >')
    expect(wrapper.text()).toContain('KILLED')
    expect(wrapper.text()).toContain('正向价格优惠折扣用例')
    expect(wrapper.text()).toContain('SURVIVED')
  })

  it('filters results by status', async () => {
    const wrapper = mount(MutationExecutionLiveMonitorDrawer, {
      props: {
        open: true,
      },
      global: {
        stubs: {
          'a-drawer': { template: '<div class="ant-drawer"><slot /></div>' },
          'a-tag': { template: '<span class="ant-tag"><slot /></span>' },
          'a-button': { template: '<button><slot /></button>' },
          'a-spin': { template: '<div><slot /></div>' },
          'a-input': { template: '<input />' },
          'a-input-number': { template: '<input type="number" />' },
          'a-radio-group': { template: '<div><slot /></div>' },
          'a-radio-button': { template: '<button><slot /></button>' },
          'a-progress': { template: '<div class="ant-progress" />' },
          'a-table': { template: '<div class="ant-table-stub" />' },
        },
      },
    })

    await flushPromises()

    const vm = wrapper.vm as any
    expect(vm.filteredResults.length).toBe(3)

    // 切换至仅击毙
    vm.statusFilter = 'KILLED'
    expect(vm.filteredResults.length).toBe(2)

    // 切换至仅存活
    vm.statusFilter = 'SURVIVED'
    expect(vm.filteredResults.length).toBe(1)
    expect(vm.filteredResults[0].mutant_id).toBe('mut_lcr_02')
  })
})
