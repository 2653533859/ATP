import { mount, flushPromises } from '@vue/test-utils'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import ElasticWorkerAutoscalerDrawer from './ElasticWorkerAutoscalerDrawer.vue'
import { elasticWorkerAutoscalerApi } from '@/api/cloudNativeCluster'

const mockClusterStatus = {
  current_active_replicas: 2,
  min_replicas: 1,
  max_replicas: 20,
  allocatable_cpu_cores: 32.0,
  allocatable_memory_gib: 64.0,
  used_cpu_cores: 1.0,
  used_memory_gib: 2.0,
  cpu_usage_pct: 3.1,
  memory_usage_pct: 3.1,
  last_scale_time: '2026-10-17T10:00:00Z',
  total_scaling_events: 1,
}

const mockDecision = {
  decision_id: 'scale_1001_20',
  action: 'SCALE_UP' as const,
  current_replicas: 2,
  desired_replicas: 5,
  allocated_replicas: 5,
  queue_depth: 20,
  reason: '检测到任务队列积压(20)，动态扩容 Worker 副本：2 -> 5。',
  arbitration_status: 'SUFFICIENT' as const,
  cpu_utilization_estimate_pct: 7.8,
  memory_utilization_estimate_pct: 7.8,
  created_at: '2026-10-17T10:01:00Z',
}

vi.mock('@/api/cloudNativeCluster', () => ({
  elasticWorkerAutoscalerApi: {
    getStatus: vi.fn(),
    getEvents: vi.fn(),
    evaluate: vi.fn(),
    apply: vi.fn(),
    clearEvents: vi.fn(),
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
  CloudServerOutlined: { template: '<span>CloudServer</span>' },
  ThunderboltOutlined: { template: '<span>Thunderbolt</span>' },
  ReloadOutlined: { template: '<span>Reload</span>' },
  DeleteOutlined: { template: '<span>Delete</span>' },
}))

describe('ElasticWorkerAutoscalerDrawer.vue', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(elasticWorkerAutoscalerApi.getStatus).mockResolvedValue(mockClusterStatus as any)
    vi.mocked(elasticWorkerAutoscalerApi.getEvents).mockResolvedValue({ total: 1, events: [mockDecision as any] })
    vi.mocked(elasticWorkerAutoscalerApi.evaluate).mockResolvedValue({
      message: '扩缩容决策评估完成',
      decision: mockDecision as any,
    })
    vi.mocked(elasticWorkerAutoscalerApi.apply).mockResolvedValue({
      status: 'APPLIED',
      decision: mockDecision as any,
      active_replicas: 5,
      message: '扩缩容调度成功执行',
    })
  })

  it('renders header, quota watermark cards, and autoscaling decision', async () => {
    const wrapper = mount(ElasticWorkerAutoscalerDrawer, {
      props: {
        open: true,
      },
      global: {
        stubs: {
          'a-drawer': { template: '<div class="ant-drawer"><slot /></div>' },
          'a-button': { template: '<button><slot /></button>' },
          'a-space': { template: '<div><slot /></div>' },
          'a-row': { template: '<div><slot /></div>' },
          'a-col': { template: '<div><slot /></div>' },
          'a-progress': { template: '<div class="ant-progress" />' },
          'a-slider': { template: '<input type="range" />' },
          'a-input-number': { template: '<input type="number" />' },
          'a-tag': { template: '<span class="ant-tag"><slot /></span>' },
          'a-table': { template: '<div class="ant-table-stub" />' },
        },
      },
    })

    await flushPromises()

    expect(elasticWorkerAutoscalerApi.getStatus).toHaveBeenCalled()
    expect(elasticWorkerAutoscalerApi.getEvents).toHaveBeenCalled()
    expect(elasticWorkerAutoscalerApi.evaluate).toHaveBeenCalled()

    // 检查机制标题与配额指标
    expect(wrapper.text()).toContain('动态 Worker 容器弹性伸缩与配额仲裁引擎')
    expect(wrapper.text()).toContain('SCALE_UP')
    expect(wrapper.text()).toContain('SUFFICIENT')
    expect(wrapper.text()).toContain('2 -> 5')

    // 触发 apply
    const vm = wrapper.vm as any
    await vm.handleApply()
    await flushPromises()

    expect(elasticWorkerAutoscalerApi.apply).toHaveBeenCalledWith({ queue_depth: 20 })
  })
})
