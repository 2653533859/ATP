import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import CellBasedTrafficControllerDrawer from './CellBasedTrafficControllerDrawer.vue'
import * as stressApi from '@/api/fullLinkStressTesting'

describe('CellBasedTrafficControllerDrawer.vue (UI2.1)', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.spyOn(stressApi, 'listCells').mockResolvedValue({
      total: 3,
      cells: [
        {
          cell_id: 'cell-beijing-01',
          cell_name: '华北1区-生产主单元A',
          zone: 'cn-beijing-a',
          traffic_weight: 50,
          status: 'ACTIVE_PROD',
          allowed_shards: [0, 1, 2, 3],
          is_stress_target: false,
        },
        {
          cell_id: 'cell-beijing-02',
          cell_name: '华北1区-生产主单元B',
          zone: 'cn-beijing-b',
          traffic_weight: 50,
          status: 'ACTIVE_PROD',
          allowed_shards: [4, 5, 6, 7],
          is_stress_target: false,
        },
        {
          cell_id: 'cell-beijing-stress',
          cell_name: '华北1区-专属压测单元S',
          zone: 'cn-beijing-c',
          traffic_weight: 100,
          status: 'STRESS_ONLY',
          allowed_shards: [8, 9],
          is_stress_target: true,
        },
      ],
    })

    vi.spyOn(stressApi, 'routeCellDecision').mockResolvedValue({
      message: 'Route decision evaluated',
      decision: {
        decision_id: 'dec_999',
        user_id: 'user_10086',
        is_shadow_traffic: true,
        assigned_cell_id: 'cell-beijing-stress',
        assigned_zone: 'cn-beijing-c',
        is_stress_cell: true,
        shunting_reason: '检测到 X-ATP-Shadow 压测标，定向至压测专用单元',
      },
    })

    vi.spyOn(stressApi, 'updateCellWeights').mockResolvedValue({
      message: 'Weights updated successfully',
      cells: [],
    })
  })

  it('正确渲染多可用区单元化切流抽屉、4项 KPI 卡片与单元矩阵', async () => {
    const wrapper = mount(CellBasedTrafficControllerDrawer, {
      props: {
        open: true,
      },
      global: {
        stubs: {
          'a-drawer': { template: '<div><slot /></div>' },
          'a-row': { template: '<div><slot /></div>' },
          'a-col': { template: '<div><slot /></div>' },
          'a-card': { template: '<div><slot name="extra" /><slot /></div>' },
          'a-table': { template: '<div class="ant-table"><slot /></div>' },
          'a-tag': { template: '<span class="ant-tag"><slot /></span>' },
          'a-badge': { template: '<span><slot /></span>' },
          'a-button': { template: '<button><slot /></button>' },
          'a-space': { template: '<div><slot /></div>' },
          'a-modal': { template: '<div><slot /></div>' },
          'a-form': { template: '<form><slot /></form>' },
          'a-form-item': { template: '<div><slot /></div>' },
          'a-input': { template: '<input />' },
          'a-input-number': { template: '<input type="number" />' },
          'a-switch': { template: '<input type="checkbox" />' },
          'a-slider': { template: '<div class="ant-slider" />' },
          'a-select': { template: '<select><slot /></select>' },
          'a-select-option': { template: '<option><slot /></option>' },
          'a-descriptions': { template: '<div><slot /></div>' },
          'a-descriptions-item': { template: '<div><slot /></div>' },
        },
      },
    })

    await flushPromises()

    expect(wrapper.text()).toContain('单元化测试隔离 (Cell-based Testing) 与智能切流调度')
    expect(wrapper.text()).toContain('活跃生产单元')
    expect(wrapper.text()).toContain('压测隔离单元')
    expect(wrapper.text()).toContain('排空/熔断单元')
    expect(wrapper.text()).toContain('单元拓扑总数')
    expect(stressApi.listCells).toHaveBeenCalledTimes(1)
  })

  it('触发单元路由沙箱演算，调用 routeCellDecision API 并展示结果', async () => {
    const wrapper = mount(CellBasedTrafficControllerDrawer, {
      props: {
        open: true,
      },
      global: {
        stubs: {
          'a-drawer': { template: '<div><slot /></div>' },
          'a-row': { template: '<div><slot /></div>' },
          'a-col': { template: '<div><slot /></div>' },
          'a-card': { template: '<div><slot name="extra" /><slot /></div>' },
          'a-table': { template: '<div class="ant-table"><slot /></div>' },
          'a-tag': { template: '<span class="ant-tag"><slot /></span>' },
          'a-badge': { template: '<span><slot /></span>' },
          'a-button': {
            props: ['loading'],
            emits: ['click'],
            template: '<button @click="$emit(\'click\')"><slot /></button>',
          },
          'a-space': { template: '<div><slot /></div>' },
          'a-modal': { template: '<div><slot /></div>' },
          'a-form': { template: '<form><slot /></form>' },
          'a-form-item': { template: '<div><slot /></div>' },
          'a-input': { template: '<input />' },
          'a-input-number': { template: '<input type="number" />' },
          'a-switch': { template: '<input type="checkbox" />' },
          'a-slider': { template: '<div class="ant-slider" />' },
          'a-select': { template: '<select><slot /></select>' },
          'a-select-option': { template: '<option><slot /></option>' },
          'a-descriptions': { template: '<div><slot /></div>' },
          'a-descriptions-item': { template: '<div><slot /></div>' },
        },
      },
    })

    await flushPromises()

    const runBtn = wrapper.findAll('button').find((b) => b.text().includes('执行单元路由演算'))
    expect(runBtn).toBeDefined()
    await runBtn?.trigger('click')
    await flushPromises()

    expect(stressApi.routeCellDecision).toHaveBeenCalledTimes(1)
    expect(wrapper.text()).toContain('路由决策裁决结果')
    expect(wrapper.text()).toContain('cell-beijing-stress')
  })
})
