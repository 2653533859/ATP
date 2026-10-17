import { describe, it, expect } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import DefectClusterInspectionDrawer from './DefectClusterInspectionDrawer.vue'

const stubs = {
  'a-drawer': { template: '<div class="ant-drawer-stub"><slot /></div>' },
  'a-modal': { template: '<div class="ant-modal-stub"><slot /></div>' },
  'a-button': { template: '<button class="ant-btn-stub" @click="$emit(\'click\')"><slot /></button>' },
  'a-tag': { template: '<span class="ant-tag-stub"><slot /></span>' },
  'a-space': { template: '<div class="ant-space-stub"><slot /></div>' },
  'a-card': { template: '<div class="ant-card-stub"><slot /><slot name="extra" /></div>' },
  'a-row': { template: '<div class="ant-row-stub"><slot /></div>' },
  'a-col': { template: '<div class="ant-col-stub"><slot /></div>' },
  'a-form': { template: '<form class="ant-form-stub"><slot /></form>' },
  'a-form-item': { template: '<div class="ant-form-item-stub"><slot /></div>' },
  'a-input': {
    template: '<input class="ant-input-stub" :value="value" @input="$emit(\'update:value\', $event.target.value)" />',
    props: ['value'],
  },
  'a-table': {
    template: '<div class="ant-table-stub"><slot /><div v-for="item in dataSource" :key="item.case_id" class="table-row">{{ item.case_id }} - {{ item.case_name }}</div></div>',
    props: ['dataSource'],
  },
}

describe('DefectClusterInspectionDrawer.vue', () => {
  const sampleCluster = {
    cluster_id: 'cl_test_01',
    primary_fingerprint: 'fp_hash_11223344556677889900aabbccddeeff11223344556677889900aabbccddeeff',
    master_title: '[payment-service] DatabaseConnectionTimeout in payment.py',
    exception_type: 'DatabaseConnectionTimeout',
    target_service: 'payment-service',
    root_cause_file: '/app/services/payment.py',
    total_failures_count: 5,
    linked_case_ids: ['case_01', 'case_02'],
    associated_case_names: ['用例1', '用例2'],
    sanitized_stack_trace: 'Traceback:\n  DatabaseConnectionTimeout at <HOST:PORT>',
    responsible_team: '资金结算组',
    suggested_assignee: '李强',
  }

  it('renders drawer hero bar, master title, exception type, and 64-bit fingerprint', () => {
    const wrapper = mount(DefectClusterInspectionDrawer, {
      props: {
        open: true,
        cluster: sampleCluster,
      },
      global: { stubs },
    })

    expect(wrapper.find('.defect-hero-bar').exists()).toBe(true)
    expect(wrapper.text()).toContain('DatabaseConnectionTimeout')
    expect(wrapper.text()).toContain('payment-service')
    expect(wrapper.text()).toContain('fp_hash_11223344556677889900aabbccddeeff11223344556677889900aabbccddeeff')
    expect(wrapper.text()).toContain('资金结算组')
    expect(wrapper.text()).toContain('李强')
  })

  it('renders linked cases table and sanitized stack trace', () => {
    const wrapper = mount(DefectClusterInspectionDrawer, {
      props: {
        open: true,
        cluster: sampleCluster,
      },
      global: { stubs },
    })

    expect(wrapper.find('.linked-cases-card').exists()).toBe(true)
    expect(wrapper.text()).toContain('case_01')
    expect(wrapper.text()).toContain('用例1')
    expect(wrapper.find('.sanitized-stack-pre').exists()).toBe(true)
    expect(wrapper.text()).toContain('<HOST:PORT>')
  })

  it('opens merge modal when clicking merge button', async () => {
    const wrapper = mount(DefectClusterInspectionDrawer, {
      props: {
        open: true,
        cluster: sampleCluster,
      },
      global: { stubs },
    })

    const buttons = wrapper.findAll('.ant-btn-stub')
    const mergeBtn = buttons.find(b => b.text().includes('合并至外部工单'))
    expect(mergeBtn).toBeDefined()
    await mergeBtn!.trigger('click')
    await flushPromises()

    expect(wrapper.find('.ant-modal-stub').exists()).toBe(true)
  })

  it('emits close event when close button is clicked', async () => {
    const wrapper = mount(DefectClusterInspectionDrawer, {
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
