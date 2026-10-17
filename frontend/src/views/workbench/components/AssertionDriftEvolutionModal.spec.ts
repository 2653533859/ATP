import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import AssertionDriftEvolutionModal from './AssertionDriftEvolutionModal.vue'
import { selfHealingCoreApi } from '@/api/testSelfHealing'

vi.mock('@/api/testSelfHealing', () => ({
  selfHealingCoreApi: {
    dryRunAssertion: vi.fn().mockResolvedValue({
      message: 'ok',
      result: {
        status: 'PASS',
        elapsed_ms: 1.5,
        output_summary: '断言验证通过 (PASS)',
        error_message: null,
      },
    }),
    rollbackAssertion: vi.fn().mockResolvedValue({
      message: 'ok',
      snapshot: { status: 'ROLLBACKED' },
    }),
  },
}))

const stubs = {
  'a-modal': { template: '<div class="ant-modal-stub"><slot /><slot name="footer" /></div>' },
  'a-button': { template: '<button><slot /></button>' },
  'a-tag': { template: '<span class="ant-tag-stub"><slot /></span>' },
  'a-space': { template: '<div class="ant-space-stub"><slot /></div>' },
  'a-tabs': { template: '<div class="ant-tabs-stub"><slot /></div>' },
  'a-tab-pane': { template: '<div class="ant-tab-pane-stub"><slot /></div>' },
  'a-table': { template: '<div class="ant-table-stub"><slot /></div>' },
  'a-textarea': {
    props: ['value'],
    template: '<textarea :value="value" @input="$emit(\'update:value\', $event.target.value)" />',
  },
}

describe('AssertionDriftEvolutionModal.vue', () => {
  const sampleEvolution = {
    evolution_id: 'evo_pay_test_01',
    original_code: 'assert res["pay_amount"] == 199.5',
    evolved_code: 'assert res["data"]["payAmount"] == 199.5',
    unified_diff: '--- original_assertion.py\n+++ evolved_assertion.py\n-assert res["pay_amount"] == 199.5\n+assert res["data"]["payAmount"] == 199.5',
    applied_drift_ids: ['d_pay'],
    status: 'EVOLVED',
    evolution_notes: ['字段包裹至 data 并重命名为驼峰 payAmount'],
  }

  const sampleConfidence = {
    score: 94.0,
    risk_level: 'LOW',
    reasons: ['底层 Schema 漂移高置信对齐 (0.98)'],
    is_safe_to_auto_apply: true,
  }

  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders modal with score, risk level, and code diff', async () => {
    const wrapper = mount(AssertionDriftEvolutionModal, {
      props: {
        open: true,
        evolutionData: sampleEvolution,
        confidenceData: sampleConfidence,
        snapshotId: 'snap_001',
      },
      global: { stubs },
    })
    await flushPromises()

    expect(wrapper.text()).toContain('94.0')
    expect(wrapper.text()).toContain('风险评级: LOW')
    expect(wrapper.text()).toContain('assert res["pay_amount"] == 199.5')
    expect(wrapper.text()).toContain('assert res["data"]["payAmount"] == 199.5')
    expect(wrapper.text()).toContain('Unified Code Diff')
  })

  it('triggers sandbox dry-run execution', async () => {
    const wrapper = mount(AssertionDriftEvolutionModal, {
      props: {
        open: true,
        evolutionData: sampleEvolution,
        confidenceData: sampleConfidence,
      },
      global: { stubs },
    })
    await flushPromises()

    const dryRunBtn = wrapper.findAll('button').find((b) => b.text().includes('执行隔离沙箱试跑'))
    expect(dryRunBtn).toBeDefined()
    await dryRunBtn!.trigger('click')
    await flushPromises()

    expect(selfHealingCoreApi.dryRunAssertion).toHaveBeenCalled()
    expect(wrapper.text()).toContain('试跑验证通过 (PASS)')
  })

  it('handles apply evolution click', async () => {
    const wrapper = mount(AssertionDriftEvolutionModal, {
      props: {
        open: true,
        evolutionData: sampleEvolution,
        confidenceData: sampleConfidence,
      },
      global: { stubs },
    })
    await flushPromises()

    const applyBtn = wrapper.findAll('button').find((b) => b.text().includes('确认采纳演进'))
    expect(applyBtn).toBeDefined()
    await applyBtn!.trigger('click')
    await flushPromises()

    expect(wrapper.emitted('applied')).toEqual([['evo_pay_test_01']])
  })

  it('handles rollback snapshot click', async () => {
    const wrapper = mount(AssertionDriftEvolutionModal, {
      props: {
        open: true,
        evolutionData: sampleEvolution,
        confidenceData: sampleConfidence,
        snapshotId: 'snap_001',
      },
      global: { stubs },
    })
    await flushPromises()

    const rollbackBtn = wrapper.findAll('button').find((b) => b.text().includes('一键回滚'))
    expect(rollbackBtn).toBeDefined()
    await rollbackBtn!.trigger('click')
    await flushPromises()

    expect(selfHealingCoreApi.rollbackAssertion).toHaveBeenCalledWith('snap_001')
    expect(wrapper.emitted('rolledBack')).toEqual([['snap_001']])
  })
})
