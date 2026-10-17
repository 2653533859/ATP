import { describe, it, expect } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import ChaosEngineeringWorkbenchView from './ChaosEngineeringWorkbenchView.vue'

const stubs = {
  'a-button': {
    template: '<button class="ant-btn-stub" @click="$emit(\'click\')"><slot /></button>',
  },
  'a-tag': { template: '<span class="ant-tag-stub"><slot /></span>' },
  'a-space': { template: '<div class="ant-space-stub"><slot /></div>' },
  'a-card': { template: '<div class="ant-card-stub"><slot /><slot name="extra" /></div>' },
  'a-table': {
    template: '<div class="ant-table-stub"><slot /><div v-for="item in dataSource" :key="item.experiment_id" class="table-row">{{ item.experiment_id }} - {{ item.name }}</div></div>',
    props: ['dataSource'],
  },
  'a-input-search': {
    template: '<input class="ant-search-stub" :value="value" @input="$emit(\'update:value\', $event.target.value)" />',
    props: ['value'],
  },
  'ChaosExperimentInspectionDrawer': {
    template: '<div class="inspection-drawer-stub" :data-open="open"><slot /></div>',
    props: ['open', 'experiment'],
  },
  'BlastRadiusConfigModal': {
    template: '<div class="config-modal-stub" :data-open="open"><slot /></div>',
    props: ['open', 'experimentId'],
  },
}

describe('ChaosEngineeringWorkbenchView.vue', () => {
  it('renders workbench page hero, title, and 4 Bento KPI cards', () => {
    const wrapper = mount(ChaosEngineeringWorkbenchView, {
      global: { stubs },
    })

    expect(wrapper.find('.page-hero').exists()).toBe(true)
    expect(wrapper.text()).toContain('分布式混沌工程与微服务弹性韧性演练工作台中枢')
    expect(wrapper.text()).toContain('v5.8.0 混沌攻防引擎在线')

    // 4 Bento KPI cards
    const bentoCards = wrapper.findAll('.bento-card')
    expect(bentoCards.length).toBe(4)
    expect(wrapper.text()).toContain('演练稳态守住率')
    expect(wrapper.text()).toContain('95.8%')
    expect(wrapper.text()).toContain('平均自愈恢复时间 (RTO)')
    expect(wrapper.text()).toContain('3.4s')
    expect(wrapper.text()).toContain('看门狗紧急熔断拦截')
    expect(wrapper.text()).toContain('14 次')
    expect(wrapper.text()).toContain('架构韧性雷达综合得分')
    expect(wrapper.text()).toContain('91.2 分')
  })

  it('renders active chaos experiments table with seed data', () => {
    const wrapper = mount(ChaosEngineeringWorkbenchView, {
      global: { stubs },
    })

    expect(wrapper.find('.experiments-table-card').exists()).toBe(true)
    expect(wrapper.text()).toContain('exp_payment_circuit_breaker')
    expect(wrapper.text()).toContain('核心支付网关高延迟与网络丢包弹性韧性演练')
    expect(wrapper.text()).toContain('exp_order_db_timeout')
  })

  it('opens inspection drawer when clicking header button or table link', async () => {
    const wrapper = mount(ChaosEngineeringWorkbenchView, {
      global: { stubs },
    })

    const buttons = wrapper.findAll('.ant-btn-stub')
    const inspectBtn = buttons.find((b) => b.text().includes('故障注入拓扑透视'))
    expect(inspectBtn).toBeDefined()
    await inspectBtn!.trigger('click')
    await flushPromises()

    const drawer = wrapper.find('.inspection-drawer-stub')
    expect(drawer.attributes('data-open')).toBe('true')
  })

  it('opens blast radius config modal when clicking header config button', async () => {
    const wrapper = mount(ChaosEngineeringWorkbenchView, {
      global: { stubs },
    })

    const buttons = wrapper.findAll('.ant-btn-stub')
    const configBtn = buttons.find((b) => b.text().includes('安全围栏与看门狗配置'))
    expect(configBtn).toBeDefined()
    await configBtn!.trigger('click')
    await flushPromises()

    const modal = wrapper.find('.config-modal-stub')
    expect(modal.attributes('data-open')).toBe('true')
  })
})
