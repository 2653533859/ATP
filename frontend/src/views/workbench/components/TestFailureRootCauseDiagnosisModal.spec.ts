import { mount, flushPromises } from '@vue/test-utils'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import TestFailureRootCauseDiagnosisModal from './TestFailureRootCauseDiagnosisModal.vue'
import { rootCauseDiagnosisApi } from '@/api/rootCauseDiagnosis'

const mockDatabaseReport = {
  diagnosis_id: 'diag_test_101',
  case_id: 'case_order_101',
  case_name: '提交订单并发支付用例',
  category: 'DATABASE_EXECUTION_FAILURE',
  confidence_score: 0.95,
  primary_root_cause_summary: '数据库层事务冲突或死锁/锁等待超时，导致微服务业务写入被强制中止回滚。',
  culprit_service: 'order-service',
  culprit_location: 'order_service.py:155 in checkout()',
  causal_chain: [
    '[1] 数据库产生并发行锁竞争/死锁异常 (order-service)',
    '[2] 数据访问层 (DAO/ORM) 抛出异常并向上扩散',
    '[3] 顶层接口捕获未决，返回 500 内部错误',
    '[4] 自动化测试断言或用例步骤失败',
  ],
  evidence_snippets: [
    {
      evidence_type: 'CONSOLE_LOG',
      title: '用例执行控制台日志与堆栈',
      content: 'Deadlock found when trying to get lock',
      is_key_evidence: false,
    },
    {
      evidence_type: 'HTTP_RESPONSE',
      title: 'HTTP 响应状态与报文 (Status: 500)',
      content: '{"code": 500}',
      is_key_evidence: true,
    },
  ],
  suggested_action: '检查相关 SQL 事务范围，优化索引避免间隙锁，为高并发写操作配置重试退避机制。',
  diagnosed_at: '2026-10-16T12:00:00Z',
}

const mockTimeoutReport = {
  diagnosis_id: 'diag_test_102',
  case_id: 'case_credit_202',
  case_name: '外部征信风控接口调用',
  category: 'NETWORK_GATEWAY_TIMEOUT',
  confidence_score: 0.92,
  primary_root_cause_summary: '下游微服务处理超时，网关触发超时熔断截断响应 (Status: 504)。',
  culprit_service: 'credit-service',
  culprit_location: 'gateway:504',
  causal_chain: ['[1] 下游微服务执行超时', '[2] 网关向调用方返回 HTTP 504'],
  evidence_snippets: [],
  suggested_action: '调高网关超时阈值',
  diagnosed_at: '2026-10-16T12:05:00Z',
}

vi.mock('@/api/rootCauseDiagnosis', () => ({
  rootCauseDiagnosisApi: {
    analyze: vi.fn(),
    batchAnalyze: vi.fn(),
    listReports: vi.fn(),
    getReport: vi.fn(),
    clearReports: vi.fn(),
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
  AimOutlined: { template: '<span>Aim</span>' },
  ThunderboltOutlined: { template: '<span>Thunderbolt</span>' },
}))

describe('TestFailureRootCauseDiagnosisModal.vue', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(rootCauseDiagnosisApi.analyze).mockResolvedValue({
      message: '测试失败根因推导完成',
      report: mockDatabaseReport as any,
    })
  })

  it('renders header, verdict banner, causal chain, and evidence snippets', async () => {
    const wrapper = mount(TestFailureRootCauseDiagnosisModal, {
      props: {
        open: true,
      },
      global: {
        stubs: {
          'a-drawer': { template: '<div class="ant-drawer"><slot /></div>' },
          'a-button': { template: '<button><slot /></button>' },
          'a-space': { template: '<div><slot /></div>' },
          'a-input': { template: '<input />' },
          'a-tag': { template: '<span class="ant-tag"><slot /></span>' },
        },
      },
    })

    await flushPromises()

    // 检查调用与标题
    expect(rootCauseDiagnosisApi.analyze).toHaveBeenCalled()
    expect(wrapper.text()).toContain('测试失败多模态证据融合与首发根因推导引擎')

    // 检查裁决横幅
    expect(wrapper.text()).toContain('DATABASE_EXECUTION_FAILURE')
    expect(wrapper.text()).toContain('95%')
    expect(wrapper.text()).toContain('order-service')
    expect(wrapper.text()).toContain('order_service.py:155 in checkout()')

    // 检查因果链条
    expect(wrapper.text()).toContain('因果失效传播链条 (Causal Failure Chain)')
    expect(wrapper.text()).toContain('数据库产生并发行锁竞争/死锁异常')

    // 检查证据卡片
    expect(wrapper.text()).toContain('多模态诊断证据汇编')
    expect(wrapper.text()).toContain('Deadlock found when trying to get lock')

    // 检查行动建议
    expect(wrapper.text()).toContain('优化索引避免间隙锁')
  })

  it('switches preset to gateway_timeout and updates report', async () => {
    vi.mocked(rootCauseDiagnosisApi.analyze).mockResolvedValueOnce({
      message: '测试失败根因推导完成',
      report: mockDatabaseReport as any,
    }).mockResolvedValueOnce({
      message: '测试失败根因推导完成',
      report: mockTimeoutReport as any,
    })

    const wrapper = mount(TestFailureRootCauseDiagnosisModal, {
      props: {
        open: true,
      },
      global: {
        stubs: {
          'a-drawer': { template: '<div class="ant-drawer"><slot /></div>' },
          'a-button': { template: '<button><slot /></button>' },
          'a-space': { template: '<div><slot /></div>' },
          'a-input': { template: '<input />' },
          'a-tag': { template: '<span class="ant-tag"><slot /></span>' },
        },
      },
    })

    await flushPromises()

    const vm = wrapper.vm as any
    await vm.applyPreset('gateway_timeout')
    await flushPromises()

    expect(rootCauseDiagnosisApi.analyze).toHaveBeenCalledTimes(2)
    expect(wrapper.text()).toContain('NETWORK_GATEWAY_TIMEOUT')
    expect(wrapper.text()).toContain('92%')
  })
})
