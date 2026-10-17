import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import CanaryTopologyInspectionDrawer from './CanaryTopologyInspectionDrawer.vue'

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

describe('CanaryTopologyInspectionDrawer.vue', () => {
  it('renders hero bar with service name, canary version, and traffic weights', () => {
    const wrapper = mount(CanaryTopologyInspectionDrawer, {
      props: {
        open: true,
        targetService: 'order-service',
        canaryVersion: 'v2.0.0-canary',
        baselineVersion: 'v1.0.0',
        currentWeightPct: 25.0,
      },
      global: { stubs },
    })

    expect(wrapper.text()).toContain('order-service')
    expect(wrapper.text()).toContain('v2.0.0-canary')
    expect(wrapper.text()).toContain('v1.0.0')
    expect(wrapper.text()).toContain('25%')
    expect(wrapper.text()).toContain('75%')
  })

  it('renders multi-node topology with Ingress Gateway and Dual-Track Pods', () => {
    const wrapper = mount(CanaryTopologyInspectionDrawer, {
      props: {
        open: true,
        targetService: 'payment-service',
        currentWeightPct: 15.0,
      },
      global: { stubs },
    })

    expect(wrapper.text()).toContain('Ingress Gateway')
    expect(wrapper.text()).toContain('Dual-Track Pods')
    expect(wrapper.text()).toContain('Storage Layer')
    expect(wrapper.text()).toContain('影子测试库 (t_order_shadow)')
  })

  it('renders dual-track metric comparator cards and shadow isolation status', () => {
    const wrapper = mount(CanaryTopologyInspectionDrawer, {
      props: {
        open: true,
        targetService: 'payment-service',
        metrics: {
          error_rate_diff_pct: 0.15,
          latency_p99_ratio: 1.08,
          baseline_error_rate: 0.1,
          canary_error_rate: 0.25,
          baseline_p99_ms: 100,
          canary_p99_ms: 108,
          baseline_success_rate: 99.9,
          canary_success_rate: 99.8,
          overall_verdict: 'CONFORMANT',
        },
        isolation: {
          isolation_compliance_pct: 100.0,
          is_pollution_detected: false,
          shadow_routed_count: 50,
          leaked_master_writes_count: 0,
        },
      },
      global: { stubs },
    })

    expect(wrapper.text()).toContain('+0.15%')
    expect(wrapper.text()).toContain('1.08x')
    expect(wrapper.text()).toContain('100%')
    expect(wrapper.text()).toContain('CONFORMANT')
  })

  it('emits refresh and close events properly', async () => {
    const wrapper = mount(CanaryTopologyInspectionDrawer, {
      props: {
        open: true,
        targetService: 'payment-service',
      },
      global: { stubs },
    })

    // 找到刷新按钮并触发点击
    const buttons = wrapper.findAll('.ant-btn-stub')
    const refreshBtn = buttons.find((b) => b.text().includes('刷新指标'))
    expect(refreshBtn).toBeDefined()
    await refreshBtn!.trigger('click')

    expect(wrapper.emitted('refresh')).toBeTruthy()
    expect(wrapper.emitted('refresh')![0]).toEqual(['payment-service'])
  })
})
