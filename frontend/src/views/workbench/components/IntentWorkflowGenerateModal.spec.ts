import { mount, flushPromises } from '@vue/test-utils'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import IntentWorkflowGenerateModal from './IntentWorkflowGenerateModal.vue'
import { intentWorkflowApi } from '@/api/intentWorkflow'

const mockSynthesis = {
  synthesis_id: 'syn_test_001',
  workflow_id: 'wf_syn_001',
  workflow_name: '电商端到端履约工作流',
  semantic_summary: '由自然语言业务意图推导生成',
  nodes: [
    {
      node_id: 'node_1',
      node_name: '创建测试订单 (HTTP)',
      node_type: 'http',
      config: { url: 'https://shop.test/api/order/create', method: 'POST' },
    },
    {
      node_id: 'node_2',
      node_name: 'iOS 客户端支付',
      node_type: 'mobile_ios',
      config: { device_id: '00008101-IPHONE', action: 'tap' },
    },
  ],
  edges: [
    {
      edge_id: 'edge_1_2',
      source_node_id: 'node_1',
      target_node_id: 'node_2',
    },
  ],
  variable_bindings: {
    node_2: '{{node_1.output.body.order_id}}',
  },
  slots: {
    raw_prompt: '创建订单后支付',
    business_domain: 'ecommerce',
    protocols: ['HTTP', 'iOS'],
    actions: ['create', 'pay'],
    extracted_entities: ['order_id'],
    suggested_node_count: 2,
    analyzed_at: '2026-10-17T14:00:00Z',
  },
  created_at: '2026-10-17T14:00:00Z',
}

const stubs = {
  'a-modal': { template: '<div class="ant-modal-stub"><slot /></div>' },
  'a-button': { template: '<button><slot /></button>' },
  'a-textarea': {
    template: '<textarea :value="value" @input="$emit(\'update:value\', $event.target.value)" />',
    props: ['value'],
  },
  'a-input': {
    template: '<input :value="value" @input="$emit(\'update:value\', $event.target.value)" />',
    props: ['value'],
  },
  'a-tag': { template: '<span class="ant-tag-stub"><slot /></span>' },
}

describe('IntentWorkflowGenerateModal.vue', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders modal banner, preset templates, and input box when open', () => {
    const wrapper = mount(IntentWorkflowGenerateModal, {
      props: {
        open: true,
      },
      global: { stubs },
    })

    expect(wrapper.text()).toContain('Intent-to-DAG 混合工作流智能合成引擎')
    expect(wrapper.text()).toContain('推荐业务意图示例:')
    expect(wrapper.text()).toContain('电商端到端履约')
    expect(wrapper.find('textarea').exists()).toBe(true)
  })

  it('selects preset template and populates prompt textarea', async () => {
    const wrapper = mount(IntentWorkflowGenerateModal, {
      props: {
        open: true,
      },
      global: { stubs },
    })

    const templateBtns = wrapper.findAll('.template-btn')
    expect(templateBtns.length).toBeGreaterThan(0)
    await templateBtns[0].trigger('click')

    const vm = wrapper.vm as any
    expect(vm.intentPrompt).toContain('在电商系统首先用 HTTP 接口创建订单')
  })

  it('triggers generateWorkflow API and renders DAG preview & insights', async () => {
    vi.spyOn(intentWorkflowApi, 'generateWorkflow').mockResolvedValue({
      message: '合成成功',
      synthesis: mockSynthesis as any,
    })

    const wrapper = mount(IntentWorkflowGenerateModal, {
      props: {
        open: true,
      },
      global: { stubs },
    })

    const vm = wrapper.vm as any
    vm.intentPrompt = '创建订单后在 iOS 支付'
    await wrapper.vm.$nextTick()

    const generateBtn = wrapper.findAll('button').find((b) => b.text().includes('一键智能推导工作流 DAG'))
    expect(generateBtn).toBeDefined()
    await generateBtn!.trigger('click')
    await flushPromises()

    expect(intentWorkflowApi.generateWorkflow).toHaveBeenCalledWith({
      prompt: '创建订单后在 iOS 支付',
      workflow_id: undefined,
      workflow_name: undefined,
    })

    // 查验 AI 语义槽位渲染
    expect(wrapper.text()).toContain('AI 语义槽位推导结果')
    expect(wrapper.text()).toContain('ecommerce')
    expect(wrapper.text()).toContain('2 节点')

    // 查验节点卡片流渲染
    expect(wrapper.text()).toContain('创建测试订单 (HTTP)')
    expect(wrapper.text()).toContain('iOS 客户端支付')
    expect(wrapper.text()).toContain('变量依赖: {{node_1.output.body.order_id}}')
  })

  it('triggers refineWorkflow API on conversational refinement input', async () => {
    vi.spyOn(intentWorkflowApi, 'generateWorkflow').mockResolvedValue({
      message: '合成成功',
      synthesis: mockSynthesis as any,
    })

    const refinedSynthesis = {
      ...mockSynthesis,
      nodes: [
        ...mockSynthesis.nodes,
        {
          node_id: 'node_3',
          node_name: '延时等待 500ms',
          node_type: 'delay_sleep',
          config: { delay_ms: 500 },
        },
      ],
      edges: [
        ...mockSynthesis.edges,
        {
          edge_id: 'edge_2_3',
          source_node_id: 'node_2',
          target_node_id: 'node_3',
        },
      ],
    }

    vi.spyOn(intentWorkflowApi, 'refineWorkflow').mockResolvedValue({
      message: '微调成功',
      synthesis: refinedSynthesis as any,
    })

    const wrapper = mount(IntentWorkflowGenerateModal, {
      props: {
        open: true,
      },
      global: { stubs },
    })

    const vm = wrapper.vm as any
    vm.intentPrompt = '创建订单后在 iOS 支付'
    await wrapper.vm.$nextTick()

    const generateBtn = wrapper.findAll('button').find((b) => b.text().includes('一键智能推导工作流 DAG'))
    await generateBtn!.trigger('click')
    await flushPromises()

    // 设置微调指令
    vm.refineInstruction = '在支付后追加延时 500ms'
    await wrapper.vm.$nextTick()

    const refineBtn = wrapper.findAll('button').find((b) => b.text().includes('对话微调'))
    expect(refineBtn).toBeDefined()
    await refineBtn!.trigger('click')
    await flushPromises()

    expect(intentWorkflowApi.refineWorkflow).toHaveBeenCalledWith({
      synthesis_id: 'syn_test_001',
      refinement_prompt: '在支付后追加延时 500ms',
    })

    // 验证更新后的节点卡片
    expect(wrapper.text()).toContain('延时等待 500ms')
  })

  it('emits applied event and closes modal when clicking 一键应用到工作流画布', async () => {
    vi.spyOn(intentWorkflowApi, 'generateWorkflow').mockResolvedValue({
      message: '合成成功',
      synthesis: mockSynthesis as any,
    })

    const wrapper = mount(IntentWorkflowGenerateModal, {
      props: {
        open: true,
      },
      global: { stubs },
    })

    const vm = wrapper.vm as any
    vm.intentPrompt = '创建订单后在 iOS 支付'
    await wrapper.vm.$nextTick()

    const generateBtn = wrapper.findAll('button').find((b) => b.text().includes('一键智能推导工作流 DAG'))
    await generateBtn!.trigger('click')
    await flushPromises()

    const applyBtn = wrapper.findAll('button').find((b) => b.text().includes('一键应用到工作流画布'))
    expect(applyBtn).toBeDefined()
    await applyBtn!.trigger('click')

    expect(wrapper.emitted('applied')).toBeDefined()
    expect(wrapper.emitted('applied')![0][0]).toEqual({
      nodes: mockSynthesis.nodes,
      edges: mockSynthesis.edges,
      name: mockSynthesis.workflow_name,
    })
    expect(wrapper.emitted('update:open')![0]).toEqual([false])
  })
})
