import { mount, flushPromises } from '@vue/test-utils'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import PrQualityGatekeeperDashboardCard from './PrQualityGatekeeperDashboardCard.vue'
import { ciImpactApi } from '@/api/ciImpact'

const mockPrReport = {
  gate_id: 'gate_test_001',
  pr_id: '#1024',
  commit_sha: 'a1b2c3d4e5f',
  author: 'dev-alice',
  target_branch: 'main',
  verdict: 'MERGE_APPROVED',
  is_mergeable: true,
  overall_compliance_score: 100.0,
  blocking_reasons: [],
  warning_reasons: [],
  evaluated_rules: [
    {
      rule_id: 'RULE_UNIT_TEST_PASS_RATE',
      rule_name: '单元测试全量通过硬门禁',
      passed: true,
      severity: 'blocking',
      measured_value: '100.0%',
      threshold_value: '>= 100.0%',
      message: '单元测试通过率 100.0% 达到硬性准入标准 (0 失败用例)',
    },
    {
      rule_id: 'RULE_MUTATION_SCORE',
      rule_name: '代码变异测试充分性门禁',
      passed: true,
      severity: 'blocking',
      measured_value: '85.0%',
      threshold_value: '>= 70.0%',
      message: '代码变异得分 85.0% 达到断言充分性门禁阈值',
    },
  ],
  remediation_steps: [],
  evaluated_at: '2026-10-16T14:00:00Z',
}

vi.mock('@/api/ciImpact', () => ({
  ciImpactApi: {
    listPrGateReports: vi.fn(),
    evaluatePrGate: vi.fn(),
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
  SafetyCertificateOutlined: { template: '<span>Safety</span>' },
  ReloadOutlined: { template: '<span>Reload</span>' },
  SlidersOutlined: { template: '<span>Sliders</span>' },
  CheckCircleOutlined: { template: '<span>Check</span>' },
  CloseCircleOutlined: { template: '<span>Close</span>' },
  ExclamationCircleOutlined: { template: '<span>Exclamation</span>' },
  ToolOutlined: { template: '<span>Tool</span>' },
}))

describe('PrQualityGatekeeperDashboardCard.vue', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(ciImpactApi.listPrGateReports).mockResolvedValue({
      total: 1,
      reports: [mockPrReport as any],
    })
  })

  it('renders card title, verdict banner with MERGE_APPROVED, rules table, and compliance score', async () => {
    const wrapper = mount(PrQualityGatekeeperDashboardCard, {
      global: {
        stubs: {
          'a-tag': { template: '<span class="ant-tag"><slot /></span>' },
          'a-button': { template: '<button><slot /></button>' },
          'a-space': { template: '<div><slot /></div>' },
          'a-spin': { template: '<div><slot /></div>' },
          'a-modal': { template: '<div><slot /></div>' },
          'a-form': { template: '<form><slot /></form>' },
          'a-form-item': { template: '<div><slot /></div>' },
          'a-input': { template: '<input />' },
          'a-input-number': { template: '<input type="number" />' },
          'a-select': { template: '<select><slot /></select>' },
          'a-select-option': { template: '<option><slot /></option>' },
          'a-switch': { template: '<input type="checkbox" />' },
          'a-table': {
            props: ['dataSource'],
            template: `
              <div class="ant-table-stub">
                <div v-for="item in dataSource" :key="item.rule_id" class="row">
                  <span class="rule-title">{{ item.rule_name }}</span>
                  <span class="rule-msg">{{ item.message }}</span>
                </div>
              </div>
            `,
          },
        },
      },
    })

    await flushPromises()

    // 验证标题与调用
    expect(wrapper.text()).toContain('CI/CD PR 全要素质量门禁合并准入仲裁卡片')
    expect(ciImpactApi.listPrGateReports).toHaveBeenCalled()

    // 验证裁决横幅
    expect(wrapper.text()).toContain('MERGE_APPROVED (准入通过)')
    expect(wrapper.text()).toContain('允许合并入目标分支')
    expect(wrapper.text()).toContain('100%') // compliance score
    expect(wrapper.text()).toContain('#1024')
    expect(wrapper.text()).toContain('dev-alice')

    // 验证规则列表与整改说明
    expect(wrapper.text()).toContain('单元测试全量通过硬门禁')
    expect(wrapper.text()).toContain('代码变异测试充分性门禁')
    expect(wrapper.text()).toContain('无待整改项，当前 PR 满足所有合并红线')
  })

  it('supports switching presets to blocked and conditional', async () => {
    const wrapper = mount(PrQualityGatekeeperDashboardCard, {
      global: {
        stubs: {
          'a-tag': { template: '<span class="ant-tag"><slot /></span>' },
          'a-button': { template: '<button><slot /></button>' },
          'a-space': { template: '<div><slot /></div>' },
          'a-spin': { template: '<div><slot /></div>' },
          'a-modal': { template: '<div><slot /></div>' },
          'a-form': { template: '<form><slot /></form>' },
          'a-form-item': { template: '<div><slot /></div>' },
          'a-input': { template: '<input />' },
          'a-input-number': { template: '<input type="number" />' },
          'a-select': { template: '<select><slot /></select>' },
          'a-select-option': { template: '<option><slot /></option>' },
          'a-switch': { template: '<input type="checkbox" />' },
          'a-table': { template: '<div class="ant-table-stub" />' },
        },
      },
    })

    await flushPromises()

    const vm = wrapper.vm as any
    vm.applyPreset('blocked')
    await wrapper.vm.$nextTick()

    expect(wrapper.text()).toContain('MERGE_BLOCKED (阻断合流)')
    expect(wrapper.text()).toContain('阻断合流 / 禁止 Merge')
    expect(wrapper.text()).toContain('50%')
    expect(wrapper.text()).toContain('查看代码变异测试热力报告')
  })
})
