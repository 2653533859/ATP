import { mount, flushPromises } from '@vue/test-utils'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import QualityGateRuleConfigDrawer from './QualityGateRuleConfigDrawer.vue'
import { qualityGovernanceApi } from '@/api/qualityGovernance'

const mockEvalPassedResult = {
  profile_id: 'gate_prod_release',
  verdict: 'APPROVED' as const,
  passed: true,
  exit_code: 0,
  failed_blockers: [],
  failed_warnings: [],
  rule_results: [
    {
      metric_key: 'pass_rate_pct',
      operator: 'gte',
      threshold: 99.0,
      actual_value: 99.5,
      severity: 'blocker' as const,
      passed: true,
      reason: '指标 99.5 满足 gte 99.0',
    },
    {
      metric_key: 'p0_pass_rate_pct',
      operator: 'gte',
      threshold: 100.0,
      actual_value: 100.0,
      severity: 'blocker' as const,
      passed: true,
      reason: '指标 100.0 满足 gte 100.0',
    },
  ],
  evaluated_at: '2026-10-16T12:00:00Z',
}


vi.mock('@/api/qualityGovernance', () => ({
  qualityGovernanceApi: {
    listGateProfiles: vi.fn(),
    registerGateProfile: vi.fn(),
    evaluateQualityGate: vi.fn(),
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

describe('QualityGateRuleConfigDrawer.vue', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders drawer title, profile metadata, and default rule list', async () => {
    const wrapper = mount(QualityGateRuleConfigDrawer, {
      props: {
        open: true,
        defaultProfileId: 'gate_prod_release',
      },
      global: {
        stubs: {
          'a-drawer': { template: '<div><slot name="title" /><slot /></div>' },
          'a-card': { template: '<div class="ant-card">{{ title }}<slot name="title" /><slot name="extra" /><slot /></div>', props: ['title'] },
          'a-tag': { template: '<span class="ant-tag"><slot /></span>' },
          'a-space': { template: '<div><slot /></div>' },
          'a-form': { template: '<form><slot /></form>' },
          'a-form-item': { template: '<div><slot /></div>' },
          'a-input': { template: '<input />' },
          'a-input-number': { template: '<input />' },
          'a-select': { template: '<select><slot /></select>' },
          'a-select-option': { template: '<option><slot /></option>' },
          'a-switch': { template: '<input type="checkbox" />' },
          'a-textarea': { template: '<textarea />' },
          'a-button': { template: '<button><slot /></button>' },
          'a-table': {
            template: `
              <div class="ant-table">
                <div v-for="(item, idx) in dataSource" :key="item.metric_key || idx" class="row">
                  <slot name="bodyCell" :column="{ key: 'metric_key' }" :record="item" :index="idx" />
                  <slot name="bodyCell" :column="{ key: 'operator' }" :record="item" :index="idx" />
                  <slot name="bodyCell" :column="{ key: 'threshold' }" :record="item" :index="idx" />
                  <slot name="bodyCell" :column="{ key: 'severity' }" :record="item" :index="idx" />
                  <slot name="bodyCell" :column="{ key: 'description' }" :record="item" :index="idx" />
                </div>
              </div>
            `,
            props: ['dataSource'],
          },
        },
      },
    })

    await flushPromises()

    expect(wrapper.text()).toContain('CI/CD 智能流水线质量门禁策略配置与卡点决策中心')
    expect(wrapper.text()).toContain('质量门禁 Profile 策略配置')
    expect(wrapper.text()).toContain('卡点规则表达式配置清单 (Rule Matrix)')
  })

  it('loads PR check preset and updates profile metadata', async () => {
    const wrapper = mount(QualityGateRuleConfigDrawer, {
      props: {
        open: true,
      },
      global: {
        stubs: {
          'a-drawer': { template: '<div><slot name="title" /><slot /></div>' },
          'a-card': { template: '<div class="ant-card">{{ title }}<slot name="title" /><slot name="extra" /><slot /></div>', props: ['title'] },
          'a-tag': { template: '<span class="ant-tag"><slot /></span>' },
          'a-space': { template: '<div><slot /></div>' },
          'a-form': { template: '<form><slot /></form>' },
          'a-form-item': { template: '<div><slot /></div>' },
          'a-input': { template: '<input />' },
          'a-input-number': { template: '<input />' },
          'a-select': { template: '<select><slot /></select>' },
          'a-select-option': { template: '<option><slot /></option>' },
          'a-switch': { template: '<input type="checkbox" />' },
          'a-textarea': { template: '<textarea />' },
          'a-button': { template: '<button><slot /></button>' },
          'a-table': { template: '<div class="ant-table" />' },
        },
      },
    })

    await flushPromises()

    const prBtn = wrapper.findAll('button').find((b) => b.text().includes('载入 PR 冒烟准入预设'))
    expect(prBtn).toBeDefined()
    await prBtn!.trigger('click')
    await flushPromises()

    expect((wrapper.vm as any).profileId).toBe('gate_pr_check')
    expect((wrapper.vm as any).rules.length).toBe(2)
  })

  it('saves quality gate profile on button click', async () => {
    vi.mocked(qualityGovernanceApi.registerGateProfile).mockResolvedValue({
      message: '质量门禁策略注册成功',
      profile: {
        profile_id: 'gate_prod_release',
        name: '生产发布阻断性质量门禁规则',
        description: 'CI/CD 智能门禁',
        rules: [],
        block_on_failure: true,
      },
    })

    const wrapper = mount(QualityGateRuleConfigDrawer, {
      props: {
        open: true,
      },
      global: {
        stubs: {
          'a-drawer': { template: '<div><slot name="title" /><slot /></div>' },
          'a-card': { template: '<div class="ant-card">{{ title }}<slot name="title" /><slot name="extra" /><slot /></div>', props: ['title'] },
          'a-tag': { template: '<span class="ant-tag"><slot /></span>' },
          'a-space': { template: '<div><slot /></div>' },
          'a-form': { template: '<form><slot /></form>' },
          'a-form-item': { template: '<div><slot /></div>' },
          'a-input': { template: '<input />' },
          'a-input-number': { template: '<input />' },
          'a-select': { template: '<select><slot /></select>' },
          'a-select-option': { template: '<option><slot /></option>' },
          'a-switch': { template: '<input type="checkbox" />' },
          'a-textarea': { template: '<textarea />' },
          'a-button': { template: '<button><slot /></button>' },
          'a-table': { template: '<div class="ant-table" />' },
        },
      },
    })

    await flushPromises()

    const saveBtn = wrapper.findAll('button').find((b) => b.text().includes('保存门禁策略'))
    expect(saveBtn).toBeDefined()
    await saveBtn!.trigger('click')
    await flushPromises()

    expect(qualityGovernanceApi.registerGateProfile).toHaveBeenCalledWith({
      profile_id: 'gate_prod_release',
      name: '生产发布阻断性质量门禁规则',
      description: expect.any(String),
      rules: expect.any(Array),
      block_on_failure: true,
    })
  })

  it('triggers online gate evaluation and renders pass and blocked decision banners', async () => {
    vi.mocked(qualityGovernanceApi.evaluateQualityGate).mockResolvedValue(mockEvalPassedResult)

    const wrapper = mount(QualityGateRuleConfigDrawer, {
      props: {
        open: true,
      },
      global: {
        stubs: {
          'a-drawer': { template: '<div><slot name="title" /><slot /></div>' },
          'a-card': { template: '<div class="ant-card">{{ title }}<slot name="title" /><slot name="extra" /><slot /></div>', props: ['title'] },
          'a-tag': { template: '<span class="ant-tag"><slot /></span>' },
          'a-space': { template: '<div><slot /></div>' },
          'a-form': { template: '<form><slot /></form>' },
          'a-form-item': { template: '<div><slot /></div>' },
          'a-input': { template: '<input />' },
          'a-input-number': { template: '<input />' },
          'a-select': { template: '<select><slot /></select>' },
          'a-select-option': { template: '<option><slot /></option>' },
          'a-switch': { template: '<input type="checkbox" />' },
          'a-textarea': { template: '<textarea />' },
          'a-button': { template: '<button><slot /></button>' },
          'a-alert': { template: '<div class="ant-alert">{{ message }} {{ description }}</div>', props: ['message', 'description'] },
          'a-table': {
            template: `
              <div class="ant-table">
                <div v-for="item in dataSource" :key="item.metric_key" class="row">
                  <slot name="bodyCell" :column="{ key: 'metric_key' }" :record="item" />
                  <slot name="bodyCell" :column="{ key: 'passed' }" :record="item" />
                  <slot name="bodyCell" :column="{ key: 'severity' }" :record="item" />
                </div>
              </div>
            `,
            props: ['dataSource'],
          },
        },
      },
    })

    await flushPromises()

    const evalBtn = wrapper.findAll('button').find((b) => b.text().includes('执行卡点在线决策'))
    expect(evalBtn).toBeDefined()
    await evalBtn!.trigger('click')
    await flushPromises()

    expect(qualityGovernanceApi.evaluateQualityGate).toHaveBeenCalledWith('gate_prod_release', expect.any(Object))
    expect(wrapper.text()).toContain('[准予放行 PASSED]')
    expect(wrapper.text()).toContain('exit_code: 0')
  })
})
