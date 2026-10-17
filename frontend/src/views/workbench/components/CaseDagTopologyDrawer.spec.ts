import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import CaseDagTopologyDrawer from './CaseDagTopologyDrawer.vue'

const stubs = {
  'a-drawer': { template: '<div class="ant-drawer-stub"><slot /></div>' },
  'a-button': { template: '<button><slot /></button>' },
  'a-tag': { template: '<span class="ant-tag-stub"><slot /></span>' },
  'a-space': { template: '<div class="ant-space-stub"><slot /></div>' },
  'a-table': { template: '<div class="ant-table-stub"><slot /></div>' },
}

describe('CaseDagTopologyDrawer.vue', () => {
  const sampleDag = {
    dag_id: 'dag_checkout_test',
    is_valid_dag: true,
    nodes_count: 3,
    edges_count: 2,
    cycles: [],
    nodes: {
      case_login: { case_name: '用户登录', produced_variables: ['auth_token'] },
      case_order: { case_name: '创建订单', produced_variables: ['order_id'] },
      case_pay: { case_name: '支付订单', produced_variables: ['receipt'] },
    },
  }

  const sampleWavePlan = {
    critical_path_duration_seconds: 37.0,
    sequential_duration_seconds: 45.0,
    concurrency_acceleration_ratio: 2.5,
    waves: [
      {
        wave_index: 0,
        concurrency_level: 1,
        wave_estimated_duration_seconds: 10.0,
        is_terminal: false,
        nodes: [{ case_id: 'case_login', case_name: '用户登录', required_variables: [], produced_variables: ['auth_token'] }],
      },
      {
        wave_index: 1,
        concurrency_level: 1,
        wave_estimated_duration_seconds: 15.0,
        is_terminal: true,
        nodes: [{ case_id: 'case_order', case_name: '创建订单', required_variables: ['auth_token'], produced_variables: ['order_id'] }],
      },
    ],
  }

  const sampleFaultReport = {
    node_records: [
      { case_id: 'case_login', status: 'FAILED', error_message: 'Auth 401' },
      { case_id: 'case_order', status: 'CASCADE_SKIPPED', cascade_skip_reason: '前置登录失败' },
    ],
  }

  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders drawer with DAG metrics, acceleration, and wave nodes', async () => {
    const wrapper = mount(CaseDagTopologyDrawer, {
      props: {
        open: true,
        dagData: sampleDag,
        wavePlan: sampleWavePlan,
        faultReport: sampleFaultReport,
      },
      global: { stubs },
    })
    await flushPromises()

    expect(wrapper.text()).toContain('2.5x')
    expect(wrapper.text()).toContain('dag_checkout_test')
    expect(wrapper.text()).toContain('DAG 有向无环 · 无死锁')
    expect(wrapper.text()).toContain('用户登录')
    expect(wrapper.text()).toContain('前置登录失败')
  })

  it('handles dispatch all waves click', async () => {
    const wrapper = mount(CaseDagTopologyDrawer, {
      props: {
        open: true,
        dagData: sampleDag,
        wavePlan: sampleWavePlan,
      },
      global: { stubs },
    })
    await flushPromises()

    const dispatchBtn = wrapper.findAll('button').find((b) => b.text().includes('一键全波次流水线调度'))
    expect(dispatchBtn).toBeDefined()
    await dispatchBtn!.trigger('click')
    await flushPromises()

    expect(wrapper.emitted('executedWave')).toEqual([[-1]])
  })

  it('emits selectedNode when node card is clicked', async () => {
    const wrapper = mount(CaseDagTopologyDrawer, {
      props: {
        open: true,
        dagData: sampleDag,
        wavePlan: sampleWavePlan,
      },
      global: { stubs },
    })
    await flushPromises()

    const nodeCard = wrapper.find('.node-card')
    expect(nodeCard.exists()).toBe(true)
    await nodeCard.trigger('click')

    expect(wrapper.emitted('selectedNode')).toEqual([['case_login']])
  })
})
