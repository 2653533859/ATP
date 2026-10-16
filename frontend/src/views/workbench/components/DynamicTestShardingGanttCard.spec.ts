import { mount, flushPromises } from '@vue/test-utils'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import DynamicTestShardingGanttCard from './DynamicTestShardingGanttCard.vue'
import { ciImpactApi } from '@/api/ciImpact'

const mockShardingReport = {
  sharding_id: 'shard_demo_123',
  target_shards_count: 4,
  actual_shards_count: 4,
  total_cases_count: 8,
  total_estimated_duration_sec: 64.0,
  max_shard_duration_sec: 17.5,
  min_shard_duration_sec: 15.0,
  duration_variance: 0.85,
  theoretical_speedup_ratio: 3.66,
  shards: [
    {
      shard_index: 0,
      case_ids: [101, 108],
      cases_count: 2,
      estimated_duration_sec: 17.3,
      worker_assigned_id: 'worker-pod-shard-0',
    },
    {
      shard_index: 1,
      case_ids: [102, 107],
      cases_count: 2,
      estimated_duration_sec: 16.2,
      worker_assigned_id: 'worker-pod-shard-1',
    },
    {
      shard_index: 2,
      case_ids: [103, 106],
      cases_count: 2,
      estimated_duration_sec: 14.5,
      worker_assigned_id: 'worker-pod-shard-2',
    },
    {
      shard_index: 3,
      case_ids: [104, 105],
      cases_count: 2,
      estimated_duration_sec: 17.5, // 瓶颈木桶上限
      worker_assigned_id: 'worker-pod-shard-3',
    },
  ],
  created_at: '2026-10-16T10:00:00Z',
}

vi.mock('@/api/ciImpact', () => ({
  ciImpactApi: {
    partitionShards: vi.fn(),
  },
}))

vi.mock('ant-design-vue', () => ({
  message: {
    success: vi.fn(),
    error: vi.fn(),
  },
}))

vi.mock('@ant-design/icons-vue', () => ({
  AppstoreOutlined: { template: '<span>Appstore</span>' },
  ReloadOutlined: { template: '<span>Reload</span>' },
}))

describe('DynamicTestShardingGanttCard.vue', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(ciImpactApi.partitionShards).mockResolvedValue({
      message: 'LPT 动态切片装箱完成',
      report: mockShardingReport as any,
    })
  })

  it('renders card title, 3.66x speedup metric, and Gantt shard rows', async () => {
    const wrapper = mount(DynamicTestShardingGanttCard, {
      props: {
        initialCaseIds: [101, 102, 103, 104, 105, 106, 107, 108],
      },
      global: {
        stubs: {
          'a-card': { template: '<div class="ant-card"><slot name="title" /><slot /></div>' },
          'a-tag': { template: '<span class="ant-tag"><slot /></span>' },
          'a-space': { template: '<div><slot /></div>' },
          'a-radio-group': { template: '<div><slot /></div>' },
          'a-radio-button': { template: '<button><slot /></button>' },
          'a-button': { template: '<button><slot /></button>' },
          'a-spin': { template: '<div><slot /></div>' },
          'a-table': {
            props: ['dataSource'],
            template: `
              <div class="ant-table-stub">
                <div v-for="item in dataSource" :key="item.shard_index" class="row">
                  <span class="shard-col">分片 #{{ item.shard_index }}</span>
                  <span class="worker-col">{{ item.worker_assigned_id }}</span>
                </div>
              </div>
            `,
          },
        },
      },
    })

    await flushPromises()

    // 验证标题与统计指标
    expect(wrapper.text()).toContain('多容器 Worker 负载均衡动态测试切片甘特图')
    expect(wrapper.text()).toContain('3.66x')
    expect(wrapper.text()).toContain('17.5')
    expect(wrapper.text()).toContain('0.85')
    expect(wrapper.text()).toContain('8')
    expect(wrapper.text()).toContain('4 桶')

    // 验证甘特条与表格内容
    expect(wrapper.text()).toContain('Shard #0')
    expect(wrapper.text()).toContain('worker-pod-shard-0')
    expect(wrapper.text()).toContain('Shard #3')

    expect(ciImpactApi.partitionShards).toHaveBeenCalled()
  })

  it('triggers partition on shards count change', async () => {
    const wrapper = mount(DynamicTestShardingGanttCard, {
      global: {
        stubs: {
          'a-card': { template: '<div class="ant-card"><slot name="title" /><slot /></div>' },
          'a-tag': { template: '<span class="ant-tag"><slot /></span>' },
          'a-space': { template: '<div><slot /></div>' },
          'a-radio-group': { template: '<div><slot /></div>' },
          'a-radio-button': { template: '<button><slot /></button>' },
          'a-button': { template: '<button><slot /></button>' },
          'a-spin': { template: '<div><slot /></div>' },
          'a-table': { template: '<div class="ant-table-stub" />' },
        },
      },
    })

    await flushPromises()

    const vm = wrapper.vm as any
    vm.targetShards = 2
    await vm.handleRunPartition()

    expect(ciImpactApi.partitionShards).toHaveBeenCalledWith(expect.objectContaining({
      target_shards_count: 2,
    }))
  })
})
