import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import CellFailoverResilienceDashboardView from './CellFailoverResilienceDashboardView.vue'
import * as stressApi from '@/api/fullLinkStressTesting'

describe('CellFailoverResilienceDashboardView.vue (UI2.3)', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.spyOn(stressApi, 'simulateCellFailover').mockResolvedValue({
      message: 'Cell failover drill completed',
      report: {
        drill_id: 'drill_1001',
        failed_cell_id: 'cell-beijing-01',
        standby_cell_id: 'cell-beijing-02',
        traffic_shift_percentage: 100,
        total_rto_duration_ms: 1350,
        estimated_packet_drop_pct: 0.015,
        verdict: 'FAILOVER_SUCCESS',
        is_resilience_qualified: true,
        timeline_phases: [
          {
            phase_name: '阶段 1: 心跳探活失联与脑裂防范',
            duration_ms: 300,
            status: 'COMPLETED',
            detail: '已成功摘除故障单元',
          },
          {
            phase_name: '阶段 2: 动态 DNS 权重与 Anycast BGP 切换',
            duration_ms: 350,
            status: 'COMPLETED',
            detail: '已切流至备用单元',
          },
        ],
        remediation_recommendations: [
          '保持备用单元常态热备水位',
        ],
        created_at: new Date().toISOString(),
      },
    })
  })

  it('正确渲染单元容灾自愈大盘 Banner、4 大金融级容灾 KPI 卡片与演练控制台', async () => {
    const wrapper = mount(CellFailoverResilienceDashboardView, {
      global: {
        stubs: {
          'a-card': {
            props: ['title'],
            template: '<div class="ant-card"><div class="ant-card-title">{{ title }}</div><slot name="extra" /><slot /></div>',
          },
          'a-col': { template: '<div><slot /></div>' },
          'a-button': { template: '<button><slot /></button>' },
          'a-space': { template: '<div><slot /></div>' },
          'a-form': { template: '<form><slot /></form>' },
          'a-form-item': { template: '<div><slot /></div>' },
          'a-select': { template: '<select><slot /></select>' },
          'a-select-option': { template: '<option><slot /></option>' },
          'a-slider': { template: '<div class="ant-slider" />' },
          'a-input-number': { template: '<input type="number" />' },
          'a-timeline': { template: '<div class="ant-timeline"><slot /></div>' },
          'a-timeline-item': { template: '<div class="ant-timeline-item"><slot /><slot name="dot" /></div>' },
          'a-tag': { template: '<span class="ant-tag"><slot /></span>' },
          CellBasedTrafficControllerDrawer: { template: '<div class="controller-drawer-stub" />' },
          CellEscapeDependencyPanel: { template: '<div class="escape-panel-stub" />' },
        },
      },
    })

    await flushPromises()

    expect(wrapper.text()).toContain('单元故障演练与常态化容灾自愈全景大盘')
    expect(wrapper.text()).toContain('全流程容灾恢复时间 (RTO)')
    expect(wrapper.text()).toContain('切流瞬时丢包率 (Packet Loss)')
    expect(wrapper.text()).toContain('容灾自愈评级裁决')
    expect(wrapper.text()).toContain('FAILOVER_SUCCESS 达标')
    expect(wrapper.text()).toContain('故障切流接管比例')
    expect(wrapper.text()).toContain('4 阶段容灾恢复时序流水线')
  })

  it('点击发起演练测试，触发 simulateCellFailover API 并更新 RTO 与时序报告', async () => {
    const wrapper = mount(CellFailoverResilienceDashboardView, {
      global: {
        stubs: {
          'a-row': { template: '<div><slot /></div>' },
          'a-col': { template: '<div><slot /></div>' },
          'a-card': {
            props: ['title'],
            template: '<div class="ant-card"><div class="ant-card-title">{{ title }}</div><slot name="extra" /><slot /></div>',
          },
          'a-button': {
            props: ['loading'],
            emits: ['click'],
            template: '<button @click="$emit(\'click\')"><slot /></button>',
          },
          'a-space': { template: '<div><slot /></div>' },
          'a-form-item': { template: '<div><slot /></div>' },
          'a-select': { template: '<select><slot /></select>' },
          'a-select-option': { template: '<option><slot /></option>' },
          'a-slider': { template: '<div class="ant-slider" />' },
          'a-input-number': { template: '<input type="number" />' },
          'a-timeline': { template: '<div class="ant-timeline"><slot /></div>' },
          'a-timeline-item': { template: '<div class="ant-timeline-item"><slot /><slot name="dot" /></div>' },
          'a-tag': { template: '<span class="ant-tag"><slot /></span>' },
          CellBasedTrafficControllerDrawer: { template: '<div class="controller-drawer-stub" />' },
          CellEscapeDependencyPanel: { template: '<div class="escape-panel-stub" />' },
        },
      },
    })

    await flushPromises()

    const drillBtn = wrapper.findAll('button').find((b) => b.text().includes('发起单机房/单元瘫痪演练测试'))
    expect(drillBtn).toBeDefined()
    await drillBtn?.trigger('click')
    await flushPromises()

    expect(stressApi.simulateCellFailover).toHaveBeenCalledTimes(1)
    expect(wrapper.text()).toContain('1350 ms')
    expect(wrapper.text()).toContain('保持备用单元常态热备水位')
  })
})
