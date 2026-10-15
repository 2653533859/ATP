import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import MeshChaosRuleCard from './MeshChaosRuleCard.vue'

const mockCreatedExperiment = {
  experiment_id: 'exp_mesh_test_881',
  name: '微服务核心链路网关混沌故障实验',
  description: '由微服务网关混沌规则卡片创建下发',
  status: 'active',
  created_at: '2026-10-16T10:00:00Z',
  rules: [
    {
      service_name: 'order-service',
      route_pattern: '^/api/v1/orders.*',
      action: 'service_down_503',
      traffic_ratio: 1.0,
      methods: ['*'],
      header_matchers: { 'x-canary': 'true' },
      enabled: true,
    },
  ],
}

const mockEvaluateDecision = {
  inject_fault: true,
  action: 'service_down_503',
  status_code: 503,
  response_body: {
    error: 'Service Unavailable',
    chaos_injected: true,
  },
}

const mockCreateExperiment = vi.fn().mockResolvedValue(mockCreatedExperiment)
const mockEvaluateMeshRequest = vi.fn().mockResolvedValue(mockEvaluateDecision)

vi.mock('@/api/meshChaos', () => ({
  meshChaosApi: {
    createExperiment: (data: unknown) => mockCreateExperiment(data),
    evaluateMeshRequest: (data: unknown) => mockEvaluateMeshRequest(data),
    listExperiments: vi.fn(),
    getExperiment: vi.fn(),
    setExperimentStatus: vi.fn(),
  },
}))

const globalStubs = {
  'a-card': { template: '<div class="ant-card"><slot name="title" /><slot /><slot name="extra" /></div>' },
  'a-button': { template: '<button class="ant-btn"><slot /></button>' },
  'a-tag': { template: '<span class="ant-tag"><slot /></span>' },
  'a-switch': true,
  'a-space': { template: '<div><slot /></div>' },
  'a-form': { template: '<form><slot /></form>' },
  'a-form-item': { template: '<div class="form-item"><slot /></div>' },
  'a-row': { template: '<div class="ant-row"><slot /></div>' },
  'a-col': { template: '<div class="ant-col"><slot /></div>' },
  'a-input': { template: '<input />' },
  'a-radio-group': { template: '<div class="ant-radio-group"><slot /></div>' },
  'a-radio-button': { template: '<button class="ant-radio-btn"><slot /></button>' },
  'a-slider': true,
}

describe('MeshChaosRuleCard.vue', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders rule card header, 4 chaos action options, and inputs', () => {
    const wrapper = mount(MeshChaosRuleCard, {
      global: {
        stubs: globalStubs,
      },
    })

    expect(wrapper.text()).toContain('微服务网关混沌故障注入规则编排卡片')
    expect(wrapper.text()).toContain('503 实例宕机 (Service Down)')
    expect(wrapper.text()).toContain('连接断路熔断 (Trip Breaker)')
    expect(wrapper.text()).toContain('网络延迟抖动 (Latency Jitter)')
    expect(wrapper.text()).toContain('报文畸形损坏 (Corrupt Payload)')
    expect(wrapper.text()).toContain('保存并下发实验')
  })

  it('evaluates mesh request upon clicking test button', async () => {
    const wrapper = mount(MeshChaosRuleCard, {
      global: {
        stubs: globalStubs,
      },
    })

    const evalBtn = wrapper.findAll('button').find((b) => b.text().includes('发送试探评估请求'))
    expect(evalBtn).toBeDefined()
    await evalBtn!.trigger('click')
    await flushPromises()

    expect(mockEvaluateMeshRequest).toHaveBeenCalledWith({
      service_name: 'order-service',
      path: '/api/v1/orders/checkout',
      method: 'POST',
      headers: { 'x-canary': 'true' },
    })

    expect(wrapper.text()).toContain('命中故障注入: service_down_503')
    expect(wrapper.text()).toContain('503')
  })

  it('creates and deploys chaos experiment upon clicking save button', async () => {
    const wrapper = mount(MeshChaosRuleCard, {
      global: {
        stubs: globalStubs,
      },
    })

    const saveBtn = wrapper.findAll('button').find((b) => b.text().includes('保存并下发实验'))
    expect(saveBtn).toBeDefined()
    await saveBtn!.trigger('click')
    await flushPromises()

    expect(mockCreateExperiment).toHaveBeenCalledWith({
      name: '微服务核心链路网关混沌故障实验',
      description: '由微服务网关混沌规则卡片创建下发',
      rules: [
        expect.objectContaining({
          service_name: 'order-service',
          action: 'service_down_503',
          traffic_ratio: 1.0,
        }),
      ],
    })

    expect(wrapper.emitted('saved')).toBeTruthy()
  })
})
