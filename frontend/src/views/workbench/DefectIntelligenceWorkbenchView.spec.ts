import { describe, it, expect } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import DefectIntelligenceWorkbenchView from './DefectIntelligenceWorkbenchView.vue'

const stubs = {
  'a-button': {
    template: '<button class="ant-btn-stub" @click="$emit(\'click\')"><slot /></button>',
  },
  'a-tag': { template: '<span class="ant-tag-stub"><slot /></span>' },
  'a-space': { template: '<div class="ant-space-stub"><slot /></div>' },
  'a-card': { template: '<div class="ant-card-stub"><slot /><slot name="extra" /></div>' },
  'a-table': {
    template: '<div class="ant-table-stub"><slot /><div v-for="item in dataSource" :key="item.cluster_id" class="table-row">{{ item.cluster_id }} - {{ item.master_title }}</div></div>',
    props: ['dataSource'],
  },
  'a-input-search': {
    template: '<input class="ant-search-stub" :value="value" @input="$emit(\'update:value\', $event.target.value)" />',
    props: ['value'],
  },
  'DefectClusterInspectionDrawer': {
    template: '<div class="inspection-drawer-stub" :data-open="open"><slot /></div>',
    props: ['open', 'cluster'],
  },
  'DefectSyncConfigModal': {
    template: '<div class="sync-modal-stub" :data-open="open"><slot /></div>',
    props: ['open'],
  },
}

describe('DefectIntelligenceWorkbenchView.vue', () => {
  it('renders page hero title and 4 Bento KPI cards', () => {
    const wrapper = mount(DefectIntelligenceWorkbenchView, {
      global: { stubs },
    })

    expect(wrapper.find('.page-hero').exists()).toBe(true)
    expect(wrapper.text()).toContain('智能缺陷聚类去重与全生命周期治理中枢')
    expect(wrapper.text()).toContain('v6.0.0 智能缺陷聚类在线')

    // 4 Bento cards
    const bentoCards = wrapper.findAll('.bento-card')
    expect(bentoCards.length).toBe(4)
    expect(wrapper.text()).toContain('失败用例去重收敛率')
    expect(wrapper.text()).toContain('91.5%')
    expect(wrapper.text()).toContain('当前活跃 Master 主缺陷')
    expect(wrapper.text()).toContain('8 起')
    expect(wrapper.text()).toContain('缺陷解决 SLA 履约率')
    expect(wrapper.text()).toContain('96.2%')
    expect(wrapper.text()).toContain('跨平台双向同步健康度')
    expect(wrapper.text()).toContain('100%')
  })

  it('renders clusters table with seed master defect clusters', () => {
    const wrapper = mount(DefectIntelligenceWorkbenchView, {
      global: { stubs },
    })

    expect(wrapper.find('.clusters-table-card').exists()).toBe(true)
    expect(wrapper.text()).toContain('cl_master_01')
    expect(wrapper.text()).toContain('payment-service')
    expect(wrapper.text()).toContain('cl_master_02')
  })

  it('opens inspection drawer when clicking header inspection button', async () => {
    const wrapper = mount(DefectIntelligenceWorkbenchView, {
      global: { stubs },
    })

    const buttons = wrapper.findAll('.ant-btn-stub')
    const inspectBtn = buttons.find((b) => b.text().includes('堆栈指纹拓扑透视'))
    expect(inspectBtn).toBeDefined()
    await inspectBtn!.trigger('click')
    await flushPromises()

    const drawer = wrapper.find('.inspection-drawer-stub')
    expect(drawer.attributes('data-open')).toBe('true')
  })

  it('opens sync config modal when clicking header config button', async () => {
    const wrapper = mount(DefectIntelligenceWorkbenchView, {
      global: { stubs },
    })

    const buttons = wrapper.findAll('.ant-btn-stub')
    const configBtn = buttons.find((b) => b.text().includes('跨平台与 SLA 策略'))
    expect(configBtn).toBeDefined()
    await configBtn!.trigger('click')
    await flushPromises()

    const modal = wrapper.find('.sync-modal-stub')
    expect(modal.attributes('data-open')).toBe('true')
  })
})
