import { mount, flushPromises } from '@vue/test-utils'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import HpaAutoscalingDashboardCard from './HpaAutoscalingDashboardCard.vue'
import { hpaAutoscalingApi } from '@/api/cloudNativeWorkers'

const mockPolicy = {
  policy_id: 'hpa_default_queue',
  target_queue: 'default',
  min_replicas: 1,
  max_replicas: 20,
  target_concurrency_per_pod: 5,
  target_latency_slo_sec: 15.0,
  scale_up_stabilization_sec: 0.0,
  scale_down_stabilization_sec: 60.0,
  enabled: true,
}

const mockDecision = {
  decision_id: 'hpa_dec_scale_up_001',
  policy_id: 'hpa_default_queue',
  target_queue: 'default',
  direction: 'scale_up' as const,
  current_replicas: 2,
  desired_replicas: 8,
  replicas_delta: 6,
  reason: '负载积压 30 个任务，P95 时延 25.0s 超标，建议扩容 6 个 Pod',
  evaluated_at: '2026-10-16T12:00:00Z',
  metrics_snapshot: {
    current_queue_depth: 25,
    running_tasks_count: 5,
    p95_queue_latency_sec: 25.0,
    current_replicas: 2,
  },
}

vi.mock('@/api/cloudNativeWorkers', () => ({
  hpaAutoscalingApi: {
    listPolicies: vi.fn(),
    createPolicy: vi.fn(),
    evaluateHpa: vi.fn(),
    applyScaling: vi.fn(),
    listHistory: vi.fn(),
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

describe('HpaAutoscalingDashboardCard.vue', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders card title, policy settings form, and simulation input controls on mount', async () => {
    vi.mocked(hpaAutoscalingApi.listPolicies).mockResolvedValue({
      total: 1,
      policies: [mockPolicy],
    })
    vi.mocked(hpaAutoscalingApi.listHistory).mockResolvedValue({
      total: 0,
      history: [],
    })

    const wrapper = mount(HpaAutoscalingDashboardCard, {
      global: {
        stubs: {
          'a-card': { template: '<div class="ant-card"><slot name="title" /><slot name="extra" /><slot /></div>' },
          'a-tag': { template: '<span class="ant-tag"><slot /></span>' },
          'a-space': { template: '<div><slot /></div>' },
          'a-form': { template: '<form><slot /></form>' },
          'a-form-item': { template: '<div><slot /></div>' },
          'a-input': { template: '<input />' },
          'a-input-number': { template: '<input />' },
          'a-select': { template: '<select><slot /></select>' },
          'a-select-option': { template: '<option><slot /></option>' },
          'a-button': { template: '<button><slot /></button>' },
          'a-table': { template: '<div class="ant-table" />' },
        },
      },
    })

    await flushPromises()

    expect(wrapper.text()).toContain('任务队列背压自适应 HPA 自动扩缩容看板')
    expect(wrapper.text()).toContain('实时队列背压输入模拟：')
    expect(wrapper.text()).toContain('排队积压:')
  })

  it('saves HPA policy when clicking save policy button', async () => {
    vi.mocked(hpaAutoscalingApi.listPolicies).mockResolvedValue({
      total: 0,
      policies: [],
    })
    vi.mocked(hpaAutoscalingApi.createPolicy).mockResolvedValue({
      message: '策略保存成功',
      policy: mockPolicy,
    })

    const wrapper = mount(HpaAutoscalingDashboardCard, {
      global: {
        stubs: {
          'a-card': { template: '<div class="ant-card"><slot name="title" /><slot name="extra" /><slot /></div>' },
          'a-tag': { template: '<span class="ant-tag"><slot /></span>' },
          'a-space': { template: '<div><slot /></div>' },
          'a-form': { template: '<form><slot /></form>' },
          'a-form-item': { template: '<div><slot /></div>' },
          'a-input': { template: '<input />' },
          'a-input-number': { template: '<input />' },
          'a-select': { template: '<select><slot /></select>' },
          'a-select-option': { template: '<option><slot /></option>' },
          'a-button': { template: '<button><slot /></button>' },
          'a-table': { template: '<div class="ant-table" />' },
        },
      },
    })

    await flushPromises()

    const saveBtn = wrapper.findAll('button').find((b) => b.text().includes('保存策略'))
    expect(saveBtn).toBeDefined()
    await saveBtn!.trigger('click')
    await flushPromises()

    expect(hpaAutoscalingApi.createPolicy).toHaveBeenCalledWith({
      policy_id: 'hpa_default_queue',
      target_queue: 'default',
      min_replicas: 1,
      max_replicas: 20,
      target_concurrency_per_pod: 5,
      target_latency_slo_sec: 15.0,
    })
  })

  it('evaluates HPA decision and applies scaling linkage', async () => {
    vi.mocked(hpaAutoscalingApi.listPolicies).mockResolvedValue({
      total: 1,
      policies: [mockPolicy],
    })
    vi.mocked(hpaAutoscalingApi.evaluateHpa).mockResolvedValue(mockDecision)
    vi.mocked(hpaAutoscalingApi.applyScaling).mockResolvedValue({
      message: '扩缩容联动执行完成',
      policy_id: 'hpa_default_queue',
      direction: 'scale_up',
      replicas_delta: 6,
      executed_actions: ['Provisioned pod: pod_worker_01'],
    })

    const wrapper = mount(HpaAutoscalingDashboardCard, {
      global: {
        stubs: {
          'a-card': { template: '<div class="ant-card"><slot name="title" /><slot name="extra" /><slot /></div>' },
          'a-tag': { template: '<span class="ant-tag"><slot /></span>' },
          'a-space': { template: '<div><slot /></div>' },
          'a-form': { template: '<form><slot /></form>' },
          'a-form-item': { template: '<div><slot /></div>' },
          'a-input': { template: '<input />' },
          'a-input-number': { template: '<input />' },
          'a-select': { template: '<select><slot /></select>' },
          'a-select-option': { template: '<option><slot /></option>' },
          'a-button': { template: '<button><slot /></button>' },
          'a-alert': { template: '<div class="ant-alert">{{ message }} {{ description }}</div>', props: ['message', 'description'] },
          'a-table': { template: '<div class="ant-table" />' },
        },
      },
    })

    await flushPromises()

    // 1. 评估决策
    const evalBtn = wrapper.findAll('button').find((b) => b.text().includes('评估扩缩容决策'))
    expect(evalBtn).toBeDefined()
    await evalBtn!.trigger('click')
    await flushPromises()

    expect(hpaAutoscalingApi.evaluateHpa).toHaveBeenCalledWith({
      policy_id: 'hpa_default_queue',
      current_queue_depth: 25,
      running_tasks_count: 5,
      p95_queue_latency_sec: 25.0,
      current_replicas: 2,
    })

    // 验证决策结果渲染
    expect(wrapper.text()).toContain('[HPA 扩缩容决策 #hpa_dec_scale_up_001]')
    expect(wrapper.text()).toContain('推荐动作: 弹性扩容 (Scale Up)')
    expect(wrapper.text()).toContain('8') // desired
    expect(wrapper.text()).toContain('+6') // delta

    // 2. 一键应用联动
    const applyBtn = wrapper.findAll('button').find((b) => b.text().includes('一键应用扩缩容联动'))
    expect(applyBtn).toBeDefined()
    await applyBtn!.trigger('click')
    await flushPromises()

    expect(hpaAutoscalingApi.applyScaling).toHaveBeenCalledWith({
      decision_id: 'hpa_dec_scale_up_001',
      policy_id: 'hpa_default_queue',
      direction: 'scale_up',
      replicas_delta: 6,
      target_queue: 'default',
    })
  })
})
