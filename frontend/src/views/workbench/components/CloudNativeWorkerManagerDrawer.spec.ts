import { mount, flushPromises } from '@vue/test-utils'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import CloudNativeWorkerManagerDrawer from './CloudNativeWorkerManagerDrawer.vue'
import { cloudNativeWorkersApi } from '@/api/cloudNativeWorkers'

const mockPods = [
  {
    pod_id: 'pod_worker_k8s_001',
    worker_name: 'k8s-worker-prod-01',
    image: 'atp/worker-python:3.12-v1',
    runtime: 'kubernetes' as const,
    assigned_queue: 'default',
    resource_quota: {
      cpu_limit_cores: 2.0,
      memory_limit_mb: 2048,
      cpu_request_cores: 0.5,
      memory_request_mb: 512,
    },
    status: 'running' as const,
    created_at: '2026-10-16T12:00:00Z',
    started_at: '2026-10-16T12:00:02Z',
    terminated_at: null,
    exit_code: null,
    logs_count: 2,
    logs: ['[INIT] Pod initialized', '[RUN] Listening for jobs'],
  },
  {
    pod_id: 'pod_worker_docker_002',
    worker_name: 'docker-worker-api-02',
    image: 'atp/worker-python:3.12-v1',
    runtime: 'docker' as const,
    assigned_queue: 'api',
    resource_quota: {
      cpu_limit_cores: 1.0,
      memory_limit_mb: 1024,
      cpu_request_cores: 0.5,
      memory_request_mb: 512,
    },
    status: 'terminated' as const,
    created_at: '2026-10-16T11:00:00Z',
    started_at: '2026-10-16T11:00:01Z',
    terminated_at: '2026-10-16T11:30:00Z',
    exit_code: 0,
    logs_count: 3,
    logs: ['[INIT] Docker started', '[TERM] Terminated gracefully'],
  },
]

vi.mock('@/api/cloudNativeWorkers', () => ({
  cloudNativeWorkersApi: {
    listPods: vi.fn(),
    provisionPod: vi.fn(),
    getPod: vi.fn(),
    terminatePod: vi.fn(),
    reapStalePods: vi.fn(),
  },
}))

vi.mock('ant-design-vue', () => ({
  message: {
    success: vi.fn(),
    warning: vi.fn(),
    error: vi.fn(),
  },
}))

describe('CloudNativeWorkerManagerDrawer.vue', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders drawer header, provisioning form, and resource waterline KPIs on mount', async () => {
    vi.mocked(cloudNativeWorkersApi.listPods).mockResolvedValue({
      total: mockPods.length,
      pods: mockPods,
    })

    const wrapper = mount(CloudNativeWorkerManagerDrawer, {
      props: {
        open: true,
      },
      global: {
        stubs: {
          'a-drawer': { template: '<div><slot name="title" /><slot /></div>' },
          'a-card': { template: '<div class="ant-card"><slot /></div>' },
          'a-tag': { template: '<span class="ant-tag"><slot /></span>' },
          'a-space': { template: '<div><slot /></div>' },
          'a-form': { template: '<form><slot /></form>' },
          'a-form-item': { template: '<div><slot /></div>' },
          'a-input': { template: '<input />' },
          'a-input-number': { template: '<input />' },
          'a-select': { template: '<select><slot /></select>' },
          'a-select-option': { template: '<option><slot /></option>' },
          'a-button': { template: '<button><slot /></button>' },
          'a-table': {
            template: `
              <div class="ant-table">
                <div v-for="item in dataSource" :key="item.pod_id" class="row">
                  <slot name="bodyCell" :column="{ key: 'worker_name' }" :record="item" />
                  <slot name="bodyCell" :column="{ key: 'runtime' }" :record="item" />
                  <slot name="bodyCell" :column="{ key: 'queue' }" :record="item" />
                  <slot name="bodyCell" :column="{ key: 'quota' }" :record="item" />
                  <slot name="bodyCell" :column="{ key: 'status' }" :record="item" />
                  <slot name="bodyCell" :column="{ key: 'actions' }" :record="item" />
                </div>
              </div>
            `,
            props: ['dataSource'],
          },
          'a-modal': { template: '<div class="ant-modal"><slot /></div>' },
        },
      },
    })

    await flushPromises()

    expect(wrapper.text()).toContain('云原生弹性 Worker 容器 Pod 调度与配额管理中心')
    expect(wrapper.text()).toContain('运行中 Pod 实例 (Running)')
    expect(wrapper.text()).toContain('已分配 CPU 核心总量')

    // 验证 Pod 列表渲染
    expect(wrapper.text()).toContain('k8s-worker-prod-01')
    expect(wrapper.text()).toContain('pod_worker_k8s_001')
    expect(wrapper.text()).toContain('KUBERNETES')
    expect(wrapper.text()).toContain('2C')
    expect(wrapper.text()).toContain('docker-worker-api-02')
  })

  it('triggers on-demand worker pod provisioning and refreshes list', async () => {
    vi.mocked(cloudNativeWorkersApi.listPods).mockResolvedValue({
      total: 0,
      pods: [],
    })
    vi.mocked(cloudNativeWorkersApi.provisionPod).mockResolvedValue({
      message: 'Pod 拉起成功',
      pod: mockPods[0],
    })

    const wrapper = mount(CloudNativeWorkerManagerDrawer, {
      props: {
        open: true,
      },
      global: {
        stubs: {
          'a-drawer': { template: '<div><slot name="title" /><slot /></div>' },
          'a-card': { template: '<div class="ant-card"><slot /></div>' },
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
          'a-modal': { template: '<div />' },
        },
      },
    })

    await flushPromises()

    const provBtn = wrapper.findAll('button').find((b) => b.text().includes('拉起 Worker Pod'))
    expect(provBtn).toBeDefined()
    await provBtn!.trigger('click')
    await flushPromises()

    expect(cloudNativeWorkersApi.provisionPod).toHaveBeenCalledWith({
      worker_name: 'k8s-worker-prod-01',
      image: 'atp/worker-python:3.12-v1',
      assigned_queue: 'default',
      runtime: 'kubernetes',
      cpu_limit_cores: 2.0,
      memory_limit_mb: 2048,
    })
    expect(cloudNativeWorkersApi.listPods).toHaveBeenCalledTimes(2)
  })

  it('opens logs modal and fetches pod console output', async () => {
    vi.mocked(cloudNativeWorkersApi.listPods).mockResolvedValue({
      total: 1,
      pods: [mockPods[0]],
    })
    vi.mocked(cloudNativeWorkersApi.getPod).mockResolvedValue(mockPods[0])

    const wrapper = mount(CloudNativeWorkerManagerDrawer, {
      props: {
        open: true,
      },
      global: {
        stubs: {
          'a-drawer': { template: '<div><slot name="title" /><slot /></div>' },
          'a-card': { template: '<div class="ant-card"><slot /></div>' },
          'a-tag': { template: '<span class="ant-tag"><slot /></span>' },
          'a-space': { template: '<div><slot /></div>' },
          'a-form': { template: '<form><slot /></form>' },
          'a-form-item': { template: '<div><slot /></div>' },
          'a-input': { template: '<input />' },
          'a-input-number': { template: '<input />' },
          'a-select': { template: '<select><slot /></select>' },
          'a-select-option': { template: '<option><slot /></option>' },
          'a-button': { template: '<button><slot /></button>' },
          'a-table': {
            template: `
              <div class="ant-table">
                <div v-for="item in dataSource" :key="item.pod_id" class="row">
                  <slot name="bodyCell" :column="{ key: 'actions' }" :record="item" />
                </div>
              </div>
            `,
            props: ['dataSource'],
          },
          'a-modal': { template: '<div class="ant-modal"><slot /></div>' },
        },
      },
    })

    await flushPromises()

    const logBtn = wrapper.findAll('button').find((b) => b.text().includes('查看日志'))
    expect(logBtn).toBeDefined()
    await logBtn!.trigger('click')
    await flushPromises()

    expect(cloudNativeWorkersApi.getPod).toHaveBeenCalledWith('pod_worker_k8s_001')
    expect(wrapper.text()).toContain('[INIT] Pod initialized')
    expect(wrapper.text()).toContain('[RUN] Listening for jobs')
  })
})
