import { defineComponent, h } from 'vue'
import { mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import AILLMConfigList from './AILLMConfigList.vue'

const {
  configList,
  discoverModels,
  testConnection,
  messageError,
  messageSuccess,
  messageWarning,
} = vi.hoisted(() => ({
  configList: vi.fn(),
  discoverModels: vi.fn(),
  testConnection: vi.fn(),
  messageError: vi.fn(),
  messageSuccess: vi.fn(),
  messageWarning: vi.fn(),
}))

vi.mock('vue-i18n', () => ({
  useI18n: () => ({
    t: (key: string, params?: Record<string, unknown>) =>
      params ? `${key}:${JSON.stringify(params)}` : key,
  }),
}))

vi.mock('ant-design-vue', () => ({
  message: {
    error: messageError,
    success: messageSuccess,
    warning: messageWarning,
  },
}))

vi.mock('@/api', () => ({
  aiLLMConfigApi: {
    list: configList,
    discoverModels,
    testConnection,
  },
}))

const passthrough = (name: string) => defineComponent({
  name,
  setup: (_props, { slots }) => () => h('div', slots.default?.()),
})

function mountPage() {
  return mount(AILLMConfigList, {
    global: {
      stubs: {
        AAlert: passthrough('AAlert'),
        AButton: passthrough('AButton'),
        ACard: passthrough('ACard'),
        AForm: passthrough('AForm'),
        AFormItem: passthrough('AFormItem'),
        AInput: passthrough('AInput'),
        AInputPassword: passthrough('AInputPassword'),
        AAutoComplete: passthrough('AAutoComplete'),
        AModal: passthrough('AModal'),
        APopconfirm: passthrough('APopconfirm'),
        ASelect: passthrough('ASelect'),
        ASelectOption: passthrough('ASelectOption'),
        ASpin: passthrough('ASpin'),
        ASwitch: passthrough('ASwitch'),
        ATable: passthrough('ATable'),
        ATextarea: passthrough('ATextarea'),
        ATag: passthrough('ATag'),
      },
    },
  })
}

describe('AILLMConfigList', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    configList.mockResolvedValue([])
    discoverModels.mockResolvedValue({
      provider: 'openai_compatible',
      endpoint: 'http://llm.example.test/v1',
      models: [{
        id: 'qwen2.5-vl',
        label: 'qwen2.5-vl',
        supports_vision: true,
        supports_reasoning: null,
        capability_source: 'model-name-hint',
        capabilities: ['vision'],
      }],
    })
    testConnection.mockResolvedValue({
      provider: 'ollama',
      model_name: 'qwen3',
      latency_ms: 42.5,
      response_received: true,
      message: '连接成功',
    })
  })

  it('offers a dedicated third-party compatible provider and requires its endpoint', async () => {
    const wrapper = mountPage()
    await Promise.resolve()
    const vm = wrapper.vm as any

    expect(vm.providerOptions).toContainEqual({
      label: 'system_pages.ai_llm.providers.openai_compatible',
      value: 'openai_compatible',
    })

    vm.resetForm()
    vm.form.provider = 'openai_compatible'
    vm.form.name = 'third-party'
    vm.form.model_name = 'qwen2.5-vl'
    vm.form.api_key = 'service-token'
    vm.form.endpoint = ''
    await vm.handleSave()

    expect(messageWarning).toHaveBeenCalledWith('system_pages.ai_llm.msg.compatible_endpoint_required')
    expect(discoverModels).not.toHaveBeenCalled()
    wrapper.unmount()
  })

  it('fetches models using the compatible provider selection', async () => {
    const wrapper = mountPage()
    const vm = wrapper.vm as any

    vm.resetForm()
    vm.form.provider = 'openai_compatible'
    vm.form.api_key = 'service-token'
    vm.form.endpoint = 'http://llm.example.test/v1'
    await vm.handleDiscoverModels()

    expect(discoverModels).toHaveBeenCalledWith({
      config_id: undefined,
      provider: 'openai_compatible',
      api_key: 'service-token',
      endpoint: 'http://llm.example.test/v1',
    })
    expect(vm.modelOptions).toHaveLength(1)
    expect(messageSuccess).toHaveBeenCalledWith('system_pages.ai_llm.msg.models_loaded:{"count":1}')
    wrapper.unmount()
  })

  it('tests an Ollama connection without requiring an API key', async () => {
    const wrapper = mountPage()
    const vm = wrapper.vm as any

    vm.resetForm()
    vm.form.provider = 'ollama'
    vm.form.model_name = 'qwen3'
    vm.form.endpoint = 'http://ollama.example.test:11434'
    await vm.handleTestConnection()

    expect(testConnection).toHaveBeenCalledWith({
      config_id: undefined,
      provider: 'ollama',
      api_key: undefined,
      endpoint: 'http://ollama.example.test:11434',
      model_name: 'qwen3',
      default_params: {},
    })
    expect(messageSuccess).toHaveBeenCalledWith(
      'system_pages.ai_llm.msg.connection_success:{"latency":42.5}',
    )
    wrapper.unmount()
  })

  it('provides thinking shortcuts without enabling reasoning by default', async () => {
    const wrapper = mountPage()
    const vm = wrapper.vm as any

    vm.resetForm()
    vm.defaultParamsText = '{"temperature":0.2,"thinking":true}'
    expect(vm.parseDefaultParams()).toEqual({ temperature: 0.2, thinking: true })

    vm.handleThinkingModeChange('reasoning_effort_medium')
    expect(JSON.parse(vm.defaultParamsText)).toEqual({
      temperature: 0.2,
      reasoning_effort: 'medium',
    })
    expect(vm.thinkingMode).toBe('reasoning_effort_medium')

    vm.handleThinkingModeChange('')
    expect(JSON.parse(vm.defaultParamsText)).toEqual({ temperature: 0.2 })
    wrapper.unmount()
  })

  it('shows model capability hints after model discovery', () => {
    const wrapper = mountPage()
    const vm = wrapper.vm as any

    vm.resetForm()
    vm.form.model_name = 'qwen3'
    vm.modelOptions = [{
      id: 'qwen3',
      label: 'qwen3',
      supports_vision: false,
      supports_reasoning: true,
      capability_source: 'model-name-hint',
      capabilities: ['reasoning'],
    }]

    expect(vm.reasoningCapabilityHint).toBe('system_pages.ai_llm.reasoning_supported')
    expect(vm.selectedModelOption.supports_reasoning).toBe(true)
    wrapper.unmount()
  })
})
