import { mount, flushPromises } from '@vue/test-utils'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import WorkerFailoverRecoveryCard from './WorkerFailoverRecoveryCard.vue'
import { clusterWorkersApi } from '@/api/clusterWorkers'

const mockHistoryReport = {
  report_id: 'failover_hist_001',
  timestamp: '2026-10-16T12:00:00Z',
  dead_worker_ids: ['worker_crash_99'],
  recovered_tasks: [
    {
      task_id: 'task_rec_01',
      task_name: '核心结算链路测试',
      dead_worker_id: 'worker_crash_99',
      action: 'rescheduled' as const,
      retry_count: 1,
      max_retries: 3,
    },
  ],
  aborted_tasks: [
    {
      task_id: 'task_abort_02',
      task_name: '死循环异常用例',
      dead_worker_id: 'worker_crash_99',
      action: 'aborted' as const,
      reason: 'Max retry limit exceeded (3 >= 3)',
    },
  ],
  orphan_tasks_scanned: 2,
}

vi.mock('@/api/clusterWorkers', () => ({
  clusterWorkersApi: {
    triggerFailoverScan: vi.fn(),
    listFailoverHistory: vi.fn(),
  },
}))

vi.mock('ant-design-vue', () => ({
  message: {
    success: vi.fn(),
    warning: vi.fn(),
    error: vi.fn(),
  },
}))

describe('WorkerFailoverRecoveryCard.vue', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders card title, description, and history summary on mount', async () => {
    vi.mocked(clusterWorkersApi.listFailoverHistory).mockResolvedValue({
      total: 1,
      history: [mockHistoryReport],
    })

    const wrapper = mount(WorkerFailoverRecoveryCard, {
      global: {
        stubs: {
          'a-card': { template: '<div class="ant-card"><slot name="title" /><slot name="extra" /><slot /></div>' },
          'a-tag': { template: '<span class="ant-tag"><slot /></span>' },
          'a-space': { template: '<div><slot /></div>' },
          'a-input-number': { template: '<input />' },
          'a-button': { template: '<button @click="$emit(\'click\')"><slot /></button>' },
          'a-alert': { template: '<div class="ant-alert">{{ message }} {{ description }}</div>', props: ['message', 'description'] },
          'a-table': {
            template: `
              <div class="ant-table">
                <div v-for="item in dataSource" :key="item.task_id" class="row">
                  <slot name="bodyCell" :column="{ key: 'action' }" :record="item" />
                  <slot name="bodyCell" :column="{ key: 'retry' }" :record="item" />
                  <slot name="bodyCell" :column="{ key: 'reason' }" :record="item" />
                </div>
              </div>
            `,
            props: ['dataSource'],
          },
        },
      },
    })

    await flushPromises()

    expect(wrapper.text()).toContain('跨节点 Worker 失联检测与孤儿任务故障转移')
    expect(wrapper.text()).toContain('高可用容灾与熔断')
    expect(wrapper.text()).toContain('节点心跳超时（默认 ≥30 秒）即刻判定为失联下线')

    // 验证最新报告渲染
    expect(wrapper.text()).toContain('worker_crash_99')
    expect(wrapper.text()).toContain('重新分发中 (rescheduled)')
    expect(wrapper.text()).toContain('第 1 / 3 次重试')
    expect(wrapper.text()).toContain('安全熔断终止 (aborted)')
    expect(wrapper.text()).toContain('Max retry limit exceeded')
  })

  it('triggers sweep scan and renders warning alert for detected dead workers', async () => {
    vi.mocked(clusterWorkersApi.listFailoverHistory).mockResolvedValue({
      total: 0,
      history: [],
    })

    vi.mocked(clusterWorkersApi.triggerFailoverScan).mockResolvedValue(mockHistoryReport)

    const wrapper = mount(WorkerFailoverRecoveryCard, {
      global: {
        stubs: {
          'a-card': { template: '<div class="ant-card"><slot name="title" /><slot name="extra" /><slot /></div>' },
          'a-tag': { template: '<span class="ant-tag"><slot /></span>' },
          'a-space': { template: '<div><slot /></div>' },
          'a-input-number': { template: '<input />' },
          'a-button': { template: '<button @click="$emit(\'click\')"><slot /></button>' },
          'a-alert': { template: '<div class="ant-alert">{{ message }} {{ description }}</div>', props: ['message', 'description'] },
          'a-table': { template: '<div class="ant-table" />' },
        },
      },
    })

    await flushPromises()

    const scanBtn = wrapper.findAll('button').find((b) => b.text().includes('全网失联巡检 (Sweep Scan)'))
    expect(scanBtn).toBeDefined()
    await scanBtn!.trigger('click')
    await flushPromises()

    expect(clusterWorkersApi.triggerFailoverScan).toHaveBeenCalledWith(30)
    expect(wrapper.text()).toContain('[巡检报告 #failover_hist_001]')
    expect(wrapper.text()).toContain('扫描孤儿任务 2 个，标记失联节点 1 个')
  })
})
