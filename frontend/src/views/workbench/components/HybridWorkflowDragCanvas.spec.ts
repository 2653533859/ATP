import { mount, flushPromises } from '@vue/test-utils'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import HybridWorkflowDragCanvas from './HybridWorkflowDragCanvas.vue'
import { hybridWorkflowApi } from '@/api/hybridWorkflow'

vi.mock('@/api/hybridWorkflow', () => ({
  hybridWorkflowApi: {
    saveDraft: vi.fn(),
    executeWorkflow: vi.fn(),
  },
}))

vi.mock('ant-design-vue', () => ({
  message: {
    success: vi.fn(),
    info: vi.fn(),
    error: vi.fn(),
  },
}))

describe('HybridWorkflowDragCanvas.vue', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(hybridWorkflowApi.saveDraft).mockResolvedValue({
      message: '保存成功',
      workflow_id: 'wf_001',
    })
    vi.mocked(hybridWorkflowApi.executeWorkflow).mockResolvedValue({
      message: '执行完成',
      report: {
        run_id: 'run_test_123',
        workflow_id: 'wf_001',
        workflow_name: '测试工作流',
        total_nodes: 2,
        executed_nodes_count: 2,
        status: 'SUCCESS',
        node_records: [
          {
            node_id: 'n1',
            node_name: '节点1',
            node_type: 'http_request',
            status: 'SUCCESS',
            duration_ms: 12.0,
            input_data: {},
            output_data: {},
            executed_at: '',
          },
        ],
        context_outputs: {},
        start_time: '',
        end_time: '',
        total_duration_ms: 50.0,
      },
    })
  })

  function createWrapper(props = {}) {
    return mount(HybridWorkflowDragCanvas, {
      props: {
        workflowId: 'wf_test_001',
        workflowName: '多协议跨端端到端混合测试工作流',
        ...props,
      },
      global: {
        stubs: {
          'a-button': {
            template: '<button type="button" @click="$emit(\'click\')"><slot /></button>',
            props: ['type', 'loading', 'disabled'],
          },
          'a-tag': {
            template: '<span class="ant-tag"><slot /></span>',
          },
          'a-space': {
            template: '<div class="ant-space"><slot /></div>',
          },
          'a-drawer': {
            template: '<div v-if="open" class="ant-drawer"><slot /></div>',
            props: ['open'],
          },
          'a-descriptions': {
            template: '<div class="ant-descriptions"><slot /></div>',
          },
          'a-descriptions-item': {
            template: '<div class="ant-descriptions-item"><slot /></div>',
          },
          'a-form': {
            template: '<form class="ant-form"><slot /></form>',
          },
          'a-form-item': {
            template: '<div class="ant-form-item"><slot /></div>',
            props: ['label'],
          },
          'a-input': {
            template: '<input class="ant-input" :value="value" @input="$emit(\'update:value\', $event.target.value)" />',
            props: ['value'],
          },
          'a-textarea': {
            template: '<textarea class="ant-textarea" :value="value" />',
            props: ['value'],
          },
          'a-divider': {
            template: '<hr class="ant-divider" />',
          },
        },
      },
    })
  }

  it('renders workflow name and node palette items', async () => {
    const wrapper = createWrapper()
    await flushPromises()

    expect(wrapper.text()).toContain('多协议跨端端到端混合测试工作流')
    expect(wrapper.text()).toContain('节点组件库')
    expect(wrapper.text()).toContain('HTTP API 请求')
    expect(wrapper.text()).toContain('gRPC 微服务调用')
    expect(wrapper.text()).toContain('Web UI (Playwright)')
    expect(wrapper.text()).toContain('Android 真机执行')
    expect(wrapper.text()).toContain('iOS 真机 WDA 执行')
  })

  it('allows clicking palette to add node to canvas', async () => {
    const wrapper = createWrapper()
    await flushPromises()

    const addBtn = wrapper.find('.node-color-http')
    await addBtn.trigger('click')
    await flushPromises()

    const nodes = wrapper.findAll('.canvas-node-card')
    expect(nodes.length).toBe(1)
    expect(wrapper.text()).toContain('HTTP / REST 接口')
  })

  it('loads ecommerce preset and executes workflow', async () => {
    const wrapper = createWrapper()
    await flushPromises()

    // 载入预置
    await (wrapper.vm as any).loadEcommercePreset()
    await flushPromises()

    const nodes = wrapper.findAll('.canvas-node-card')
    expect(nodes.length).toBe(4)

    // 触发执行
    await (wrapper.vm as any).handleExecuteWorkflow()
    await flushPromises()

    expect(hybridWorkflowApi.executeWorkflow).toHaveBeenCalledWith(
      expect.objectContaining({
        workflow_id: 'wf_test_001',
      })
    )
    expect(wrapper.emitted('executed')).toBeTruthy()
  })
})
