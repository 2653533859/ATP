import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import BlastRadiusTopologyGraph from './BlastRadiusTopologyGraph.vue'

const mockTopology = {
  services: ['api-gateway', 'order-service', 'pay-service', 'billing-core', 'user-auth'],
  dependencies: [
    { caller: 'api-gateway', callee: 'order-service' },
    { caller: 'order-service', callee: 'pay-service' },
    { caller: 'pay-service', callee: 'billing-core' },
  ],
}

const mockEvaluateSafe = {
  injected_service: 'pay-service',
  direct_services: ['order-service'],
  cascading_services: ['api-gateway'],
  all_impacted_services: ['pay-service', 'order-service', 'api-gateway'],
  total_impacted_count: 3,
  max_depth_reached: 2,
  breached: false,
  breach_reasons: [],
  emergency_aborted: false,
}

const mockEvaluateBreached = {
  injected_service: 'billing-core',
  direct_services: ['pay-service'],
  cascading_services: ['order-service', 'api-gateway'],
  all_impacted_services: ['billing-core', 'pay-service', 'order-service', 'api-gateway'],
  total_impacted_count: 4,
  max_depth_reached: 3,
  breached: true,
  breach_reasons: [
    '受波及微服务总数 (4) 超过上限 (3)',
    '级联传导深度 (3) 超过上限 (2)',
    '触碰核心受保护服务黑名单: billing-core',
  ],
  emergency_aborted: true,
}

const mockGetTopology = vi.fn().mockResolvedValue(mockTopology)
const mockEvaluateBlastRadius = vi.fn().mockResolvedValue(mockEvaluateSafe)
const mockEnforceBlastRadius = vi.fn().mockResolvedValue(mockEvaluateBreached)

vi.mock('@/api/meshChaos', () => ({
  meshChaosApi: {
    getTopology: () => mockGetTopology(),
    evaluateBlastRadius: (data: unknown) => mockEvaluateBlastRadius(data),
    enforceBlastRadius: (data: unknown) => mockEnforceBlastRadius(data),
    listExperiments: vi.fn(),
    createExperiment: vi.fn(),
    getExperiment: vi.fn(),
    setExperimentStatus: vi.fn(),
    evaluateMeshRequest: vi.fn(),
  },
}))
vi.mock('vue-echarts', () => ({
  default: { name: 'VChart', template: '<div class="echarts-stub" />' },
}))


const globalStubs = {
  'a-card': { template: '<div class="ant-card"><h4>{{ $attrs.title }}</h4><slot /><slot name="extra" /></div>' },
  'a-button': { template: '<button class="ant-btn"><slot /></button>' },
  'a-tag': { template: '<span class="ant-tag"><slot /></span>' },
  'a-space': { template: '<div><slot /></div>' },
  'a-form': { template: '<form><slot /></form>' },
  'a-form-item': { template: '<div class="form-item"><slot /></div>' },
  'a-row': { template: '<div class="ant-row"><slot /></div>' },
  'a-col': { template: '<div class="ant-col"><slot /></div>' },
  'a-select': { template: '<select><slot /></select>' },
  'a-select-option': { template: '<option><slot /></option>' },
  'a-input-number': { template: '<input type="number" />' },
  'a-alert': { template: '<div class="ant-alert"><h5>{{ $attrs.message }}</h5><p>{{ $attrs.description }}</p></div>' },
  VChart: { template: '<div class="v-chart" />' },
}

describe('BlastRadiusTopologyGraph.vue', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('loads topology on mount and renders header controls and metrics', async () => {
    const wrapper = mount(BlastRadiusTopologyGraph, {
      global: {
        stubs: globalStubs,
      },
    })
    await flushPromises()

    expect(mockGetTopology).toHaveBeenCalled()
    expect(wrapper.text()).toContain('微服务调用依赖拓扑与混沌爆炸半径控制')
    expect(wrapper.text()).toContain('评估爆炸半径')
    expect(wrapper.text()).toContain('安全管控强校验')
    expect(wrapper.text()).toContain('已注册微服务')
    expect(wrapper.text()).toContain('5') // 5 services from mockTopology
    expect(wrapper.text()).toContain('pay-service')
  })

  it('evaluates blast radius upon clicking evaluate button', async () => {
    const wrapper = mount(BlastRadiusTopologyGraph, {
      global: {
        stubs: globalStubs,
      },
    })
    await flushPromises()

    const evalBtn = wrapper.findAll('button').find((b) => b.text().includes('评估爆炸半径'))
    expect(evalBtn).toBeDefined()
    await evalBtn!.trigger('click')
    await flushPromises()

    expect(mockEvaluateBlastRadius).toHaveBeenCalledWith({
      injected_service: 'pay-service',
      max_impacted_services: 3,
      max_depth: 2,
      protected_services: ['user-auth', 'billing-core'],
    })

    expect(wrapper.text()).toContain('爆炸半径安全受控')
    expect(wrapper.text()).toContain('order-service')
    expect(wrapper.text()).toContain('api-gateway')
  })

  it('triggers emergency abort alert when safety boundary is breached', async () => {
    const wrapper = mount(BlastRadiusTopologyGraph, {
      global: {
        stubs: globalStubs,
      },
    })
    await flushPromises()

    const enforceBtn = wrapper.findAll('button').find((b) => b.text().includes('安全管控强校验'))
    expect(enforceBtn).toBeDefined()
    await enforceBtn!.trigger('click')
    await flushPromises()

    expect(mockEnforceBlastRadius).toHaveBeenCalled()
    expect(wrapper.text()).toContain('EMERGENCY ABORT 紧急熔断已触发')
    expect(wrapper.text()).toContain('触碰核心受保护服务黑名单: billing-core')
  })
})
