import { describe, it, expect } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import StressTestingWorkbenchView from './StressTestingWorkbenchView.vue'

const stubs = {
  'a-button': {
    template: '<button class="ant-btn-stub" @click="$emit(\'click\')"><slot /></button>',
  },
  'a-tag': { template: '<span class="ant-tag-stub"><slot /></span>' },
  'a-space': { template: '<div class="ant-space-stub"><slot /></div>' },
  'a-progress': { template: '<div class="ant-progress-stub" :data-percent="percent" />', props: ['percent'] },
  'a-popconfirm': {
    template: '<div class="ant-popconfirm-stub" @confirm="$emit(\'confirm\')"><slot /></div>',
    props: ['title'],
  },
  'a-table': {
    template: '<div class="ant-table-stub"><slot /><div v-for="item in dataSource" :key="item.service_name" class="table-row">{{ item.service_name }} - {{ item.profile_type }}</div></div>',
    props: ['dataSource'],
  },
  'a-input-search': {
    template: '<input class="ant-search-stub" :value="value" @input="$emit(\'update:value\', $event.target.value)" />',
    props: ['value'],
  },
  'StressTopologyInspectionDrawer': {
    template: '<div class="topology-drawer-stub" :data-open="open"><slot /></div>',
    props: ['open'],
  },
  'StressConfigModal': {
    template: '<div class="stress-modal-stub" :data-open="open"><slot /></div>',
    props: ['open'],
  },
}

describe('StressTestingWorkbenchView.vue', () => {
  it('renders page hero title and 4 Bento KPI cards', () => {
    const wrapper = mount(StressTestingWorkbenchView, {
      global: { stubs },
    })

    expect(wrapper.find('.page-hero').exists()).toBe(true)
    expect(wrapper.text()).toContain('全链路生产影子压测与架构容量基线中枢')
    expect(wrapper.text()).toContain('v6.2.0 生产全链路压测在线')

    // 4 Bento cards
    const bentoCards = wrapper.findAll('.bento-card')
    expect(bentoCards.length).toBe(4)
    expect(wrapper.text()).toContain('生产当前实测峰值吞吐')
    expect(wrapper.text()).toContain('16,500')
    expect(wrapper.text()).toContain('架构容量饱和度 (USL)')
    expect(wrapper.text()).toContain('82.5%')
    expect(wrapper.text()).toContain('识别架构性能瓶颈节点')
    expect(wrapper.text()).toContain('1 个')
    expect(wrapper.text()).toContain('累计过载紧急熔断泄压')
    expect(wrapper.text()).toContain('6 次')
  })

  it('renders microservices stress testing table with seed data', () => {
    const wrapper = mount(StressTestingWorkbenchView, {
      global: { stubs },
    })

    expect(wrapper.find('.table-container').exists()).toBe(true)
    expect(wrapper.text()).toContain('payment-service')
    expect(wrapper.text()).toContain('order-service')
    expect(wrapper.text()).toContain('cart-service')
    expect(wrapper.text()).toContain('inventory-service')
  })

  it('opens topology inspection drawer when clicking header button', async () => {
    const wrapper = mount(StressTestingWorkbenchView, {
      global: { stubs },
    })

    const buttons = wrapper.findAll('.ant-btn-stub')
    const drawerBtn = buttons.find((b) => b.text().includes('发压链路透视'))
    expect(drawerBtn).toBeDefined()
    await drawerBtn!.trigger('click')
    await flushPromises()

    const drawer = wrapper.find('.topology-drawer-stub')
    expect(drawer.attributes('data-open')).toBe('true')
  })

  it('opens config modal when clicking header config button', async () => {
    const wrapper = mount(StressTestingWorkbenchView, {
      global: { stubs },
    })

    const buttons = wrapper.findAll('.ant-btn-stub')
    const configBtn = buttons.find((b) => b.text().includes('发压策略与围栏'))
    expect(configBtn).toBeDefined()
    await configBtn!.trigger('click')
    await flushPromises()

    const modal = wrapper.find('.stress-modal-stub')
    expect(modal.attributes('data-open')).toBe('true')
  })
})
