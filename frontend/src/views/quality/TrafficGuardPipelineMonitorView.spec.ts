import { mount, flushPromises } from '@vue/test-utils'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import TrafficGuardPipelineMonitorView from './TrafficGuardPipelineMonitorView.vue'
import { trafficGuardPipelineApi } from '@/api/trafficGateway'

const mockPassReport = {
  pipeline_run_id: 'pl_run_101',
  pipeline_name: 'ATP-Traffic-Guard-Pipeline',
  endpoint: 'POST /api/v1/orders/checkout',
  exit_code: 0,
  overall_status: 'PASSED',
  stages: [
    {
      stage_index: 1,
      stage_name: '流量捕获与敏感数据清洗 (Capture & PII Masking)',
      status: 'PASSED',
      duration_ms: 12.5,
      summary: '成功捕获 2 条流量样本，清洗 1 处手机号脱敏。',
      metrics: { captured_samples: 2, masked_fields_count: 1 },
    },
    {
      stage_index: 2,
      stage_name: '影子流量无副作用双写回放与黄金基线差分 (Shadow Replay & Golden Diff)',
      status: 'PASSED',
      duration_ms: 45.2,
      summary: '写操作拦截 0 脏数据，黄金基线相似度 100.0% 达标。',
      metrics: { replayed_requests: 2, similarity_score_pct: 100.0 },
    },
    {
      stage_index: 3,
      stage_name: '接口契约破坏变更逆向识别与阻断 (Contract Drift Breaking Guard)',
      status: 'PASSED',
      duration_ms: 18.0,
      summary: '契约双向兼容，无 Breaking 破坏性阻断。',
      metrics: { breaking_changes_count: 0 },
    },
    {
      stage_index: 4,
      stage_name: '流量故障注入与微服务自愈韧性验证 (Chaos Resilience & RTO)',
      status: 'PASSED',
      duration_ms: 22.1,
      summary: '断路器快速跳闸 (85ms)，RTO 自愈时长 420ms，评级 EXCELLENT。',
      metrics: { trip_latency_ms: 85, rto_duration_ms: 420 },
    },
  ],
  remediation_actions: [],
  console_log_output: '\x1b[1;32m[STAGE 1/4] 生产流量旁路捕获与敏感清洗 ... OK\x1b[0m\n\x1b[1;32m[STAGE 2/4] 影子流量无副作用回放 ... OK\x1b[0m',
  executed_at: '2026-10-16T12:00:00Z',
}

const mockBlockReport = {
  pipeline_run_id: 'pl_run_102',
  pipeline_name: 'ATP-Traffic-Guard-Pipeline',
  endpoint: 'POST /api/v1/orders/checkout',
  exit_code: 1,
  overall_status: 'BLOCKED',
  stages: [
    {
      stage_index: 3,
      stage_name: '接口契约破坏变更逆向识别与阻断 (Contract Drift Breaking Guard)',
      status: 'BLOCKED',
      duration_ms: 20.0,
      summary: '检出核心响应字段 pay_token 被删除，触发 BREAKING 阻断！',
      metrics: { breaking_changes_count: 1 },
    },
  ],
  remediation_actions: ['响应体被下游核心消费，严禁删除字段！需补全或灰度升级。'],
  console_log_output: '\x1b[1;31m[STAGE 3/4] 检出 Breaking 契约破坏! 阻断发布!\x1b[0m',
  executed_at: '2026-10-16T12:05:00Z',
}

vi.mock('@/api/trafficGateway', () => ({
  trafficGuardPipelineApi: {
    run: vi.fn(),
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
  CheckCircleOutlined: { template: '<span>CheckCircle</span>' },
  ClockCircleOutlined: { template: '<span>ClockCircle</span>' },
  PlayCircleOutlined: { template: '<span>PlayCircle</span>' },
  HistoryOutlined: { template: '<span>History</span>' },
  CodeOutlined: { template: '<span>Code</span>' },
  CopyOutlined: { template: '<span>Copy</span>' },
}))

describe('TrafficGuardPipelineMonitorView.vue', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(trafficGuardPipelineApi.run).mockResolvedValue({
      message: '生产流量防线流水线执行完毕，Exit Code: 0 (PASSED)',
      report: mockPassReport as any,
    })
    vi.mocked(trafficGuardPipelineApi.listReports).mockResolvedValue({
      total: 1,
      reports: [mockPassReport as any],
    })
  })

  it('renders page hero, exit code banner, 4 checkpoint stages, and terminal log', async () => {
    const wrapper = mount(TrafficGuardPipelineMonitorView, {
      global: {
        stubs: {
          'a-card': { template: '<div class="ant-card"><slot /></div>' },
          'a-space': { template: '<div><slot /></div>' },
          'a-input': { template: '<input />' },
          'a-input-number': { template: '<input type="number" />' },
          'a-select': { template: '<select><slot /></select>' },
          'a-select-option': { template: '<option><slot /></option>' },
          'a-switch': { template: '<input type="checkbox" />' },
          'a-button': { template: '<button><slot /></button>' },
          'a-tag': { template: '<span class="ant-tag"><slot /></span>' },
        },
      },
    })

    await flushPromises()

    // 检查加载
    expect(trafficGuardPipelineApi.run).toHaveBeenCalled()
    expect(trafficGuardPipelineApi.listReports).toHaveBeenCalled()

    // 检查标题与 Exit Code
    expect(wrapper.text()).toContain('生产流量防线 Checkpoint 检查点端到端全景监控看板')
    expect(wrapper.text()).toContain('EXIT CODE 0 (PASSED)')
    expect(wrapper.text()).toContain('端到端流量防线四阶段全量通过')

    // 检查四阶段
    expect(wrapper.text()).toContain('流量捕获与敏感数据清洗')
    expect(wrapper.text()).toContain('影子流量无副作用双写回放')
    expect(wrapper.text()).toContain('接口契约破坏变更逆向识别与阻断')
    expect(wrapper.text()).toContain('流量故障注入与微服务自愈韧性验证')

    // 检查终端日志
    expect(wrapper.text()).toContain('流水线执行终端控制台日志')
    expect(wrapper.html()).toContain('color:#4ade80') // ANSI green span
  })

  it('switches preset to block and triggers Exit Code 1', async () => {
    vi.mocked(trafficGuardPipelineApi.run).mockResolvedValueOnce({
      message: '生产流量防线流水线执行完毕，Exit Code: 0 (PASSED)',
      report: mockPassReport as any,
    }).mockResolvedValueOnce({
      message: '生产流量防线流水线执行完毕，Exit Code: 1 (BLOCKED)',
      report: mockBlockReport as any,
    })

    const wrapper = mount(TrafficGuardPipelineMonitorView, {
      global: {
        stubs: {
          'a-card': { template: '<div class="ant-card"><slot /></div>' },
          'a-space': { template: '<div><slot /></div>' },
          'a-input': { template: '<input />' },
          'a-input-number': { template: '<input type="number" />' },
          'a-select': { template: '<select><slot /></select>' },
          'a-select-option': { template: '<option><slot /></option>' },
          'a-switch': { template: '<input type="checkbox" />' },
          'a-button': { template: '<button><slot /></button>' },
          'a-tag': { template: '<span class="ant-tag"><slot /></span>' },
        },
      },
    })

    await flushPromises()

    const vm = wrapper.vm as any
    await vm.applyPreset('block')
    await flushPromises()

    expect(trafficGuardPipelineApi.run).toHaveBeenCalledTimes(2)
    expect(wrapper.text()).toContain('EXIT CODE 1 (BLOCKED)')
    expect(wrapper.text()).toContain('检出硬性契约破坏变更')
    expect(wrapper.text()).toContain('响应体被下游核心消费，严禁删除字段')
  })
})
