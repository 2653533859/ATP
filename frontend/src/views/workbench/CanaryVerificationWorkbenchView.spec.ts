import { describe, it, expect } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import CanaryVerificationWorkbenchView from './CanaryVerificationWorkbenchView.vue'

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
    template: '<div class="ant-table-stub"><slot /><div v-for="item in dataSource" :key="item.service_name" class="table-row">{{ item.service_name }} - {{ item.canary_version }}</div></div>',
    props: ['dataSource'],
  },
  'a-input-search': {
    template: '<input class="ant-search-stub" :value="value" @input="$emit(\'update:value\', $event.target.value)" />',
    props: ['value'],
  },
  'CanaryTopologyInspectionDrawer': {
    template: '<div class="topology-drawer-stub" :data-open="open"><slot /></div>',
    props: ['open'],
  },
  'CanarySteppingConfigModal': {
    template: '<div class="stepping-modal-stub" :data-open="open"><slot /></div>',
    props: ['open'],
  },
}

describe('CanaryVerificationWorkbenchView.vue', () => {
  it('renders page hero title and 4 Bento KPI cards', () => {
    const wrapper = mount(CanaryVerificationWorkbenchView, {
      global: { stubs },
    })

    expect(wrapper.find('.page-hero').exists()).toBe(true)
    expect(wrapper.text()).toContain('全链路金丝雀双轨流向透视与灰度控制工作台')
    expect(wrapper.text()).toContain('v6.1.0 全链路金丝雀在线')

    // 4 Bento cards
    const bentoCards = wrapper.findAll('.bento-card')
    expect(bentoCards.length).toBe(4)
    expect(wrapper.text()).toContain('运行中金丝雀微服务')
    expect(wrapper.text()).toContain('6 个')
    expect(wrapper.text()).toContain('五维健康度综合均分')
    expect(wrapper.text()).toContain('93.8 分')
    expect(wrapper.text()).toContain('累计自动熔断避险')
    expect(wrapper.text()).toContain('14 次')
    expect(wrapper.text()).toContain('影子存储隔离防污染率')
    expect(wrapper.text()).toContain('100.0%')
  })

  it('renders canary microservices table with seed data', () => {
    const wrapper = mount(CanaryVerificationWorkbenchView, {
      global: { stubs },
    })

    expect(wrapper.find('.table-container').exists()).toBe(true)
    expect(wrapper.text()).toContain('payment-service')
    expect(wrapper.text()).toContain('order-service')
    expect(wrapper.text()).toContain('user-service')
  })

  it('opens topology inspection drawer when clicking header button', async () => {
    const wrapper = mount(CanaryVerificationWorkbenchView, {
      global: { stubs },
    })

    const buttons = wrapper.findAll('.ant-btn-stub')
    const drawerBtn = buttons.find((b) => b.text().includes('全链路流向透视'))
    expect(drawerBtn).toBeDefined()
    await drawerBtn!.trigger('click')
    await flushPromises()

    const drawer = wrapper.find('.topology-drawer-stub')
    expect(drawer.attributes('data-open')).toBe('true')
  })

  it('opens stepping config modal when clicking header config button', async () => {
    const wrapper = mount(CanaryVerificationWorkbenchView, {
      global: { stubs },
    })

    const buttons = wrapper.findAll('.ant-btn-stub')
    const configBtn = buttons.find((b) => b.text().includes('灰度步进与围栏配置'))
    expect(configBtn).toBeDefined()
    await configBtn!.trigger('click')
    await flushPromises()

    const modal = wrapper.find('.stepping-modal-stub')
    expect(modal.attributes('data-open')).toBe('true')
  })
})
