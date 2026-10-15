import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import AuditTamperEvidentChainView from './AuditTamperEvidentChainView.vue'

const mockReport = {
  report_id: 'cert_audit_test_9901',
  organization: 'ATP Enterprise QA & Cyber Security Team',
  generated_at: '2026-10-16T10:00:00Z',
  compliance_standard: 'ISO/IEC 27001 & SOC 2 Type II Tamper-Evident Audit Standard',
  integrity_status: 'VERIFIED_UNALTERED' as const,
  total_records: 4,
  chain_head_hash: 'c4b9e28f731a55019284beefcafe992817462819034827164928471928374829',
  digital_seal_signature: '7a98cf4210984729184729184729184729184729184729184729184729184729',
  integrity_diagnostic: {
    is_valid: true,
    tampered: false,
    total_blocks_checked: 4,
    chain_head_hash: 'c4b9e28f731a55019284beefcafe992817462819034827164928471928374829',
    tampered_at_index: null,
    error_description: '哈希链连续性校验 100% 通过，未检测到任何篡改或漏删记录。',
  },
  blocks: [
    {
      index: 1,
      log_id: 1,
      timestamp: '2026-10-16T10:00:00Z',
      previous_hash: '0000000000000000000000000000000000000000000000000000000000000000',
      record_hash: '1111111111111111111111111111111111111111111111111111111111111111',
      chain_hash: '2222222222222222222222222222222222222222222222222222222222222222',
      payload_summary: {
        action: 'user_login',
        resource_type: 'user',
        resource_id: 1,
        username: 'admin',
      },
    },
    {
      index: 2,
      log_id: 2,
      timestamp: '2026-10-16T10:05:00Z',
      previous_hash: '2222222222222222222222222222222222222222222222222222222222222222',
      record_hash: '3333333333333333333333333333333333333333333333333333333333333333',
      chain_hash: '4444444444444444444444444444444444444444444444444444444444444444',
      payload_summary: {
        action: 'case_create',
        resource_type: 'case',
        resource_id: 101,
        username: 'engineer_wong',
      },
    },
  ],
}

const mockVerifyResponse = {
  is_valid: true,
  tampered: false,
  total_blocks_checked: 4,
  chain_head_hash: 'c4b9e28f731a55019284beefcafe992817462819034827164928471928374829',
  tampered_at_index: null,
  error_description: '哈希链连续性校验 100% 通过，未检测到任何篡改或漏删记录。',
}

const mockGenerateReport = vi.fn().mockResolvedValue(mockReport)
const mockVerifyChain = vi.fn().mockResolvedValue(mockVerifyResponse)

vi.mock('@/api/auditChain', () => ({
  auditChainApi: {
    generateReport: (data: unknown) => mockGenerateReport(data),
    verifyChain: (params: unknown) => mockVerifyChain(params),
  },
}))

vi.mock('vue-router', () => ({
  useRouter: () => ({ push: vi.fn() }),
}))

const globalStubs = {
  'a-card': { template: '<div class="ant-card"><h4>{{ $attrs.title }}</h4><slot /><slot name="extra" /></div>' },
  'a-button': { template: '<button class="ant-btn"><slot /></button>' },
  'a-tag': { template: '<span class="ant-tag"><slot /></span>' },
  'a-space': { template: '<div><slot /></div>' },
  'a-alert': { template: '<div class="ant-alert"><h5>{{ $attrs.message }}</h5><p>{{ $attrs.description }}</p></div>' },
  'a-modal': { template: '<div class="ant-modal"><h3>{{ $attrs.title }}</h3><slot /></div>' },
  'a-descriptions': { template: '<div><slot /></div>' },
  'a-descriptions-item': { template: '<div><slot /></div>' },
}

describe('AuditTamperEvidentChainView.vue', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('generates report on mount and renders blockchain metrics and blocks', async () => {
    const wrapper = mount(AuditTamperEvidentChainView, {
      global: { stubs: globalStubs },
    })
    await flushPromises()

    expect(mockGenerateReport).toHaveBeenCalled()
    expect(wrapper.text()).toContain('类区块链 SHA-256 审计日志防篡改哈希链与合规证明中心')
    expect(wrapper.text()).toContain('0000000000000000...')
    expect(wrapper.text()).toContain('区块 #1')
    expect(wrapper.text()).toContain('区块 #2')
    expect(wrapper.text()).toContain('user_login')
    expect(wrapper.text()).toContain('VERIFIED UNALTERED')
  })

  it('runs online chain verification upon clicking verify button', async () => {
    const wrapper = mount(AuditTamperEvidentChainView, {
      global: { stubs: globalStubs },
    })
    await flushPromises()

    const verifyBtn = wrapper.findAll('button').find((b) => b.text().includes('自检哈希链完整性'))
    expect(verifyBtn).toBeDefined()
    await verifyBtn!.trigger('click')
    await flushPromises()

    expect(mockVerifyChain).toHaveBeenCalledWith({ limit: 100 })
    expect(wrapper.text()).toContain('密码学完整性 100% 验证通过')
  })

  it('simulates tamper attack and triggers TAMPER DETECTED alert', async () => {
    const wrapper = mount(AuditTamperEvidentChainView, {
      global: { stubs: globalStubs },
    })
    await flushPromises()

    const tamperBtn = wrapper.findAll('button').find((b) => b.text().includes('模拟篡改攻击检测'))
    expect(tamperBtn).toBeDefined()
    await tamperBtn!.trigger('click')
    await flushPromises()

    expect(wrapper.text()).toContain('TAMPER DETECTED 严重告警')
    expect(wrapper.text()).toContain('Payload Hash Mismatch')
    expect(wrapper.text()).toContain('块 #2')
  })
})
