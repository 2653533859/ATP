import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import StepLoadThroughputKneeDrawer from './StepLoadThroughputKneeDrawer.vue'
import * as stressApi from '@/api/fullLinkStressTesting'

describe('StepLoadThroughputKneeDrawer.vue (UI4.1)', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.spyOn(stressApi, 'listThroughputKneeReports').mockResolvedValue({
      total: 1,
      reports: [
        {
          report_id: 'rep_knee_01',
          scenario_name: 'full-link-order-checkout-stress',
          total_steps_count: 5,
          peak_tps: 6850,
          knee_point_concurrency: 450,
          knee_point_tps: 6800,
          knee_point_latency_ms: 120,
          cliff_point_concurrency: 850,
          recommended_safe_concurrency: 337,
          step_samples: [
            {
              step_index: 1,
              concurrency_threads: 100,
              measured_tps: 2200,
              avg_latency_ms: 35,
              p99_latency_ms: 65,
              error_rate_pct: 0.0,
              zone: 'OPTIMAL_ZONE',
            },
            {
              step_index: 2,
              concurrency_threads: 450,
              measured_tps: 6800,
              avg_latency_ms: 120,
              p99_latency_ms: 220,
              error_rate_pct: 0.05,
              zone: 'OPTIMAL_ZONE',
            },
            {
              step_index: 3,
              concurrency_threads: 850,
              measured_tps: 4200,
              avg_latency_ms: 950,
              p99_latency_ms: 2400,
              error_rate_pct: 8.5,
              zone: 'DEGRADED_OVERLOAD_ZONE',
            },
          ],
          capacity_planning_advice: [
            '系统在 450 VU 达到最佳拐点 Knee Point',
            '建议线上日常生产限流设定为 337 VU',
          ],
          created_at: new Date().toISOString(),
        },
      ],
    })

    vi.spyOn(stressApi, 'analyzeThroughputKnee').mockResolvedValue({
      message: 'Knee point analyzed',
      report: {
        report_id: 'rep_knee_02',
        scenario_name: 'full-link-order-checkout-stress',
        total_steps_count: 3,
        peak_tps: 7200,
        knee_point_concurrency: 500,
        knee_point_tps: 7150,
        knee_point_latency_ms: 130,
        cliff_point_concurrency: 900,
        recommended_safe_concurrency: 375,
        step_samples: [
          {
            step_index: 1,
            concurrency_threads: 500,
            measured_tps: 7150,
            avg_latency_ms: 130,
            p99_latency_ms: 240,
            error_rate_pct: 0.02,
            zone: 'OPTIMAL_ZONE',
          },
        ],
        capacity_planning_advice: [
          '重算后最佳拐点提升至 500 VU',
        ],
        created_at: new Date().toISOString(),
      },
    })
  })

  it('正确渲染阶梯加压拐点分析抽屉、4 大 KPI 卡片与采样大表', async () => {
    const wrapper = mount(StepLoadThroughputKneeDrawer, {
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

    expect(wrapper.text()).toContain('阶梯加压拐点探测 (Throughput Knee & Cliff Detection)')
    expect(wrapper.text()).toContain('极限峰值吞吐量 (Peak TPS)')
    expect(wrapper.text()).toContain('6850')
    expect(wrapper.text()).toContain('最佳拐点并发 (Knee Point)')
    expect(wrapper.text()).toContain('450 VU')
    expect(wrapper.text()).toContain('崩溃断崖并发 (Cliff Point)')
    expect(wrapper.text()).toContain('850 VU')
    expect(wrapper.text()).toContain('日常推荐安全并发 (Safe VU)')
    expect(wrapper.text()).toContain('337 VU')
    expect(stressApi.listThroughputKneeReports).toHaveBeenCalledTimes(1)
  })

  it('点击执行阶梯加压拐点智能计算，调用 analyzeThroughputKnee API 并更新指标', async () => {
    const wrapper = mount(StepLoadThroughputKneeDrawer, {
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
                  <slot name="bodyCell" :column="{ key: 'step' }" :record="record" />
                  <slot name="bodyCell" :column="{ key: 'concurrency' }" :record="record" />
                  <slot name="bodyCell" :column="{ key: 'tps' }" :record="record" />
                  <slot name="bodyCell" :column="{ key: 'latency' }" :record="record" />
                  <slot name="bodyCell" :column="{ key: 'error' }" :record="record" />
                  <slot name="bodyCell" :column="{ key: 'zone' }" :record="record" />
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

    const calcBtn = wrapper.findAll('button').find((b) => b.text().includes('执行阶梯加压拐点智能计算'))
    expect(calcBtn).toBeDefined()
    await calcBtn?.trigger('click')
    await flushPromises()

    expect(stressApi.analyzeThroughputKnee).toHaveBeenCalledTimes(1)
    expect(wrapper.text()).toContain('7200')
    expect(wrapper.text()).toContain('500 VU')
    expect(wrapper.text()).toContain('重算后最佳拐点提升至 500 VU')
  })
})
