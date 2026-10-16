import { mount, flushPromises } from '@vue/test-utils'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import AdaptiveTaskQueueDrawer from './AdaptiveTaskQueueDrawer.vue'
import { clusterWorkersApi } from '@/api/clusterWorkers'

const mockTasks = [
  {
    task_id: 'task_p0_001',
    task_name: '线上阻断紧急冒烟测试 (P0)',
    queue_name: 'default',
    priority: 'P0',
    assigned_worker_id: 'worker_node_1',
    status: 'running',
    enqueued_at: Date.now() - 5000,
    started_at: Date.now() - 3000,
    estimated_duration_sec: 15.0,
    preempted_count: 0,
    preempted_by_task_id: null,
  },
  {
    task_id: 'task_p2_002',
    task_name: '常规自动化回归用例测试 (P2)',
    queue_name: 'default',
    priority: 'P2',
    assigned_worker_id: null,
    status: 'suspended',
    enqueued_at: Date.now() - 10000,
    started_at: null,
    estimated_duration_sec: 40.0,
    preempted_count: 1,
    preempted_by_task_id: 'task_p0_001',
  },
  {
    task_id: 'task_p2_003',
    task_name: '性能基线压测任务',
    queue_name: 'default',
    priority: 'P2',
    assigned_worker_id: null,
    status: 'queued',
    enqueued_at: Date.now() - 2000,
    started_at: null,
    estimated_duration_sec: 60.0,
    preempted_count: 0,
    preempted_by_task_id: null,
  },
]

const mockEtaResult = {
  task_id: 'task_p2_003',
  status: 'queued',
  queue_position: 2,
  total_queued_in_line: 2,
  estimated_wait_seconds: 18.5,
  active_workers_count: 2,
  message: '前方有 1 个任务排队，预计 18.5 秒后分配 Worker',
}

vi.mock('@/api/clusterWorkers', () => ({
  clusterWorkersApi: {
    listTasks: vi.fn(),
    enqueueTask: vi.fn(),
    completeTask: vi.fn(),
    getTaskEta: vi.fn(),
  },
}))

vi.mock('ant-design-vue', () => ({
  message: {
    success: vi.fn(),
    warning: vi.fn(),
    error: vi.fn(),
  },
}))

describe('AdaptiveTaskQueueDrawer.vue', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders drawer title and queue waterline metric cards correctly', async () => {
    vi.mocked(clusterWorkersApi.listTasks).mockResolvedValue({
      total: mockTasks.length,
      tasks: mockTasks as any,
    })

    const wrapper = mount(AdaptiveTaskQueueDrawer, {
      props: {
        open: true,
      },
      global: {
        stubs: {
          'a-drawer': { template: '<div><slot name="title" /><slot /></div>' },
          'a-card': { template: '<div class="ant-card"><slot /></div>' },
          'a-button': { template: '<button @click="$emit(\'click\')"><slot /></button>' },
          'a-select': { template: '<select><slot /></select>' },
          'a-select-option': { template: '<option><slot /></option>' },
          'a-space': { template: '<div><slot /></div>' },
          'a-table': {
            template: `
              <div class="ant-table">
                <div v-for="item in dataSource" :key="item.task_id" class="row">
                  <slot name="bodyCell" :column="{ key: 'task_name' }" :record="item" />
                  <slot name="bodyCell" :column="{ key: 'priority' }" :record="item" />
                  <slot name="bodyCell" :column="{ key: 'status' }" :record="item" />
                  <slot name="bodyCell" :column="{ key: 'worker' }" :record="item" />
                  <slot name="bodyCell" :column="{ key: 'actions' }" :record="item" />
                </div>
              </div>
            `,
            props: ['dataSource'],
          },
          'a-tag': { template: '<span class="ant-tag"><slot /></span>' },
          'a-alert': { template: '<div class="ant-alert">{{ message }} {{ description }}</div>', props: ['message', 'description'] },
        },
      },
    })

    await flushPromises()

    expect(wrapper.text()).toContain('自适应任务排队水位与 P0 弹性抢占调度控制台')
    expect(wrapper.text()).toContain('正在执行中 (Running)')
    expect(wrapper.text()).toContain('排队等待中 (Queued)')
    expect(wrapper.text()).toContain('被弹性抢占挂起 (Suspended)')

    // 验证表格内容
    expect(wrapper.text()).toContain('线上阻断紧急冒烟测试 (P0)')
    expect(wrapper.text()).toContain('常规自动化回归用例测试 (P2)')
    expect(wrapper.text()).toContain('被抢占 1 次')
    expect(wrapper.text()).toContain('worker_node_1')
  })

  it('calculates ETA for a queued task and renders alert banner', async () => {
    vi.mocked(clusterWorkersApi.listTasks).mockResolvedValue({
      total: mockTasks.length,
      tasks: mockTasks as any,
    })
    vi.mocked(clusterWorkersApi.getTaskEta).mockResolvedValue(mockEtaResult)

    const wrapper = mount(AdaptiveTaskQueueDrawer, {
      props: {
        open: true,
      },
      global: {
        stubs: {
          'a-drawer': { template: '<div><slot name="title" /><slot /></div>' },
          'a-card': { template: '<div class="ant-card"><slot /></div>' },
          'a-button': { template: '<button @click="$emit(\'click\')"><slot /></button>' },
          'a-select': { template: '<select><slot /></select>' },
          'a-select-option': { template: '<option><slot /></option>' },
          'a-space': { template: '<div><slot /></div>' },
          'a-table': {
            template: `
              <div class="ant-table">
                <div v-for="item in dataSource" :key="item.task_id" class="row">
                  <slot name="bodyCell" :column="{ key: 'actions' }" :record="item" />
                </div>
              </div>
            `,
            props: ['dataSource'],
          },
          'a-tag': { template: '<span class="ant-tag"><slot /></span>' },
          'a-alert': { template: '<div class="ant-alert">{{ message }} {{ description }}</div>', props: ['message', 'description'] },
        },
      },
    })

    await flushPromises()

    // 找到测算 ETA 按钮并点击
    const etaButtons = wrapper.findAll('button').filter((b) => b.text().includes('测算 ETA'))
    expect(etaButtons.length).toBeGreaterThan(0)
    await etaButtons[0].trigger('click')
    await flushPromises()

    expect(clusterWorkersApi.getTaskEta).toHaveBeenCalledWith('task_p2_002')
    expect(wrapper.text()).toContain('当前排在队列第 2 位')
    expect(wrapper.text()).toContain('预计等待 18.5 秒')
  })
  it('triggers P0 quick enqueue and handles preemption feedback', async () => {
    vi.mocked(clusterWorkersApi.listTasks).mockResolvedValue({
      total: mockTasks.length,
      tasks: mockTasks as any,
    })
    vi.mocked(clusterWorkersApi.enqueueTask).mockResolvedValue({
      task: mockTasks[0] as any,
      preempted: true,
    })

    const wrapper = mount(AdaptiveTaskQueueDrawer, {
      props: {
        open: true,
      },
      global: {
        stubs: {
          'a-drawer': { template: '<div><slot name="title" /><slot /></div>' },
          'a-card': { template: '<div class="ant-card"><slot /></div>' },
          'a-button': { template: '<button @click="$emit(\'click\')"><slot /></button>' },
          'a-select': { template: '<select><slot /></select>' },
          'a-select-option': { template: '<option><slot /></option>' },
          'a-space': { template: '<div><slot /></div>' },
          'a-table': { template: '<div class="ant-table" />' },
          'a-tag': { template: '<span class="ant-tag"><slot /></span>' },
          'a-alert': { template: '<div class="ant-alert" />' },
        },
      },
    })

    await flushPromises()

    const p0Button = wrapper.findAll('button').find((b) => b.text().includes('模拟提交 P0 紧急抢占'))
    expect(p0Button).toBeDefined()
    await p0Button!.trigger('click')
    await flushPromises()

    expect(clusterWorkersApi.enqueueTask).toHaveBeenCalledWith({
      task_name: '线上阻断紧急冒烟测试 (P0)',
      queue_name: 'default',
      priority: 'P0',
      allow_preemption: true,
    })
  })
})
