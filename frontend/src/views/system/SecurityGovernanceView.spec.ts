import { flushPromises, mount } from '@vue/test-utils'
import { defineComponent, h } from 'vue'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import SecurityGovernanceView from './SecurityGovernanceView.vue'

const {
  projectList,
  createApiKey,
  getApiKeyAuditReport,
  revokeApiKey,
  createDrSnapshot,
  performDrDrill,
  maskPii,
  messageSuccess,
} = vi.hoisted(() => ({
  projectList: vi.fn(),
  createApiKey: vi.fn(),
  getApiKeyAuditReport: vi.fn(),
  revokeApiKey: vi.fn(),
  createDrSnapshot: vi.fn(),
  performDrDrill: vi.fn(),
  maskPii: vi.fn(),
  messageSuccess: vi.fn(),
}))

vi.mock('vue-i18n', () => ({ useI18n: () => ({ t: (key: string) => key }) }))
vi.mock('ant-design-vue', () => ({
  message: { error: vi.fn(), success: messageSuccess, warning: vi.fn(), info: vi.fn() },
}))
vi.mock('@/api', () => ({
  projectApi: { list: projectList },
  securityApi: {
    createApiKey,
    getApiKeyAuditReport,
    revokeApiKey,
    createDrSnapshot,
    performDrDrill,
    maskPii,
  },
}))

const passthrough = (name: string) =>
  defineComponent({ name, setup: (_props, { slots }) => () => h('div', slots.default?.()) })

const stubs = {
  AAlert: passthrough('AAlert'),
  AButton: passthrough('AButton'),
  ACard: passthrough('ACard'),
  ACol: passthrough('ACol'),
  ADescriptions: passthrough('ADescriptions'),
  ADescriptionsItem: passthrough('ADescriptionsItem'),
  AEmpty: passthrough('AEmpty'),
  AForm: passthrough('AForm'),
  AFormItem: passthrough('AFormItem'),
  AInput: passthrough('AInput'),
  AInputNumber: passthrough('AInputNumber'),
  AModal: passthrough('AModal'),
  APopconfirm: passthrough('APopconfirm'),
  ARow: passthrough('ARow'),
  ASelect: passthrough('ASelect'),
  ASpace: passthrough('ASpace'),
  ATable: passthrough('ATable'),
  ATabPane: passthrough('ATabPane'),
  ATabs: passthrough('ATabs'),
  ATag: passthrough('ATag'),
  ATextarea: passthrough('ATextarea'),
}

beforeEach(() => {
  vi.clearAllMocks()
  projectList.mockResolvedValue([{ id: 1, name: 'Core' }])
  getApiKeyAuditReport.mockResolvedValue([
    {
      key_id: 1,
      name: 'CI Key',
      key_prefix: 'atp_sec_12...',
      user_id: 1,
      project_id: 1,
      role: 'engineer',
      ip_allowlist: [],
      has_ip_restriction: false,
      is_active: true,
      is_expired: false,
      total_calls: 5,
    },
  ])
})

describe('SecurityGovernanceView', () => {
  it('creates and revokes API keys, runs disaster recovery checks, and masks PII', async () => {
    createApiKey.mockResolvedValue({ id: 2, name: 'Deploy Key', raw_key: 'atp_sec_raw_token', key_prefix: 'atp_sec_ra...' })
    revokeApiKey.mockResolvedValue(undefined)
    createDrSnapshot.mockResolvedValue({ snapshot_id: 'dr_manual_1', platform_version: 'v2.7.0', mode: 'server', database_type: 'postgresql', table_counts: { projects: 1 }, files: {} })
    performDrDrill.mockResolvedValue({ status: 'passed', drill_at: '2026-11-27T00:00:00Z', duration_ms: 4.5, integrity_passed: true, verified_files: ['database.sql'], checksum_failures: [], table_counts: { projects: 1 }, table_reconciliation: {} })
    maskPii.mockResolvedValue({ redacted: { phone: '138****0000' }, success: true })

    const wrapper = mount(SecurityGovernanceView, { global: { stubs } })
    await flushPromises()
    expect(getApiKeyAuditReport).toHaveBeenCalledWith(undefined)

    const vm = wrapper.vm as any
    vm.openCreateKey()
    vm.keyForm.name = 'Deploy Key'
    vm.keyForm.ip_allowlist = '10.0.0.1, 10.0.0.2'
    await vm.handleCreateKey()
    expect(createApiKey).toHaveBeenCalledWith(expect.objectContaining({
      name: 'Deploy Key',
      ip_allowlist: ['10.0.0.1', '10.0.0.2'],
    }))
    expect(vm.rawKeyModalOpen).toBe(true)
    expect(vm.createdRawKey).toBe('atp_sec_raw_token')

    await vm.handleRevokeKey(1)
    expect(revokeApiKey).toHaveBeenCalledWith(1)

    await vm.handleCreateSnapshot()
    expect(createDrSnapshot).toHaveBeenCalledWith('manual')
    expect(vm.snapshotResult.snapshot_id).toBe('dr_manual_1')

    await vm.handlePerformDrill()
    expect(performDrDrill).toHaveBeenCalledOnce()
    expect(vm.drillResult.status).toBe('passed')

    vm.piiPayload = '{"phone":"13812340000"}'
    vm.piiKeywords = 'secret'
    await vm.handleMaskPii()
    expect(maskPii).toHaveBeenCalledWith({ payload: { phone: '13812340000' }, custom_keywords: ['secret'] })
    expect(vm.piiRedactedText).toContain('138****0000')
    wrapper.unmount()
  })
})
