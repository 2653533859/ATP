import { mount, flushPromises } from '@vue/test-utils'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import ReleaseGateVerdictWaiverModal from './ReleaseGateVerdictWaiverModal.vue'
import { releaseGateVerdictApi } from '@/api/cloudNativeCluster'

const mockNoGoRecord = {
  release_id: 'rel_v430_p0_1001',
  target_version: 'v4.3.0-hotfix-p0',
  verdict: 'NO_GO' as const,
  quality_score: 58.0,
  blocking_reasons: ['存在 1 个未修复的 P0 核心阻塞级缺陷', '检测到 1 个 CRITICAL 级安全合规漏洞'],
  warning_reasons: ['存在 1 个 P1 级缺陷待跟进'],
  is_waived: false,
  waiver_info: null,
  created_at: '2026-10-17T12:00:00Z',
}

const mockWaivedRecord = {
  release_id: 'rel_v430_p0_1001',
  target_version: 'v4.3.0-hotfix-p0',
  verdict: 'WAIVED_GO' as const,
  quality_score: 58.0,
  blocking_reasons: ['存在 1 个未修复的 P0 核心阻塞级缺陷'],
  warning_reasons: [],
  is_waived: true,
  waiver_info: {
    approver: 'chief_architect_zhang',
    waiver_reason: '线上核心紧急修复',
    rollback_plan: '5分钟内一键切旧流量',
    waived_at: '2026-10-17T12:05:00Z',
  },
  created_at: '2026-10-17T12:00:00Z',
}

vi.mock('@/api/cloudNativeCluster', () => ({
  releaseGateVerdictApi: {
    evaluate: vi.fn(),
    waive: vi.fn(),
    revokeWaiver: vi.fn(),
    listRecords: vi.fn(),
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
  ThunderboltOutlined: { template: '<span>Thunderbolt</span>' },
  ExclamationCircleOutlined: { template: '<span>Exclamation</span>' },
  AuditOutlined: { template: '<span>Audit</span>' },
}))

describe('ReleaseGateVerdictWaiverModal.vue', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(releaseGateVerdictApi.evaluate).mockResolvedValue({
      message: '门禁裁决完成',
      record: mockNoGoRecord as any,
    })
    vi.mocked(releaseGateVerdictApi.waive).mockResolvedValue({
      success: true,
      message: '特批豁免成功',
      record: mockWaivedRecord as any,
    })
    vi.mocked(releaseGateVerdictApi.revokeWaiver).mockResolvedValue({
      success: true,
      message: '特批豁免已撤销',
      record: mockNoGoRecord as any,
    })
  })

  it('renders header, NO_GO blocking reasons, and performs waiver grant & revoke', async () => {
    const wrapper = mount(ReleaseGateVerdictWaiverModal, {
      props: {
        open: true,
      },
      global: {
        stubs: {
          'a-modal': { template: '<div class="ant-modal"><slot /><slot name="footer" /></div>' },
          'a-button': { template: '<button><slot /></button>' },
          'a-radio-group': { template: '<div><slot /></div>' },
          'a-radio-button': { template: '<button><slot /></button>' },
          'a-input': { template: '<input />' },
        },
      },
    })

    await flushPromises()

    expect(releaseGateVerdictApi.evaluate).toHaveBeenCalled()

    // 检查标题与 NO_GO 阻断
    expect(wrapper.text()).toContain('发版准入阻断状态机与架构师特批风险豁免网关')
    expect(wrapper.text()).toContain('NO_GO')
    expect(wrapper.text()).toContain('存在 1 个未修复的 P0 核心阻塞级缺陷')

    // 签署特批豁免
    const vm = wrapper.vm as any
    await vm.handleGrantWaiver()
    await flushPromises()

    expect(releaseGateVerdictApi.waive).toHaveBeenCalled()
    expect(wrapper.text()).toContain('WAIVED_GO')
    expect(wrapper.text()).toContain('chief_architect_zhang')

    // 撤销豁免
    await vm.handleRevokeWaiver()
    await flushPromises()

    expect(releaseGateVerdictApi.revokeWaiver).toHaveBeenCalled()
    expect(wrapper.text()).toContain('NO_GO')
  })
})
