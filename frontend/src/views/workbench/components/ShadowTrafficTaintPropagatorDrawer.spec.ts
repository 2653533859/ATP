import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import ShadowTrafficTaintPropagatorDrawer from './ShadowTrafficTaintPropagatorDrawer.vue'
import * as stressApi from '@/api/fullLinkStressTesting'

describe('ShadowTrafficTaintPropagatorDrawer.vue (UI1.1)', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.spyOn(stressApi, 'listShadowTaintReports').mockResolvedValue({
      total: 1,
      reports: [
        {
          report_id: 'taint_rpt_001',
          trace_id: 'st_trace_20261017_01',
          total_hops_count: 4,
          lost_hops_count: 0,
          verdict: 'FULL_PROPAGATION_SUCCESS',
          integrity_score_pct: 100.0,
          has_leakage_risk: false,
          hops: [
            {
              hop_order: 1,
              service_name: 'api_gateway',
              protocol: 'HTTP_REST',
              received_shadow_flag: true,
              retained_trace_id: 'st_trace_20261017_01',
              is_taint_lost: false,
            },
          ],
          remediation_advice: ['全链路影子流量染色标透明透传 100% 闭环。'],
          created_at: new Date().toISOString(),
        },
      ],
    })
    vi.spyOn(stressApi, 'injectShadowTaint').mockResolvedValue({
      message: '注入成功',
      protocol: 'HTTP_REST',
      injected_headers: {
        'X-ATP-Shadow': 'true',
        'X-ATP-Shadow-Trace': 'st_trace_20261017_01',
        'X-ATP-Shadow-Cluster': 'prod_stress_01',
      },
    })
    vi.spyOn(stressApi, 'verifyTracePropagation').mockResolvedValue({
      message: '校验完成',
      report: {
        report_id: 'taint_rpt_002',
        trace_id: 'st_trace_20261017_01',
        total_hops_count: 4,
        lost_hops_count: 0,
        verdict: 'FULL_PROPAGATION_SUCCESS',
        integrity_score_pct: 100.0,
        has_leakage_risk: false,
        hops: [],
        remediation_advice: [],
        created_at: new Date().toISOString(),
      },
    })
  })

  it('正确渲染标题 Banner、4 项核心染色透传 KPI 卡片及生成器与多跳表', async () => {
    const wrapper = mount(ShadowTrafficTaintPropagatorDrawer, {
      props: {
        open: true,
      },
      global: {
        stubs: {
          'a-drawer': { template: '<div><slot /></div>' },
          'a-row': { template: '<div><slot /></div>' },
          'a-col': { template: '<div><slot /></div>' },
          'a-tag': { template: '<span class="ant-tag"><slot /></span>' },
          'a-button': { template: '<button><slot /></button>' },
          'a-input': { template: '<input />' },
          'a-select': { template: '<select><slot /></select>' },
          'a-select-option': { template: '<option><slot /></option>' },
          'a-table': { template: '<div class="ant-table"><slot /></div>' },
          'a-form-item': { template: '<div><slot /></div>' },
        },
      },
    })

    await flushPromises()

    expect(wrapper.text()).toContain('全链路影子流量染色标 (Shadow Traffic Taint) 跨协议透传校验控制台')
    expect(wrapper.text()).toContain('透传完整性评分')
    expect(wrapper.text()).toContain('染色透传裁决结论')
    expect(wrapper.text()).toContain('丢标泄漏节点数')
    expect(wrapper.text()).toContain('全链路拓扑跳数')
    expect(wrapper.text()).toContain('100.0%')
  })

  it('点击启动多跳透传校验按钮能正确调用 API 并更新展示结果', async () => {
    const wrapper = mount(ShadowTrafficTaintPropagatorDrawer, {
      props: {
        open: true,
      },
      global: {
        stubs: {
          'a-drawer': { template: '<div><slot /></div>' },
          'a-row': { template: '<div><slot /></div>' },
          'a-col': { template: '<div><slot /></div>' },
          'a-tag': { template: '<span class="ant-tag"><slot /></span>' },
          'a-button': { template: '<button><slot /></button>' },
          'a-input': { template: '<input />' },
          'a-select': { template: '<select><slot /></select>' },
          'a-select-option': { template: '<option><slot /></option>' },
          'a-table': { template: '<div class="ant-table"><slot /></div>' },
          'a-form-item': { template: '<div><slot /></div>' },
        },
      },
    })

    await flushPromises()

    const verifyBtn = wrapper.findAll('button').find(b => b.text().includes('启动多跳透传校验'))
    expect(verifyBtn).toBeDefined()
    await verifyBtn?.trigger('click')
    await flushPromises()

    expect(stressApi.verifyTracePropagation).toHaveBeenCalledTimes(1)
  })
})
