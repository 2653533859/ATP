import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import MultisourceCapacityWatermarkDrawer from './MultisourceCapacityWatermarkDrawer.vue'
import * as stressApi from '@/api/fullLinkStressTesting'

describe('MultisourceCapacityWatermarkDrawer.vue (UI3.1)', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.spyOn(stressApi, 'listWatermarkReports').mockResolvedValue({
      total: 1,
      reports: [
        {
          report_id: 'rep_wm_01',
          target_cluster_or_env: 'prod-stress-cluster',
          total_resources_measured: 4,
          health_load_index_pct: 79.5,
          max_utilization_pct: 88.0,
          weakest_bottleneck_resource: 'db_connection_pool_master',
          requires_avalanche_breaker: true,
          watermarks: [
            {
              resource_id: 'db_connection_pool_master',
              resource_type: 'DATABASE_POOL',
              current_value: 440,
              capacity_limit: 500,
              utilization_rate_pct: 88.0,
              watermark_level: 'SATURATED',
              unit: 'conn',
              detail_metric_name: 'hikari_active_connections_pool_master',
            },
            {
              resource_id: 'redis_cluster_cache',
              resource_type: 'REDIS_CACHE',
              current_value: 48,
              capacity_limit: 64,
              utilization_rate_pct: 75.0,
              watermark_level: 'WARNING',
              unit: 'GB',
              detail_metric_name: 'used_memory_rss_bytes',
            },
          ],
          remediation_actions: [
            '数据库连接池达到 SATURATED 水位，建议扩容',
          ],
          created_at: new Date().toISOString(),
        },
      ],
    })

    vi.spyOn(stressApi, 'meterCapacityWatermark').mockResolvedValue({
      message: 'Watermark metered',
      report: {
        report_id: 'rep_wm_02',
        target_cluster_or_env: 'prod-stress-cluster',
        total_resources_measured: 4,
        health_load_index_pct: 85.0,
        max_utilization_pct: 92.0,
        weakest_bottleneck_resource: 'db_connection_pool_master',
        requires_avalanche_breaker: true,
        watermarks: [
          {
            resource_id: 'db_connection_pool_master',
            resource_type: 'DATABASE_POOL',
            current_value: 460,
            capacity_limit: 500,
            utilization_rate_pct: 92.0,
            watermark_level: 'SATURATED',
            unit: 'conn',
            detail_metric_name: 'hikari_active_connections_pool_master',
          },
        ],
        remediation_actions: [
          '触发防雪崩熔断，建议开启一级降级',
        ],
        created_at: new Date().toISOString(),
      },
    })
  })

  it('正确渲染多源基础设施容量水位抽屉、4 大核心 KPI 与资源大表', async () => {
    const wrapper = mount(MultisourceCapacityWatermarkDrawer, {
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
          'a-progress': { template: '<div class="ant-progress" />' },
        },
      },
    })

    await flushPromises()

    expect(wrapper.text()).toContain('多源基础设施容量水位 (Watermark) 与木桶短板定位')
    expect(wrapper.text()).toContain('综合健康负载指数')
    expect(wrapper.text()).toContain('79.5%')
    expect(wrapper.text()).toContain('峰值资源利用率')
    expect(wrapper.text()).toContain('88.0%')
    expect(wrapper.text()).toContain('木桶短板瓶颈资源')
    expect(wrapper.text()).toContain('db_connection_pool_master')
    expect(wrapper.text()).toContain('BREAKER_TRIPPED')
    expect(stressApi.listWatermarkReports).toHaveBeenCalledTimes(1)
  })

  it('点击即时多源容量水位采样，调用 meterCapacityWatermark API 并更新报告', async () => {
    const wrapper = mount(MultisourceCapacityWatermarkDrawer, {
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
          'a-button': {
            props: ['loading'],
            emits: ['click'],
            template: '<button @click="$emit(\'click\')"><slot /></button>',
          },
          'a-space': { template: '<div><slot /></div>' },
          'a-progress': { template: '<div class="ant-progress" />' },
        },
      },
    })

    await flushPromises()

    const meterBtn = wrapper.findAll('button').find((b) => b.text().includes('即时多源容量水位采样'))
    expect(meterBtn).toBeDefined()
    await meterBtn?.trigger('click')
    await flushPromises()

    expect(stressApi.meterCapacityWatermark).toHaveBeenCalledTimes(1)
    expect(wrapper.text()).toContain('85.0%')
    expect(wrapper.text()).toContain('触发防雪崩熔断，建议开启一级降级')
  })
})
