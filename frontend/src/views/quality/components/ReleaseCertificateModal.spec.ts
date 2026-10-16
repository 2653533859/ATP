import { mount, flushPromises } from '@vue/test-utils'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import ReleaseCertificateModal from './ReleaseCertificateModal.vue'
import { qualityGovernanceApi } from '@/api/qualityGovernance'

const mockCertResponse = {
  certificate_id: 'CERT-RELEASE-20261016-A1B2C3D4',
  project_id: 1,
  release_version: 'v3.3.0',
  commit_sha: '15c38686',
  target_environment: 'production',
  verdict: 'APPROVED' as const,
  quality_score: 91.5,
  gate_profile_id: 'gate_prod_release',
  blocked_reasons: [],
  issued_at: '2026-10-16 12:00:00 UTC',
  certificate_hash: 'sha256_mock_hash_8f9a2b',
  digital_seal_signature: 'hmac_sha256_mock_signature_778899aabb',
}

const mockVerifyResponse = {
  is_authentic: true,
  message: '发版准入证书真实有效，未发生任何篡改',
  certificate_id: 'CERT-RELEASE-20261016-A1B2C3D4',
}

vi.mock('@/api/qualityGovernance', () => ({
  qualityGovernanceApi: {
    generateCertificate: vi.fn(),
    verifyCertificate: vi.fn(),
    getCertificate: vi.fn(),
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

describe('ReleaseCertificateModal.vue', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders modal header and certificate generation inputs', async () => {
    const wrapper = mount(ReleaseCertificateModal, {
      props: {
        open: true,
        projectId: 1,
      },
      global: {
        stubs: {
          'a-modal': { template: '<div><slot name="title" /><slot /></div>' },
          'a-card': { template: '<div class="ant-card"><slot /></div>' },
          'a-tag': { template: '<span class="ant-tag"><slot /></span>' },
          'a-space': { template: '<div><slot /></div>' },
          'a-form': { template: '<form><slot /></form>' },
          'a-form-item': { template: '<div><slot /></div>' },
          'a-input': { template: '<input />' },
          'a-select': { template: '<select><slot /></select>' },
          'a-select-option': { template: '<option><slot /></option>' },
          'a-button': { template: '<button><slot /></button>' },
        },
      },
    })

    await flushPromises()

    expect(wrapper.text()).toContain('自动化发版准入合格证书与防伪数字印章')
  })

  it('generates release certificate and displays certificate ticket with seal and badges', async () => {
    vi.mocked(qualityGovernanceApi.generateCertificate).mockResolvedValue(mockCertResponse)

    const wrapper = mount(ReleaseCertificateModal, {
      props: {
        open: true,
        projectId: 1,
      },
      global: {
        stubs: {
          'a-modal': { template: '<div><slot name="title" /><slot /></div>' },
          'a-card': { template: '<div class="ant-card"><slot /></div>' },
          'a-tag': { template: '<span class="ant-tag"><slot /></span>' },
          'a-space': { template: '<div><slot /></div>' },
          'a-form': { template: '<form><slot /></form>' },
          'a-form-item': { template: '<div><slot /></div>' },
          'a-input': { template: '<input />' },
          'a-select': { template: '<select><slot /></select>' },
          'a-select-option': { template: '<option><slot /></option>' },
          'a-button': { template: '<button><slot /></button>' },
          'a-alert': { template: '<div class="ant-alert">{{ message }} {{ description }}</div>', props: ['message', 'description'] },
        },
      },
    })

    await flushPromises()

    const genBtn = wrapper.findAll('button').find((b) => b.text().includes('签发准入证书'))
    expect(genBtn).toBeDefined()
    await genBtn!.trigger('click')
    await flushPromises()

    expect(qualityGovernanceApi.generateCertificate).toHaveBeenCalledWith({
      project_id: 1,
      release_version: 'v3.3.0',
      commit_sha: '15c38686',
      target_environment: 'production',
      gate_profile_id: 'gate_prod_release',
    })

    // 验证证书票据渲染
    expect(wrapper.text()).toContain('CERT-RELEASE-20261016-A1B2C3D4')
    expect(wrapper.text()).toContain('ISO 27001 AUDITED')
    expect(wrapper.text()).toContain('SOC 2 TYPE II COMPLIANT')
    expect(wrapper.text()).toContain('全生命周期软件发版准入合格证书')
    expect(wrapper.text()).toContain('准予发布')
    expect(wrapper.text()).toContain('hmac_sha256_mock_signature_778899aabb')
  })

  it('verifies certificate authenticity signature and displays verification success', async () => {
    vi.mocked(qualityGovernanceApi.generateCertificate).mockResolvedValue(mockCertResponse)
    vi.mocked(qualityGovernanceApi.verifyCertificate).mockResolvedValue(mockVerifyResponse)

    const wrapper = mount(ReleaseCertificateModal, {
      props: {
        open: true,
        projectId: 1,
      },
      global: {
        stubs: {
          'a-modal': { template: '<div><slot name="title" /><slot /></div>' },
          'a-card': { template: '<div class="ant-card"><slot /></div>' },
          'a-tag': { template: '<span class="ant-tag"><slot /></span>' },
          'a-space': { template: '<div><slot /></div>' },
          'a-form': { template: '<form><slot /></form>' },
          'a-form-item': { template: '<div><slot /></div>' },
          'a-input': { template: '<input />' },
          'a-select': { template: '<select><slot /></select>' },
          'a-select-option': { template: '<option><slot /></option>' },
          'a-button': { template: '<button><slot /></button>' },
          'a-alert': { template: '<div class="ant-alert">{{ message }} {{ description }}</div>', props: ['message', 'description'] },
        },
      },
    })

    await flushPromises()

    // 先签发证书
    const genBtn = wrapper.findAll('button').find((b) => b.text().includes('签发准入证书'))
    await genBtn!.trigger('click')
    await flushPromises()

    // 点击检验防伪签名
    const verifyBtn = wrapper.findAll('button').find((b) => b.text().includes('检验签名真伪与防篡改自检'))
    expect(verifyBtn).toBeDefined()
    await verifyBtn!.trigger('click')
    await flushPromises()

    expect(qualityGovernanceApi.verifyCertificate).toHaveBeenCalledWith({
      certificate_id: 'CERT-RELEASE-20261016-A1B2C3D4',
      release_version: 'v3.3.0',
      commit_sha: '15c38686',
      verdict: 'APPROVED',
      quality_score: 91.5,
      issued_at: '2026-10-16 12:00:00 UTC',
      digital_seal_signature: 'hmac_sha256_mock_signature_778899aabb',
    })

    expect(wrapper.text()).toContain('[数字印章验证通过]')
  })
})
