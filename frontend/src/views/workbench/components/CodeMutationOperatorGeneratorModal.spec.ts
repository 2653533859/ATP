import { mount, flushPromises } from '@vue/test-utils'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import CodeMutationOperatorGeneratorModal from './CodeMutationOperatorGeneratorModal.vue'
import { ciImpactApi } from '@/api/ciImpact'

const mockReport = {
  generation_id: 'gen_test_123',
  file_path: 'discount_service.py',
  total_mutants_generated: 3,
  operator_distribution: {
    ROR: 1,
    LCR: 1,
    AOR: 1,
  },
  target_lines_count: 2,
  mutants: [
    {
      mutant_id: 'mut_ror_1',
      file_path: 'discount_service.py',
      line_number: 2,
      operator_type: 'ROR',
      original_token: '<=',
      mutated_token: '>',
      original_line: '    if price <= 0:',
      mutated_line: '    if price > 0:',
      mutated_code: 'def calculate_discount(price: float):\n    if price > 0:\n        return 0.0\n    return price\n',
      description: '将第 2 行的关系运算符 <= 替换为 >',
    },
    {
      mutant_id: 'mut_lcr_2',
      file_path: 'discount_service.py',
      line_number: 5,
      operator_type: 'LCR',
      original_token: 'and',
      mutated_token: 'or',
      original_line: '    if is_vip and coupon_count > 0:',
      mutated_line: '    if is_vip or coupon_count > 0:',
      mutated_code: 'def calculate_discount(price: float):\n    if is_vip or coupon_count > 0:\n        return price * 0.2\n',
      description: '将第 5 行的逻辑连接符 and 替换为 or',
    },
    {
      mutant_id: 'mut_aor_3',
      file_path: 'discount_service.py',
      line_number: 6,
      operator_type: 'AOR',
      original_token: '*',
      mutated_token: '/',
      original_line: '        discount = price * 0.20',
      mutated_line: '        discount = price / 0.20',
      mutated_code: 'def calculate_discount(price: float):\n        discount = price / 0.20\n',
      description: '将第 6 行的算术运算符 * 替换为 /',
    },
  ],
  created_at: '2026-10-16T12:00:00Z',
}

vi.mock('@/api/ciImpact', () => ({
  ciImpactApi: {
    generateMutants: vi.fn(),
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
  ThunderboltOutlined: { template: '<span>Thunderbolt</span>' },
  CodeOutlined: { template: '<span>Code</span>' },
  ExperimentOutlined: { template: '<span>Experiment</span>' },
  CopyOutlined: { template: '<span>Copy</span>' },
}))

describe('CodeMutationOperatorGeneratorModal.vue', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(ciImpactApi.generateMutants).mockResolvedValue({
      message: '一阶代码语法变异体生成完成',
      report: mockReport as any,
    })
  })

  it('renders modal content, operator tags, and generates mutants on open', async () => {
    const wrapper = mount(CodeMutationOperatorGeneratorModal, {
      props: {
        open: true,
      },
      global: {
        stubs: {
          'a-modal': { template: '<div class="ant-modal"><slot /></div>' },
          'a-tag': { template: '<span class="ant-tag"><slot /></span>' },
          'a-button': { template: '<button><slot /></button>' },
          'a-spin': { template: '<div><slot /></div>' },
          'a-textarea': { template: '<textarea />' },
          'a-input': { template: '<input />' },
          'a-input-number': { template: '<input type="number" />' },
          'a-space': { template: '<div><slot /></div>' },
          'a-empty': { template: '<div class="ant-empty" />' },
        },
      },
    })

    await flushPromises()

    // 检查标题与算子
    expect(wrapper.text()).toContain('AST 一阶语法变异注入引擎')
    expect(wrapper.text()).toContain('ROR')
    expect(wrapper.text()).toContain('LCR')
    expect(wrapper.text()).toContain('AOR')
    expect(wrapper.text()).toContain('RVO')
    expect(wrapper.text()).toContain('BVO')

    // 检查 API 调用
    expect(ciImpactApi.generateMutants).toHaveBeenCalledWith(expect.objectContaining({
      file_path: 'discount_service.py',
      max_mutants: 25,
    }))

    // 检查 KPI 指标呈现
    expect(wrapper.text()).toContain('已生成变异体总数')
    expect(wrapper.text()).toContain('3') // total generated
    expect(wrapper.text()).toContain('2') // target lines count

    // 检查双栏 Diff 比对
    expect(wrapper.text()).toContain('原始代码 (Original)')
    expect(wrapper.text()).toContain('一阶变异代码 (Mutated)')
    expect(wrapper.text()).toContain('if price <= 0:')
    expect(wrapper.text()).toContain('if price > 0:')
  })

  it('allows switching mutant and sample code', async () => {
    const wrapper = mount(CodeMutationOperatorGeneratorModal, {
      props: {
        open: true,
      },
      global: {
        stubs: {
          'a-modal': { template: '<div class="ant-modal"><slot /></div>' },
          'a-tag': { template: '<span class="ant-tag"><slot /></span>' },
          'a-button': { template: '<button><slot /></button>' },
          'a-spin': { template: '<div><slot /></div>' },
          'a-textarea': { template: '<textarea />' },
          'a-input': { template: '<input />' },
          'a-input-number': { template: '<input type="number" />' },
          'a-space': { template: '<div><slot /></div>' },
          'a-empty': { template: '<div class="ant-empty" />' },
        },
      },
    })

    await flushPromises()

    const vm = wrapper.vm as any
    // 测试切换示例代码
    vm.loadSampleCode('auth')
    expect(vm.sourceCode).toContain('check_user_access')
    expect(vm.filePath).toBe('auth_guard.py')

    // 测试切换至第二个变异体 (LCR)
    vm.selectedMutant = mockReport.mutants[1]
    await wrapper.vm.$nextTick()
    expect(wrapper.text()).toContain('if is_vip and coupon_count > 0:')
    expect(wrapper.text()).toContain('if is_vip or coupon_count > 0:')
  })
})
