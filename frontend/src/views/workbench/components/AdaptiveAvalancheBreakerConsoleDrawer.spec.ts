import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import AdaptiveAvalancheBreakerConsoleDrawer from './AdaptiveAvalancheBreakerConsoleDrawer.vue'
import * as stressApi from '@/api/fullLinkStressTesting'

describe('AdaptiveAvalancheBreakerConsoleDrawer.vue (UI3.3)', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.spyOn(stressApi, 'listBreakerReports').mockResolvedValue({
      total: 1,
      reports: [
        {
          report_id: 'rep_brk_01',
          scenario_name: 'full-link-order-checkout-stress',
          current_watermark_pct: 88.0,
          current_p99_latency_ms: 850,
          current_error_rate_pct: 2.5,
          is_circuit_broken: false,
          circuit_state: 'THROTTLING_STAGE_1',
          final_decision: {
            decision_id: 'dec_01',
            breaker_state: 'THROTTLING_STAGE_1',
            action: 'THROTTLE_DOWN',
            throttle_ratio_pct: 25,
            trigger_reason: '资源水位突破 85% (当前 88%) 且 P99 延迟突破 800ms，触发一级缓速限流 25%',
            suggested_safe_tps: 3150,
          },
          remediation_instructions: [
            '网关集群已自动广播降级指令，对非核心查询类请求开启 25% 快速失败',
          ],
          created_at: new Date().toISOString(),
        },
      ],
    })

    vi.spyOn(stressApi, 'evaluateCircuitBreaker').mockResolvedValue({
      message: 'Circuit breaker evaluated',
      report: {
        report_id: 'rep_brk_02',
        scenario_name: 'full-link-order-checkout-stress',
        current_watermark_pct: 96.0,
        current_p99_latency_ms: 1200,
        current_error_rate_pct: 6.2,
        is_circuit_broken: true,
        circuit_state: 'THROTTLING_STAGE_2',
        final_decision: {
          decision_id: 'dec_02',
          breaker_state: 'THROTTLING_STAGE_2',
          action: 'THROTTLE_DOWN_HARD',
          throttle_ratio_pct: 60,
          trigger_reason: '资源水位突破 95% 且错误率达 6.2%，启动二级急刹截流 60%',
          suggested_safe_tps: 1800,
        },
        remediation_instructions: [
          '通知下游加速连接池释放，若继续攀升将升级至 ABORT 硬核熔断',
        ],
        created_at: new Date().toISOString(),
      },
    })

    vi.spyOn(stressApi, 'resetCircuitBreaker').mockResolvedValue({
      message: 'Circuit breaker reset successfully',
      current_state: 'CLOSED_NORMAL',
    })
  })

  it('正确渲染自适应分级限流与熔断控制台抽屉、4 大 KPI 与 4 阶段状态机卡片', async () => {
    const wrapper = mount(AdaptiveAvalancheBreakerConsoleDrawer, {
      props: {
        open: true,
      },
      global: {
        stubs: {
          'a-drawer': { template: '<div><slot /></div>' },
          'a-row': { template: '<div><slot /></div>' },
          'a-col': { template: '<div><slot /></div>' },
          'a-card': { template: '<div><slot name="extra" /><slot /></div>' },
          'a-button': { template: '<button><slot /></button>' },
          'a-space': { template: '<div><slot /></div>' },
          'a-form': { template: '<form><slot /></form>' },
          'a-form-item': { template: '<div><slot /></div>' },
          'a-input-number': { template: '<input type="number" />' },
        },
      },
    })

    await flushPromises()

    expect(wrapper.text()).toContain('自适应分级限流 (Adaptive Throttling) 与级联雪崩阻断器')
    expect(wrapper.text()).toContain('当前熔断状态机')
    expect(wrapper.text()).toContain('STAGE 1 (缓速)')
    expect(wrapper.text()).toContain('实时限流截流比例')
    expect(wrapper.text()).toContain('25%')
    expect(wrapper.text()).toContain('建议安全承载 TPS')
    expect(wrapper.text()).toContain('3150')
    expect(wrapper.text()).toContain('尾部 P99 瞬时延迟')
    expect(wrapper.text()).toContain('850 ms')
    expect(wrapper.text()).toContain('CLOSED_NORMAL')
    expect(wrapper.text()).toContain('THROTTLING_1')
    expect(wrapper.text()).toContain('THROTTLING_2')
    expect(wrapper.text()).toContain('TRIPPED_ABORT')
    expect(stressApi.listBreakerReports).toHaveBeenCalledTimes(1)
  })

  it('点击执行自适应熔断判定评估，触发 evaluateCircuitBreaker API 并更新状态', async () => {
    const wrapper = mount(AdaptiveAvalancheBreakerConsoleDrawer, {
      props: {
        open: true,
      },
      global: {
        stubs: {
          'a-drawer': { template: '<div><slot /></div>' },
          'a-row': { template: '<div><slot /></div>' },
          'a-col': { template: '<div><slot /></div>' },
          'a-card': { template: '<div><slot name="extra" /><slot /></div>' },
          'a-button': {
            props: ['loading'],
            emits: ['click'],
            template: '<button @click="$emit(\'click\')"><slot /></button>',
          },
          'a-space': { template: '<div><slot /></div>' },
          'a-form': { template: '<form><slot /></form>' },
          'a-form-item': { template: '<div><slot /></div>' },
          'a-input-number': { template: '<input type="number" />' },
        },
      },
    })

    await flushPromises()

    const evalBtn = wrapper.findAll('button').find((b) => b.text().includes('执行自适应熔断判定评估'))
    expect(evalBtn).toBeDefined()
    await evalBtn?.trigger('click')
    await flushPromises()

    expect(stressApi.evaluateCircuitBreaker).toHaveBeenCalledTimes(1)
    expect(wrapper.text()).toContain('STAGE 2 (急刹)')
    expect(wrapper.text()).toContain('60%')
    expect(wrapper.text()).toContain('1800')
  })

  it('点击一键紧急重置熔断器，触发 resetCircuitBreaker API 并恢复常态放行', async () => {
    const wrapper = mount(AdaptiveAvalancheBreakerConsoleDrawer, {
      props: {
        open: true,
      },
      global: {
        stubs: {
          'a-drawer': { template: '<div><slot /></div>' },
          'a-row': { template: '<div><slot /></div>' },
          'a-col': { template: '<div><slot /></div>' },
          'a-card': { template: '<div><slot name="extra" /><slot /></div>' },
          'a-button': {
            props: ['loading'],
            emits: ['click'],
            template: '<button @click="$emit(\'click\')"><slot /></button>',
          },
          'a-space': { template: '<div><slot /></div>' },
          'a-form': { template: '<form><slot /></form>' },
          'a-form-item': { template: '<div><slot /></div>' },
          'a-input-number': { template: '<input type="number" />' },
        },
      },
    })

    await flushPromises()

    const resetBtn = wrapper.findAll('button').find((b) => b.text().includes('一键紧急重置熔断器'))
    expect(resetBtn).toBeDefined()
    await resetBtn?.trigger('click')
    await flushPromises()

    expect(stressApi.resetCircuitBreaker).toHaveBeenCalledTimes(1)
    expect(wrapper.text()).toContain('NORMAL (正常)')
    expect(wrapper.text()).toContain('0%')
  })
})
