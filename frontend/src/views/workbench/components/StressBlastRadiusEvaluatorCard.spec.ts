import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import StressBlastRadiusEvaluatorCard from './StressBlastRadiusEvaluatorCard.vue'
import * as stressApi from '@/api/fullLinkStressTesting'

describe('StressBlastRadiusEvaluatorCard.vue (UI4.2)', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.spyOn(stressApi, 'listBlastRadiusReports').mockResolvedValue({
      total: 1,
      reports: [
        {
          report_id: 'rep_blast_01',
          drill_id: 'drill_prod_001',
          blast_radius_tier: 'TIER_1_ISOLATED',
          safety_verdict: 'PASS_READY_FOR_STRESS',
          safety_score_pct: 100.0,
          is_stress_approved: true,
          audit_tamper_evident_fingerprint: 'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855',
          safety_checks: [
            {
              check_name: '跨协议影子染色标透传',
              is_passed: true,
              risk_weight: 30,
              description: '全链路服务透传 X-ATP-Shadow 标',
            },
            {
              check_name: '持久层影子库表重写路由',
              is_passed: true,
              risk_weight: 30,
              description: '所有写入表已登记影子映射',
            },
          ],
          emergency_rollback_procedures: [
            '下发 ABORT 紧急熔断指令',
          ],
          created_at: new Date().toISOString(),
        },
      ],
    })

    vi.spyOn(stressApi, 'evaluateStressBlastRadius').mockResolvedValue({
      message: 'Blast radius evaluated',
      report: {
        report_id: 'rep_blast_02',
        drill_id: 'drill_prod_001',
        blast_radius_tier: 'TIER_2_CELL_BOUND',
        safety_verdict: 'CAUTION_MONITORED',
        safety_score_pct: 88.0,
        is_stress_approved: true,
        audit_tamper_evident_fingerprint: '9f86d081884c7d659a2feaa0c55ad015a3bf4f1b2b0b822cd15d6c15b0f00a08',
        safety_checks: [
          {
            check_name: '跨协议影子染色标透传',
            is_passed: true,
            risk_weight: 30,
            description: '全链路服务透传 X-ATP-Shadow 标',
          },
        ],
        emergency_rollback_procedures: [
          '通知运维开启备用监控',
        ],
        created_at: new Date().toISOString(),
      },
    })
  })

  it('正确渲染爆炸半径评估抽屉、4 大 KPI 卡片与 SHA-256 指纹 Banner', async () => {
    const wrapper = mount(StressBlastRadiusEvaluatorCard, {
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
          'a-button': { template: '<button><slot /></button>' },
          'a-space': { template: '<div><slot /></div>' },
        },
      },
    })

    await flushPromises()

    expect(wrapper.text()).toContain('全链路压测爆炸半径评估 (Blast Radius Safety Evaluator)')
    expect(wrapper.text()).toContain('安全准入合规评分')
    expect(wrapper.text()).toContain('100.0%')
    expect(wrapper.text()).toContain('评估爆炸半径等级')
    expect(wrapper.text()).toContain('TIER 1 (沙箱隔离)')
    expect(wrapper.text()).toContain('APPROVED 准许加压')
    expect(wrapper.text()).toContain('e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855')
    expect(stressApi.listBlastRadiusReports).toHaveBeenCalledTimes(1)
  })

  it('点击执行爆炸半径准入核验，调用 evaluateStressBlastRadius API 并更新状态', async () => {
    const wrapper = mount(StressBlastRadiusEvaluatorCard, {
      props: {
        open: true,
      },
      global: {
        stubs: {
          'a-drawer': { template: '<div><slot /></div>' },
          'a-row': { template: '<div><slot /></div>' },
          'a-col': { template: '<div><slot /></div>' },
          'a-card': { template: '<div><slot name="extra" /><slot /></div>' },
          'a-table': {
            props: ['dataSource'],
            template: `
              <div class="ant-table">
                <div v-for="(record, idx) in dataSource" :key="idx" class="ant-table-row">
                  <slot name="bodyCell" :column="{ key: 'check_name' }" :record="record" />
                  <slot name="bodyCell" :column="{ key: 'status' }" :record="record" />
                  <slot name="bodyCell" :column="{ key: 'weight' }" :record="record" />
                  <slot name="bodyCell" :column="{ key: 'description' }" :record="record" />
                </div>
              </div>
            `,
          },
          'a-tag': { template: '<span class="ant-tag"><slot /></span>' },
          'a-button': {
            props: ['loading'],
            emits: ['click'],
            template: '<button @click="$emit(\'click\')"><slot /></button>',
          },
          'a-space': { template: '<div><slot /></div>' },
        },
      },
    })

    await flushPromises()

    const evalBtn = wrapper.findAll('button').find((b) => b.text().includes('执行爆炸半径准入核验'))
    expect(evalBtn).toBeDefined()
    await evalBtn?.trigger('click')
    await flushPromises()

    expect(stressApi.evaluateStressBlastRadius).toHaveBeenCalledTimes(1)
    expect(wrapper.text()).toContain('88.0%')
    expect(wrapper.text()).toContain('TIER 2 (单元闭环)')
    expect(wrapper.text()).toContain('9f86d081884c7d659a2feaa0c55ad015a3bf4f1b2b0b822cd15d6c15b0f00a08')
  })
})
