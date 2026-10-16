import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import ClusterWorkerMonitorDrawer from './ClusterWorkerMonitorDrawer.vue'

const mockOverview = {
  total_nodes_registered: 3,
  total_alive_nodes: 2,
  total_concurrency_slots: 20,
  total_active_tasks: 6,
  cluster_utilization_pct: 30.0,
  average_cpu_pct: 25.5,
  average_memory_pct: 38.0,
  health_distribution: {
    HEALTHY_IDLE: 1,
    MODERATE_LOAD: 1,
    HEAVY_LOAD: 0,
    OVERLOADED: 0,
    OFFLINE: 1,
  },
}

const mockWorkers = [
  {
    worker_id: 'w_prod_shanghai_01',
    hostname: 'worker-sh-01',
    ip_address: '10.0.1.10',
    queues: ['default', 'performance'],
    status: 'online' as const,
    current_concurrency: 1,
    max_concurrency: 10,
    cpu_usage_pct: 15.0,
    memory_usage_pct: 30.0,
    heartbeat_timestamp: Date.now() / 1000,
    is_alive: true,
    load_score: 17.0,
    capacity_score: 83.0,
    capacity_level: 'HEALTHY_IDLE' as const,
    weight: 1.0,
  },
  {
    worker_id: 'w_prod_beijing_02',
    hostname: 'worker-bj-02',
    ip_address: '10.0.2.20',
    queues: ['default'],
    status: 'online' as const,
    current_concurrency: 5,
    max_concurrency: 10,
    cpu_usage_pct: 55.0,
    memory_usage_pct: 60.0,
    heartbeat_timestamp: Date.now() / 1000,
    is_alive: true,
    load_score: 53.5,
    capacity_score: 46.5,
    capacity_level: 'MODERATE_LOAD' as const,
    weight: 1.0,
  },
]

const mockGetOverview = vi.fn().mockResolvedValue(mockOverview)
const mockListWorkers = vi.fn().mockResolvedValue({ total: 2, workers: mockWorkers })
const mockSelectOptimal = vi.fn().mockResolvedValue({
  selected: true,
  worker: mockWorkers[0],
})

vi.mock('@/api/clusterWorkers', () => ({
  clusterWorkersApi: {
    getOverview: () => mockGetOverview(),
    listWorkers: (params?: unknown) => mockListWorkers(params),
    selectOptimal: (data: unknown) => mockSelectOptimal(data),
  },
}))

const globalStubs = {
  'a-drawer': { template: '<div class="ant-drawer"><slot name="title" /><slot /></div>' },
  'a-card': { template: '<div class="ant-card"><h4>{{ $attrs.title }}</h4><slot /></div>' },
  'a-button': { template: '<button class="ant-btn"><slot /></button>' },
  'a-tag': { template: '<span class="ant-tag"><slot /></span>' },
  'a-space': { template: '<div><slot /></div>' },
  'a-form': { template: '<form><slot /></form>' },
  'a-form-item': { template: '<div class="form-item"><slot /></div>' },
  'a-input': { template: '<input />' },
  'a-select': { template: '<select><slot /></select>' },
  'a-select-option': { template: '<option><slot /></option>' },
  'a-progress': { template: '<div class="ant-progress" />' },
  'a-table': {
    props: ['dataSource'],
    template: `
      <div class="ant-table">
        <div v-for="item in dataSource" :key="item.worker_id" class="table-row">
          <span>{{ item.worker_id }}</span>
          <span>{{ item.hostname }}</span>
          <span>{{ item.capacity_level }}</span>
        </div>
      </div>
    `,
  },
}

describe('ClusterWorkerMonitorDrawer.vue', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('loads overview and worker list on mount and renders metrics', async () => {
    const wrapper = mount(ClusterWorkerMonitorDrawer, {
      props: { open: true },
      global: { stubs: globalStubs },
    })
    await flushPromises()

    expect(mockGetOverview).toHaveBeenCalled()
    expect(mockListWorkers).toHaveBeenCalled()
    expect(wrapper.text()).toContain('跨节点 Worker 集群协同负载与容量分级监控台')
    expect(wrapper.text()).toContain('2') // alive nodes
    expect(wrapper.text()).toContain('3') // registered
    expect(wrapper.text()).toContain('30%') // utilization
    expect(wrapper.text()).toContain('CPU: 25.5%')
    expect(wrapper.text()).toContain('w_prod_shanghai_01')
    expect(wrapper.text()).toContain('HEALTHY_IDLE')
  })

  it('runs optimal worker selection simulation upon button click', async () => {
    const wrapper = mount(ClusterWorkerMonitorDrawer, {
      props: { open: true },
      global: { stubs: globalStubs },
    })
    await flushPromises()

    const simBtn = wrapper.findAll('button').find((b) => b.text().includes('运行最优节点选举算法'))
    expect(simBtn).toBeDefined()
    await simBtn!.trigger('click')
    await flushPromises()

    expect(mockSelectOptimal).toHaveBeenCalledWith({ required_queue: 'default' })
    expect(wrapper.text()).toContain('当前选举胜出节点')
    expect(wrapper.text()).toContain('w_prod_shanghai_01')
    expect(wrapper.text()).toContain('83')
  })
})
