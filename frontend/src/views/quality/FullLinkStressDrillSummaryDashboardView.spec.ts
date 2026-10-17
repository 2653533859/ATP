import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import FullLinkStressDrillSummaryDashboardView from './FullLinkStressDrillSummaryDashboardView.vue'
import * as stressApi from '@/api/fullLinkStressTesting'

describe('FullLinkStressDrillSummaryDashboardView.vue (UI4.3)', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.spyOn(stressApi, 'listFullDrillReports').mockResolvedValue({
      total: 1,
      reports: [
        {
          report_id: 'drill_rep_01',
          drill_id: 'drill_prod_001',
          scenario_name: 'full-link-order-checkout-stress',
          overall_drill_grade: 'GRADE_A_EXCELLENT',
          is_production_approved: true,
          composite_health_score_pct: 98.5,
          peak_concurrency_vu: 1200,
          peak_tps: 6850,
          p99_latency_ms: 220,
          error_rate_pct: 0.05,
          knee_point_concurrency: 450,
          knee_point_tps: 6800,
          cliff_point_concurrency: 850,
          max_db_watermark_pct: 88,
          max_redis_watermark_pct: 75,
          max_mq_backlog: 12500,
          circuit_breaker_triggered: false,
          failover_rto_ms: 1420,
          sha256_audit_fingerprint: '38fe8eaab2de3c87a9ef4717b074d2847291a27e1f42284959db2856238bc3a1',
          optimization_remediations: [
            '系统最佳产出并发为 450 VU',
            '单元故障切换演练 RTO 为 1420ms',
          ],
          created_at: new Date().toISOString(),
        },
      ],
    })
    vi.spyOn(stressApi, 'getFullDrillMarkdown').mockResolvedValue({
      report_id: 'drill_rep_01',
      markdown: '# 全链路压力演练综合复盘报告 (drill_prod_001)\n\nGRADE_A_EXCELLENT',
    })
  })

  it('正确渲染全链路压力演练大盘 Hero、4 大核心 KPI 与数字孪生明细', async () => {
    const wrapper = mount(FullLinkStressDrillSummaryDashboardView, {
      global: {
        stubs: {
          'a-row': { template: '<div><slot /></div>' },
          'a-col': { template: '<div><slot /></div>' },
          'a-card': {
            props: ['title'],
            template: '<div class="ant-card"><div class="ant-card-title">{{ title }}</div><slot name="extra" /><slot /></div>',
          },
          'a-button': { template: '<button><slot /></button>' },
          'a-space': { template: '<div><slot /></div>' },
          'a-tag': { template: '<span class="ant-tag"><slot /></span>' },
          'a-descriptions': { template: '<div class="ant-desc"><slot /></div>' },
          'a-descriptions-item': { template: '<div><slot /></div>' },
          'a-modal': { template: '<div class="ant-modal"><slot /></div>' },
          'a-textarea': { template: '<textarea />' },
          StepLoadThroughputKneeDrawer: { template: '<div class="knee-drawer-stub" />' },
          StressBlastRadiusEvaluatorCard: { template: '<div class="blast-drawer-stub" />' },
          AdaptiveAvalancheBreakerConsoleDrawer: { template: '<div class="breaker-drawer-stub" />' },
        },
      },
    })

    await flushPromises()

    expect(wrapper.text()).toContain('全链路压力演练综合审计与数字孪生复盘大盘')
    expect(wrapper.text()).toContain('全链路演练综合评级')
    expect(wrapper.text()).toContain('GRADE A (卓越)')
    expect(wrapper.text()).toContain('生产发布准入裁决')
    expect(wrapper.text()).toContain('APPROVED 准入')
    expect(wrapper.text()).toContain('综合系统健康得分')
    expect(wrapper.text()).toContain('98.5%')
    expect(wrapper.text()).toContain('6850')
    expect(wrapper.text()).toContain('38fe8eaab2de3c87a9ef4717b074d2847291a27e1f42284959db2856238bc3a1')
    expect(stressApi.listFullDrillReports).toHaveBeenCalledTimes(1)
  })

  it('点击查看全景演练报告 Markdown，调用 getFullDrillMarkdown API 并弹出对话框', async () => {
    const wrapper = mount(FullLinkStressDrillSummaryDashboardView, {
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
          'a-tag': { template: '<span class="ant-tag"><slot /></span>' },
          'a-descriptions': { template: '<div class="ant-desc"><slot /></div>' },
          'a-descriptions-item': { template: '<div><slot /></div>' },
          'a-modal': {
            props: ['open', 'title'],
            template: '<div v-if="open" class="ant-modal"><slot /></div>',
          },
          'a-textarea': {
            props: ['value'],
            template: '<textarea :value="value" />',
          },
          StepLoadThroughputKneeDrawer: { template: '<div class="knee-drawer-stub" />' },
          StressBlastRadiusEvaluatorCard: { template: '<div class="blast-drawer-stub" />' },
          AdaptiveAvalancheBreakerConsoleDrawer: { template: '<div class="breaker-drawer-stub" />' },
        },
      },
    })

    await flushPromises()

    const mdBtn = wrapper.findAll('button').find((b) => b.text().includes('全景演练报告 Markdown'))
    expect(mdBtn).toBeDefined()
    await mdBtn?.trigger('click')
    await flushPromises()

    expect(stressApi.getFullDrillMarkdown).toHaveBeenCalledTimes(1)
    expect(wrapper.find('textarea').element.value).toContain('GRADE_A_EXCELLENT')
  })
})
