import { mount, flushPromises } from '@vue/test-utils'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import HybridWorkflowWorkbenchView from './HybridWorkflowWorkbenchView.vue'
import { hybridWorkflowApi } from '@/api/hybridWorkflow'

const mockRuns = [
  {
    run_id: 'wfrun_0192a8b7c6d5',
    workflow_id: 'wf_e2e_hybrid_master',
    workflow_name: '多协议跨端端到端综合业务链路',
    total_nodes: 5,
    executed_nodes_count: 5,
    status: 'SUCCESS',
    node_records: [],
    context_outputs: {},
    start_time: '2026-10-17 12:30:00',
    end_time: '2026-10-17 12:30:05',
    total_duration_ms: 250.0,
  },
]

vi.mock('@/api/hybridWorkflow', () => ({
  hybridWorkflowApi: {
    listRuns: vi.fn(),
    getRun: vi.fn(),
  },
}))

vi.mock('vue-i18n', () => ({
  useI18n: () => ({
    t: (key: string, fallback?: string) => fallback || key,
  }),
}))

describe('HybridWorkflowWorkbenchView.vue', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(hybridWorkflowApi.listRuns).mockResolvedValue({
      total: 1,
      runs: mockRuns as any,
    })
  })

  function createWrapper() {
    return mount(HybridWorkflowWorkbenchView, {
      global: {
        stubs: {
          'a-button': {
            template: '<button type="button" @click="$emit(\'click\')"><slot /></button>',
            props: ['type'],
          },
          'a-card': {
            template: '<div class="ant-card"><slot /><slot name="extra" /></div>',
            props: ['title'],
          },
          'a-tag': {
            template: '<span class="ant-tag"><slot /></span>',
          },
          'a-space': {
            template: '<div class="ant-space"><slot /></div>',
          },
          'a-input-search': {
            template: '<input class="ant-input-search" :value="value" @input="$emit(\'update:value\', $event.target.value)" />',
            props: ['value'],
          },
          'a-modal': {
            template: '<div v-if="open" class="ant-modal"><slot /></div>',
            props: ['open'],
          },
          'a-table': {
            template: `
              <div class="ant-table">
                <div v-for="item in dataSource" :key="item.run_id" class="table-row">
                  <span class="row-run-id">{{ item.run_id }}</span>
                  <span class="row-name">{{ item.workflow_name }}</span>
                  <button class="view-btn" @click="$parent.$emit('view-detail', item)">查看报告</button>
                </div>
              </div>
            `,
            props: ['dataSource', 'columns'],
          },
          HybridWorkflowDragCanvas: {
            template: '<div class="hybrid-workflow-drag-canvas-stub" />',
            props: ['workflowId', 'workflowName'],
          },
          VisualCoverageGapInspectorDrawer: {
            template: '<div v-if="open" class="visual-coverage-gap-inspector-drawer-stub" />',
            props: ['open'],
          },
        },
      },
    })
  }

  it('renders workbench title and 4 Bento KPI cards', async () => {
    const wrapper = createWrapper()
    await flushPromises()

    expect(wrapper.text()).toContain('多协议多端混合工作流编排与漏测血缘中枢')
    expect(wrapper.text()).toContain('混合工作流执行通过率')
    expect(wrapper.text()).toContain('98.5%')
    expect(wrapper.text()).toContain('纳管跨端多协议节点')
    expect(wrapper.text()).toContain('业务与契约漏测盲区率')
    expect(wrapper.text()).toContain('变量总线动态上下文注入')
  })

  it('renders canvas stub and table rows', async () => {
    const wrapper = createWrapper()
    await flushPromises()

    expect(wrapper.find('.hybrid-workflow-drag-canvas-stub').exists()).toBe(true)
    expect(wrapper.text()).toContain('wfrun_0192a8b7c6d5')
    expect(wrapper.text()).toContain('多协议跨端端到端综合业务链路')
  })

  it('opens coverage gap inspector drawer when button is clicked', async () => {
    const wrapper = createWrapper()
    await flushPromises()

    // 触发漏测血缘深度透视
    const buttons = wrapper.findAll('header button')
    await buttons[1].trigger('click')
    await flushPromises()

    expect(wrapper.find('.visual-coverage-gap-inspector-drawer-stub').exists()).toBe(true)
  })
})
