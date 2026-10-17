import { describe, it, expect } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import ChaosExperimentInspectionDrawer from './ChaosExperimentInspectionDrawer.vue'

const stubs = {
  'a-drawer': { template: '<div class="ant-drawer-stub"><slot /></div>' },
  'a-card': { template: '<div class="ant-card-stub"><slot /><slot name="extra" /></div>' },
  'a-button': { template: '<button class="ant-btn-stub" @click="$emit(\'click\')"><slot /></button>' },
  'a-tag': { template: '<span class="ant-tag-stub"><slot /></span>' },
  'a-space': { template: '<div class="ant-space-stub"><slot /></div>' },
  'a-table': {
    template: '<div class="ant-table-stub"><slot /><div v-for="item in dataSource" :key="item.rule_id" class="table-row">{{ item.target_service }}</div></div>',
    props: ['dataSource'],
  },
  'a-row': { template: '<div class="ant-row-stub"><slot /></div>' },
  'a-col': { template: '<div class="ant-col-stub"><slot /></div>' },
  'a-switch': { template: '<input type="checkbox" class="ant-switch-stub" />' },
  'a-divider': { template: '<hr />' },
}

describe('ChaosExperimentInspectionDrawer.vue', () => {
  const sampleExperiment = {
    experiment_id: 'exp_payment_circuit_breaker',
    name: '支付微服务熔断演练',
    target_service: 'payment-service',
    state: 'FAULT_INJECTING',
    baseline_hypothesis: {
      max_p99_latency_ms: 250.0,
      min_success_rate_pct: 99.0,
      health_probe_endpoint: '/health/ready',
    },
    rto_seconds: 3.8,
  }

  const sampleRules = [
    {
      rule_id: 'rule_1',
      fault_type: 'NETWORK_LATENCY',
      target_service: 'payment-service',
      target_pattern: '/api/v1/payment/*',
      config: { latency_ms: 400, jitter_ms: 50 },
      is_enabled: true,
    },
  ]

  it('renders drawer header, experiment metadata, and hero metrics correctly', () => {
    const wrapper = mount(ChaosExperimentInspectionDrawer, {
      props: {
        open: true,
        experiment: sampleExperiment,
        rules: sampleRules,
      },
      global: { stubs },
    })

    expect(wrapper.find('.chaos-hero-bar').exists()).toBe(true)
    expect(wrapper.text()).toContain('exp_payment_circuit_breaker')
    expect(wrapper.text()).toContain('payment-service')
    expect(wrapper.text()).toContain('P99 延迟:')
    expect(wrapper.text()).toContain('降级接管率:')
  })

  it('renders topology canvas and nodes', () => {
    const wrapper = mount(ChaosExperimentInspectionDrawer, {
      props: {
        open: true,
        experiment: sampleExperiment,
      },
      global: { stubs },
    })

    expect(wrapper.find('.topology-canvas').exists()).toBe(true)
    expect(wrapper.text()).toContain('api-gateway')
    expect(wrapper.text()).toContain('redis-cache / 旁路')
  })

  it('emits emergencyAbort event when abort button is clicked', async () => {
    const wrapper = mount(ChaosExperimentInspectionDrawer, {
      props: {
        open: true,
        experiment: sampleExperiment,
      },
      global: { stubs },
    })

    const abortBtn = wrapper.find('.abort-btn')
    expect(abortBtn.exists()).toBe(true)
    await abortBtn.trigger('click')
    await flushPromises()

    expect(wrapper.emitted('emergencyAbort')).toBeTruthy()
    expect(wrapper.emitted('emergencyAbort')![0]).toEqual(['exp_payment_circuit_breaker'])
  })

  it('emits close event when close button is clicked', async () => {
    const wrapper = mount(ChaosExperimentInspectionDrawer, {
      props: {
        open: true,
      },
      global: { stubs },
    })

    const buttons = wrapper.findAll('.ant-btn-stub')
    const closeBtn = buttons.find(b => b.text().includes('关闭'))
    expect(closeBtn).toBeDefined()
    await closeBtn!.trigger('click')

    expect(wrapper.emitted('close')).toBeTruthy()
  })
})
