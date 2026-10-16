import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import ShadowDatabaseIsolationDrawer from './ShadowDatabaseIsolationDrawer.vue'
import * as stressApi from '@/api/fullLinkStressTesting'

describe('ShadowDatabaseIsolationDrawer.vue (UI1.2)', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.spyOn(stressApi, 'listShadowMappings').mockResolvedValue({
      total: 1,
      mappings: [
        {
          mapping_id: 'map_01',
          production_table: 't_order',
          shadow_table: '__shadow_t_order__',
          isolation_strategy: 'SHADOW_TABLE',
          is_active: true,
        },
      ],
    })
    vi.spyOn(stressApi, 'inspectSqlIsolation').mockResolvedValue({
      message: '检验完成',
      report: {
        report_id: 'db_iso_001',
        target_cluster: 'prod_mysql_primary',
        total_queries_checked: 1,
        routed_to_shadow_count: 1,
        blocked_pollution_count: 0,
        safe_passthrough_count: 0,
        isolation_safety_score_pct: 100.0,
        has_critical_pollution_risk: false,
        inspections: [
          {
            item_id: 'sql_1',
            original_sql: 'INSERT INTO t_order VALUES (1)',
            is_shadow_traffic: true,
            is_write_operation: true,
            detected_target_table: 't_order',
            verdict: 'ROUTED_TO_SHADOW',
            rewritten_sql: 'INSERT INTO __shadow_t_order__ VALUES (1)',
            explanation: '重定向至影子表',
          },
        ],
        created_at: new Date().toISOString(),
      },
    })
  })

  it('正确渲染标题 Banner、4 项核心库表隔离 KPI 卡片及 SQL 检验器与映射表', async () => {
    const wrapper = mount(ShadowDatabaseIsolationDrawer, {
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
          'a-textarea': { template: '<textarea />' },
          'a-checkbox': { template: '<input type="checkbox" />' },
          'a-table': { template: '<div class="ant-table"><slot /></div>' },
          'a-modal': { template: '<div><slot /></div>' },
          'a-form': { template: '<form><slot /></form>' },
          'a-form-item': { template: '<div><slot /></div>' },
          'a-select': { template: '<select><slot /></select>' },
          'a-select-option': { template: '<option><slot /></option>' },
        },
      },
    })

    await flushPromises()

    expect(wrapper.text()).toContain('数据库连接池影子表动态路由重写与生产防污染拦截中心')
    expect(wrapper.text()).toContain('隔离安全合规评分')
    expect(wrapper.text()).toContain('生产数据污染风险')
    expect(wrapper.text()).toContain('成功重定向影子表')
    expect(wrapper.text()).toContain('高危写阻断拦截数')
    expect(wrapper.text()).toContain('100.0%')
  })

  it('点击模拟 SQL 路由检验按钮能正确调用 API 并更新展示结果', async () => {
    const wrapper = mount(ShadowDatabaseIsolationDrawer, {
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
          'a-textarea': { template: '<textarea />' },
          'a-checkbox': { template: '<input type="checkbox" />' },
          'a-table': { template: '<div class="ant-table"><slot /></div>' },
          'a-modal': { template: '<div><slot /></div>' },
          'a-form': { template: '<form><slot /></form>' },
          'a-form-item': { template: '<div><slot /></div>' },
          'a-select': { template: '<select><slot /></select>' },
          'a-select-option': { template: '<option><slot /></option>' },
        },
      },
    })

    await flushPromises()

    const inspectBtn = wrapper.findAll('button').find(b => b.text().includes('模拟 SQL 路由检验'))
    expect(inspectBtn).toBeDefined()
    await inspectBtn?.trigger('click')
    await flushPromises()

    expect(stressApi.inspectSqlIsolation).toHaveBeenCalledTimes(1)
  })
})
