import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import CellEscapeDependencyPanel from './CellEscapeDependencyPanel.vue'
import * as stressApi from '@/api/fullLinkStressTesting'

describe('CellEscapeDependencyPanel.vue (UI2.2)', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.spyOn(stressApi, 'listCellEscapeReports').mockResolvedValue({
      total: 1,
      reports: [
        {
          report_id: 'rep_esc_001',
          topology_name: 'prod-multi-zone-topology',
          total_edges_checked: 12,
          total_escapes_count: 0,
          shadow_escapes_count: 0,
          isolation_purity_score_pct: 100.0,
          is_strictly_cell_isolated: true,
          violations: [],
          created_at: new Date().toISOString(),
        },
      ],
    })

    vi.spyOn(stressApi, 'detectCellEscapes').mockResolvedValue({
      message: 'Cell escape detected',
      report: {
        report_id: 'rep_esc_002',
        topology_name: 'prod-multi-zone-topology',
        total_edges_checked: 15,
        total_escapes_count: 1,
        shadow_escapes_count: 0,
        isolation_purity_score_pct: 93.3,
        is_strictly_cell_isolated: false,
        violations: [
          {
            violation_id: 'viol_101',
            violation_type: 'SHARED_RESOURCE_CONTAMINATION',
            severity: 'HIGH',
            source_cell: 'cell-beijing-01',
            target_cell: 'cell-beijing-02',
            service_or_resource: 'user-profile-cache',
            description: '跨单元全局共享缓存未隔离',
            remediation_suggestion: '将缓存拆分为单元私有 Redis 实例',
          },
        ],
        created_at: new Date().toISOString(),
      },
    })
  })

  it('正确渲染跨单元逃逸面板、4 大核心 KPI 指标卡与调用边列表', async () => {
    const wrapper = mount(CellEscapeDependencyPanel, {
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

    expect(wrapper.text()).toContain('跨单元依赖逃逸 (Cell Escape) 与拓扑孤岛探查')
    expect(wrapper.text()).toContain('单元隔离纯度得分')
    expect(wrapper.text()).toContain('100.0%')
    expect(wrapper.text()).toContain('单元隔离合规裁决')
    expect(wrapper.text()).toContain('跨单元逃逸边总数')
    expect(wrapper.text()).toContain('影子流量逃逸数')
    expect(wrapper.text()).toContain('太棒了！当前拓扑未检测到任何跨单元调用逃逸')
    expect(stressApi.listCellEscapeReports).toHaveBeenCalledTimes(1)
  })

  it('点击执行逃逸探查扫描，调用 detectCellEscapes API 并展示违规与修复建议', async () => {
    const wrapper = mount(CellEscapeDependencyPanel, {
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
                  <slot name="bodyCell" :column="{ key: 'type' }" :record="record" />
                  <slot name="bodyCell" :column="{ key: 'path' }" :record="record" />
                  <slot name="bodyCell" :column="{ key: 'resource' }" :record="record" />
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

    const scanBtn = wrapper.findAll('button').find((b) => b.text().includes('立即执行逃逸探查扫描'))
    expect(scanBtn).toBeDefined()
    await scanBtn?.trigger('click')
    await flushPromises()

    expect(stressApi.detectCellEscapes).toHaveBeenCalledTimes(1)
    expect(wrapper.text()).toContain('SHARED_RESOURCE_CONTAMINATION')
    expect(wrapper.text()).toContain('跨单元全局共享缓存未隔离')
    expect(wrapper.text()).toContain('建议：将缓存拆分为单元私有 Redis 实例')
  })
})
