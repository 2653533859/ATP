import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import DistributedBottleneckClassifierCard from './DistributedBottleneckClassifierCard.vue'
import * as stressApi from '@/api/fullLinkStressTesting'

describe('DistributedBottleneckClassifierCard.vue (UI3.2)', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.spyOn(stressApi, 'listBottleneckReports').mockResolvedValue({
      total: 1,
      reports: [
        {
          report_id: 'rep_bn_01',
          scenario_name: 'full-link-order-checkout-stress',
          total_spans_analyzed: 45000,
          p50_latency_ms: 45,
          p90_latency_ms: 180,
          p99_latency_ms: 680,
          total_bottlenecks_count: 2,
          primary_root_cause: 'LOCK_CONTENTION_DEADLOCK',
          system_stress_health_score: 86.5,
          findings: [
            {
              finding_id: 'find_01',
              cause_type: 'LOCK_CONTENTION_DEADLOCK',
              severity: 'CRITICAL',
              culprit_service: 'order-payment-service',
              culprit_endpoint_or_sql: 'UPDATE account_wallet SET balance = balance - 100 WHERE user_id = ?',
              measured_duration_ms: 680,
              impact_description: '热点账户行级排他锁争用超时',
              optimization_recommendation: '采用分段锁或内存账本异步冲正',
            },
          ],
          created_at: new Date().toISOString(),
        },
      ],
    })

    vi.spyOn(stressApi, 'classifyBottlenecks').mockResolvedValue({
      message: 'Bottlenecks classified',
      report: {
        report_id: 'rep_bn_02',
        scenario_name: 'full-link-order-checkout-stress',
        total_spans_analyzed: 50000,
        p50_latency_ms: 50,
        p90_latency_ms: 210,
        p99_latency_ms: 750,
        total_bottlenecks_count: 1,
        primary_root_cause: 'SLOW_DATABASE_QUERY',
        system_stress_health_score: 82.0,
        findings: [
          {
            finding_id: 'find_02',
            cause_type: 'SLOW_DATABASE_QUERY',
            severity: 'HIGH',
            culprit_service: 'order-query-service',
            culprit_endpoint_or_sql: 'SELECT * FROM orders WHERE status = ?',
            measured_duration_ms: 750,
            impact_description: '缺少 status 复合索引导致全表扫描',
            optimization_recommendation: '新增 (status, create_time) 联合索引',
          },
        ],
        created_at: new Date().toISOString(),
      },
    })
  })

  it('正确渲染调用链瓶颈归因抽屉、4 大延迟 KPI 与瓶颈根因 Banner', async () => {
    const wrapper = mount(DistributedBottleneckClassifierCard, {
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

    expect(wrapper.text()).toContain('分布式调用链热点与争用瓶颈根因分类诊断')
    expect(wrapper.text()).toContain('压测综合健康分')
    expect(wrapper.text()).toContain('86.5')
    expect(wrapper.text()).toContain('P50 中位响应延迟')
    expect(wrapper.text()).toContain('45 ms')
    expect(wrapper.text()).toContain('P90 分位响应延迟')
    expect(wrapper.text()).toContain('180 ms')
    expect(wrapper.text()).toContain('P99 尾部尖刺延迟')
    expect(wrapper.text()).toContain('680 ms')
    expect(wrapper.text()).toContain('LOCK_CONTENTION_DEADLOCK')
    expect(stressApi.listBottleneckReports).toHaveBeenCalledTimes(1)
  })

  it('点击即时调用链争用归因分析，调用 classifyBottlenecks API 并更新明细', async () => {
    const wrapper = mount(DistributedBottleneckClassifierCard, {
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
                  <slot name="bodyCell" :column="{ key: 'culprit' }" :record="record" />
                  <slot name="bodyCell" :column="{ key: 'cause' }" :record="record" />
                  <slot name="bodyCell" :column="{ key: 'duration' }" :record="record" />
                  <slot name="bodyCell" :column="{ key: 'remediation' }" :record="record" />
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

    const classifyBtn = wrapper.findAll('button').find((b) => b.text().includes('即时调用链争用归因分析'))
    expect(classifyBtn).toBeDefined()
    await classifyBtn?.trigger('click')
    await flushPromises()

    expect(stressApi.classifyBottlenecks).toHaveBeenCalledTimes(1)
    expect(wrapper.text()).toContain('SLOW_DATABASE_QUERY')
    expect(wrapper.text()).toContain('缺少 status 复合索引导致全表扫描')
    expect(wrapper.text()).toContain('新增 (status, create_time) 联合索引')
  })
})
