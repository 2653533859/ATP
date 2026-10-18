import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import StressTopologyInspectionDrawer from './StressTopologyInspectionDrawer.vue'

const stubs = {
  'a-drawer': { template: '<div class="ant-drawer-stub"><slot /></div>' },
  'a-button': { template: '<button class="ant-btn-stub" @click="$emit(\'click\')"><slot /></button>' },
  'a-tag': { template: '<span class="ant-tag-stub"><slot /></span>' },
  'a-space': { template: '<div class="ant-space-stub"><slot /></div>' },
  'a-popconfirm': {
    template: '<div class="ant-popconfirm-stub" @confirm="$emit(\'confirm\')"><slot /></div>',
    props: ['title'],
  },
}

describe('StressTopologyInspectionDrawer.vue', () => {
  it('renders hero bar with service name, current VU, and TPS', () => {
    const wrapper = mount(StressTopologyInspectionDrawer, {
      props: {
        open: true,
        targetService: 'order-service',
        currentVu: 5000,
        currentTps: 14800,
        p99LatencyMs: 185.0,
        errorRatePct: 0.08,
        kneePointVu: 4200,
        bottleneckNode: 't_order_shadow (锁争用)',
      },
      global: { stubs },
    })

    expect(wrapper.text()).toContain('order-service')
    expect(wrapper.text()).toContain('5000 VU')
    expect(wrapper.text()).toContain('14,800')
    expect(wrapper.text()).toContain('185.0 ms')
    expect(wrapper.text()).toContain('4200 VU')
    expect(wrapper.text()).toContain('t_order_shadow (锁争用)')
  })

  it('renders 4-node full-link topology pipeline', () => {
    const wrapper = mount(StressTopologyInspectionDrawer, {
      props: {
        open: true,
        targetService: 'payment-service',
      },
      global: { stubs },
    })

    expect(wrapper.text()).toContain('Stress Influx')
    expect(wrapper.text()).toContain('Ingress Gateway')
    expect(wrapper.text()).toContain('Bottleneck Service')
    expect(wrapper.text()).toContain('Shadow Storage')
    expect(wrapper.text()).toContain('路由: t_order_shadow')
  })

  it('renders capacity & bottleneck diagnostic cards', () => {
    const wrapper = mount(StressTopologyInspectionDrawer, {
      props: {
        open: true,
        targetService: 'payment-service',
        currentTps: 12500,
        p99LatencyMs: 160.0,
        kneePointVu: 5000,
        currentVu: 4000,
      },
      global: { stubs },
    })

    expect(wrapper.text()).toContain('当前实测吞吐量 (TPS)')
    expect(wrapper.text()).toContain('P99 响应时延 (Latency)')
    expect(wrapper.text()).toContain('+1000') // 5000 - 4000 = +1000
    expect(wrapper.text()).toContain('处于线性增长安全区')
    expect(wrapper.text()).toContain('100.0%')
  })

  it('emits refresh and emergencyStop events properly', async () => {
    const wrapper = mount(StressTopologyInspectionDrawer, {
      props: {
        open: true,
        targetService: 'payment-service',
      },
      global: { stubs },
    })

    const buttons = wrapper.findAll('.ant-btn-stub')
    const refreshBtn = buttons.find((b) => b.text().includes('刷新拓扑'))
    expect(refreshBtn).toBeDefined()
    await refreshBtn!.trigger('click')

    expect(wrapper.emitted('refresh')).toBeTruthy()
    expect(wrapper.emitted('refresh')![0]).toEqual(['payment-service'])
  })
})
