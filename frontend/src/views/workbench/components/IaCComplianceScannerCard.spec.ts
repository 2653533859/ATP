import { mount, flushPromises } from '@vue/test-utils'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import IaCComplianceScannerCard from './IaCComplianceScannerCard.vue'
import { iacComplianceScannerApi } from '@/api/cloudNativeCluster'

const mockBlockedReport = {
  report_id: 'iac_insecure_1001',
  target_name: 'insecure_workload',
  total_resources_scanned: 1,
  total_violations_count: 2,
  critical_count: 2,
  high_count: 0,
  medium_count: 0,
  low_count: 0,
  compliance_score_pct: 50.0,
  verdict: 'BLOCKED' as const,
  violations: [
    {
      rule_id: 'IAC-001',
      rule_name: '禁止特权容器运行',
      severity: 'CRITICAL',
      resource_kind: 'Deployment',
      resource_name: 'ci-runner-deployment/docker-builder',
      violation_message: '容器配置了 privileged: true',
      remediation_guidance: '移除 privileged: true',
    },
    {
      rule_id: 'IAC-002',
      rule_name: '禁止挂载敏感宿主机路径',
      severity: 'CRITICAL',
      resource_kind: 'Deployment',
      resource_name: 'ci-runner-deployment',
      violation_message: '卷挂载了敏感宿主机目录 (/var/run/docker.sock)',
      remediation_guidance: '改用 ConfigMap 或 Secret 卷',
    },
  ],
  created_at: '2026-10-17T12:00:00Z',
}

const mockPassReport = {
  report_id: 'iac_secure_1002',
  target_name: 'secure_workload',
  total_resources_scanned: 1,
  total_violations_count: 0,
  critical_count: 0,
  high_count: 0,
  medium_count: 0,
  low_count: 0,
  compliance_score_pct: 100.0,
  verdict: 'PASS' as const,
  violations: [],
  created_at: '2026-10-17T12:05:00Z',
}

vi.mock('@/api/cloudNativeCluster', () => ({
  iacComplianceScannerApi: {
    scan: vi.fn(),
    getRules: vi.fn(),
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
  SecurityScanOutlined: { template: '<span>Security</span>' },
  ThunderboltOutlined: { template: '<span>Thunderbolt</span>' },
}))

describe('IaCComplianceScannerCard.vue', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(iacComplianceScannerApi.scan).mockResolvedValue({
      message: '合规扫描完成',
      report: mockBlockedReport as any,
    })
  })

  it('renders header, BLOCKED verdict banner, KPI cards, and violations table', async () => {
    const wrapper = mount(IaCComplianceScannerCard, {
      props: {
        open: true,
      },
      global: {
        stubs: {
          'a-drawer': { template: '<div class="ant-drawer"><slot /></div>' },
          'a-button': { template: '<button><slot /></button>' },
          'a-radio-group': { template: '<div><slot /></div>' },
          'a-radio-button': { template: '<button><slot /></button>' },
          'a-row': { template: '<div><slot /></div>' },
          'a-col': { template: '<div><slot /></div>' },
          'a-tag': { template: '<span class="ant-tag"><slot /></span>' },
          'a-table': { template: '<div class="ant-table-stub" />' },
          'a-alert': { props: ['message', 'description'], template: '<div class="ant-alert"><span>{{ message }}</span><span>{{ description }}</span><slot /></div>' },
        },
      },
    })

    await flushPromises()

    expect(iacComplianceScannerApi.scan).toHaveBeenCalled()

    // 检查标题与 BLOCKED 警告
    expect(wrapper.text()).toContain('云原生 IaC 清单与 NetworkPolicy 准入安全巡检引擎')
    expect(wrapper.text()).toContain('发版准入阻断 (BLOCKED)')
    expect(wrapper.text()).toContain('50%')
    expect(wrapper.text()).toContain('2 处')

    // 切换到安全预设
    vi.mocked(iacComplianceScannerApi.scan).mockResolvedValueOnce({
      message: '合规扫描完成',
      report: mockPassReport as any,
    })

    const vm = wrapper.vm as any
    vm.selectedPreset = 'secure_workload'
    await vm.handlePresetChange()
    await flushPromises()

    expect(iacComplianceScannerApi.scan).toHaveBeenCalledTimes(2)
  })
})
