import { mount, flushPromises } from '@vue/test-utils'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import ComprehensiveAuditReportView from './ComprehensiveAuditReportView.vue'
import { comprehensiveAuditReportApi } from '@/api/cloudNativeCluster'

const mockReport = {
  report_id: 'audit_rep_v430_1001',
  target_version: 'v4.3.0',
  project_name: 'ATP 自动化测试平台',
  generated_by: 'QualityGatekeeperBot',
  overall_verdict: 'GO',
  composite_health_score: 96.0,
  health_grade: 'A+',
  execution_summary: {
    total_cases: 250,
    passed_cases: 250,
    failed_cases: 0,
    pass_rate_pct: 100.0,
    duration_seconds: 42.5,
  },
  config_and_schema_drift: {
    config_drifts_count: 0,
    schema_drifts_count: 0,
    schema_compatibility_rate_pct: 100.0,
  },
  iac_compliance_summary: {
    iac_violations_count: 0,
    critical_violations_count: 0,
    compliance_score_pct: 100.0,
    iac_verdict: 'PASS',
  },
  fuzzing_vulnerability_summary: {
    fuzzing_mutations_count: 50,
    unhandled_crashes_count: 0,
    robustness_score_pct: 98.0,
  },
  gatekeeper_details: {
    verdict: 'GO',
    blocking_reasons: [],
    is_waived: false,
  },
  sha256_audit_fingerprint: 'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855',
  created_at: '2026-10-17T12:00:00Z',
}

vi.mock('@/api/cloudNativeCluster', () => ({
  comprehensiveAuditReportApi: {
    generate: vi.fn(),
    verify: vi.fn(),
    getMarkdown: vi.fn(),
    listReports: vi.fn(),
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
  CheckCircleOutlined: { template: '<span>CheckCircle</span>' },
  DownloadOutlined: { template: '<span>Download</span>' },
  ReloadOutlined: { template: '<span>Reload</span>' },
  FileProtectOutlined: { template: '<span>FileProtect</span>' },
  KeyOutlined: { template: '<span>Key</span>' },
  CopyOutlined: { template: '<span>Copy</span>' },
}))

describe('ComprehensiveAuditReportView.vue', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(comprehensiveAuditReportApi.listReports).mockResolvedValue({
      total: 1,
      reports: [mockReport as any],
    })
    vi.mocked(comprehensiveAuditReportApi.generate).mockResolvedValue({
      message: '质量合规全景审计报告生成完成',
      report: mockReport as any,
    })
    vi.mocked(comprehensiveAuditReportApi.verify).mockResolvedValue({
      valid: true,
      message: '报告签名验证通过',
    })
    vi.mocked(comprehensiveAuditReportApi.getMarkdown).mockResolvedValue('# Audit Report Markdown')
  })

  it('renders header, SHA-256 fingerprint, 5 evidence dimension cards, and verifies integrity', async () => {
    const wrapper = mount(ComprehensiveAuditReportView, {
      global: {
        stubs: {
          'a-button': { template: '<button><slot /></button>' },
          'a-space': { template: '<div><slot /></div>' },
          'a-row': { template: '<div><slot /></div>' },
          'a-col': { template: '<div><slot /></div>' },
          'a-tag': { template: '<span class="ant-tag"><slot /></span>' },
          'a-table': { template: '<div class="ant-table-stub" />' },
        },
      },
    })

    await flushPromises()

    expect(comprehensiveAuditReportApi.listReports).toHaveBeenCalled()

    // 检查标题与 SHA-256 指纹
    expect(wrapper.text()).toContain('端到端测试执行与质量合规全景审计报告大盘')
    expect(wrapper.text()).toContain('e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855')
    expect(wrapper.text()).toContain('1. 测试执行自动化总览')
    expect(wrapper.text()).toContain('2. 综合质量健康度')
    expect(wrapper.text()).toContain('3. 配置与数据结构漂移')
    expect(wrapper.text()).toContain('4. 云原生 IaC 安全合规')
    expect(wrapper.text()).toContain('5. 模糊变异与健壮防御')
    expect(wrapper.text()).toContain('GO (准许上线)')

    // 测试在线验签
    const vm = wrapper.vm as any
    await vm.handleVerifyIntegrity()
    await flushPromises()

    expect(comprehensiveAuditReportApi.verify).toHaveBeenCalledWith('audit_rep_v430_1001')
    expect(vm.verifyStatusText).toContain('验签有效')
  })
})
