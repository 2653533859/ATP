import { mount, flushPromises } from '@vue/test-utils'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import MultiEnvConfigDriftDrawer from './MultiEnvConfigDriftDrawer.vue'
import { multiEnvConfigDriftApi } from '@/api/cloudNativeCluster'

const mockDriftReport = {
  report_id: 'drift_order_service_1001',
  service_name: 'order-service',
  base_env: 'production',
  target_env: 'testing',
  total_keys_checked: 5,
  identical_count: 2,
  drift_count: 3,
  highest_severity: 'CRITICAL',
  consistency_score_pct: 40.0,
  drifts: [
    {
      key: 'DATABASE_URL',
      base_value: 'postgresql://prod-db:5432/orders',
      target_value: 'postgresql://test-db:5432/orders',
      drift_type: 'VALUE_MISMATCH',
      severity: 'HIGH',
      risk_explanation: '数据库地址不一致',
      remediation_suggestion: '核对中间件网络隔离',
    },
    {
      key: 'JWT_SECRET_KEY',
      base_value: 'PROD_SEC_KEY',
      target_value: null,
      drift_type: 'MISSING_IN_TARGET',
      severity: 'CRITICAL',
      risk_explanation: '生产密钥在测试环境缺失',
      remediation_suggestion: '配置独立测试凭证',
    },
    {
      key: 'DEBUG_VERBOSE',
      base_value: null,
      target_value: true,
      drift_type: 'EXTRA_IN_TARGET',
      severity: 'LOW',
      risk_explanation: '测试环境存在额外调试参数',
      remediation_suggestion: '按需保留或清理',
    },
  ],
  created_at: '2026-10-17T12:00:00Z',
}

vi.mock('@/api/cloudNativeCluster', () => ({
  multiEnvConfigDriftApi: {
    compare: vi.fn(),
    registerSnapshot: vi.fn(),
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
}))

describe('MultiEnvConfigDriftDrawer.vue', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(multiEnvConfigDriftApi.compare).mockResolvedValue({
      message: '配置差分比对完成',
      report: mockDriftReport as any,
    })
  })

  it('renders header, CRITICAL alert, KPI cards, and diff table', async () => {
    const wrapper = mount(MultiEnvConfigDriftDrawer, {
      props: {
        open: true,
      },
      global: {
        stubs: {
          'a-drawer': { template: '<div class="ant-drawer"><slot /></div>' },
          'a-button': { template: '<button><slot /></button>' },
          'a-select': { template: '<select><slot /></select>' },
          'a-select-option': { template: '<option><slot /></option>' },
          'a-radio-group': { template: '<div><slot /></div>' },
          'a-radio-button': { template: '<button><slot /></button>' },
          'a-row': { template: '<div><slot /></div>' },
          'a-col': { template: '<div><slot /></div>' },
          'a-tag': { template: '<span class="ant-tag"><slot /></span>' },
          'a-table': { template: '<div class="ant-table-stub" />' },
          'a-alert': { template: '<div class="ant-alert"><slot /></div>' },
        },
      },
    })

    await flushPromises()

    expect(multiEnvConfigDriftApi.compare).toHaveBeenCalled()

    // 检查标题与 CRITICAL 警告
    expect(wrapper.text()).toContain('多环境微服务配置与环境变量深度差分比对引擎')
    expect(wrapper.text()).toContain('CRITICAL')
    expect(wrapper.text()).toContain('5 项')
    expect(wrapper.text()).toContain('40%')
    expect(wrapper.text()).toContain('3 项')

    // 切换预设
    const vm = wrapper.vm as any
    vm.selectedPreset = 'payment_service'
    await vm.handlePresetChange()
    await flushPromises()

    expect(multiEnvConfigDriftApi.compare).toHaveBeenCalledTimes(2)
  })
})
