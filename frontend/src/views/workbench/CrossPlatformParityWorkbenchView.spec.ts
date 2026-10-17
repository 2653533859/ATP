import { mount, flushPromises } from '@vue/test-utils'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import CrossPlatformParityWorkbenchView from './CrossPlatformParityWorkbenchView.vue'
import { crossPlatformMigrationApi } from '@/api/crossPlatformMigration'

const mockMigrations = [
  {
    mapping_id: 'map_web_and_01',
    case_id: 'case_web_checkout_01',
    case_name: 'Web 登录加购与结算全链路用例',
    source_platform: 'web',
    target_platform: 'android',
    total_steps: 4,
    mapped_steps_count: 4,
    average_confidence: 0.945,
    unresolved_count: 0,
    unresolved_step_ids: [],
    mapped_steps: [],
    created_at: '2026-10-17 12:30:00',
  },
]

const mockReports = [
  {
    report_id: 'parrep_checkout_center_01',
    screen_name: '收银台结算中心',
    source_platform: 'ios',
    target_platform: 'android',
    composite_score: 82.5,
    grade: 'GRADE_B' as const,
    verdict: 'WARN' as const,
    scores: {
      control_alignment_score: 75.0,
      core_business_score: 85.0,
      text_consistency_score: 90.0,
      interaction_compatibility_score: 100.0,
      weighted_composite_score: 82.5,
    },
    matrix_summary: {
      total_source_nodes: 4,
      total_target_nodes: 4,
      aligned_pairs_count: 3,
      alignment_rate: 0.75,
    },
    discrepancy_summary: {
      total_gaps_count: 2,
      critical_count: 0,
      high_count: 1,
      medium_count: 1,
      low_count: 0,
    },
    gaps: [],
    executive_summary: '【带险放行】双端一致性综合评分为 82.5 分',
    generated_at: '2026-10-17 12:00:00',
  },
]

const stubs = {
  'a-button': { template: '<button type="button" @click="$emit(\'click\')"><slot /></button>' },
  'a-card': { template: '<div class="ant-card"><slot /></div>' },
  'a-tag': { template: '<span class="ant-tag"><slot /></span>' },
  'a-space': { template: '<div class="ant-space"><slot /></div>' },
  'a-tabs': { template: '<div class="ant-tabs"><slot /></div>' },
  'a-tab-pane': { template: '<div class="ant-tab-pane"><slot /></div>' },
  'a-select': { template: '<select><slot /></select>' },
  'a-select-option': { template: '<option><slot /></option>' },
  'a-input-search': {
    template: '<input class="ant-input-search" :value="value" @input="$emit(\'update:value\', $event.target.value)" />',
    props: ['value'],
  },
  'a-table': {
    template: `
      <div class="ant-table">
        <div v-for="item in dataSource" :key="item.mapping_id || item.report_id" class="table-row">
          <span>{{ item.mapping_id || item.report_id }}</span>
          <span>{{ item.case_name || item.screen_name }}</span>
          <button class="action-btn" @click="$parent.$emit('action', item)">操作</button>
        </div>
      </div>
    `,
    props: ['dataSource', 'columns'],
  },
  CrossPlatformMigrationModal: {
    template: '<div v-if="open" class="cross-platform-migration-modal-stub" />',
    props: ['open', 'sourceCaseName'],
  },
  ParityAlignmentDiffDrawer: {
    template: '<div v-if="open" class="parity-alignment-diff-drawer-stub" />',
    props: ['open', 'reportId'],
  },
}

describe('CrossPlatformParityWorkbenchView.vue', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.spyOn(crossPlatformMigrationApi, 'listHistory').mockResolvedValue({
      total: 1,
      history: mockMigrations as any,
    })
    vi.spyOn(crossPlatformMigrationApi, 'listParityReports').mockResolvedValue({
      total: 1,
      reports: mockReports as any,
    })
  })

  function createWrapper() {
    return mount(CrossPlatformParityWorkbenchView, {
      global: { stubs },
    })
  }

  it('renders workbench title and 4 Bento KPI cards', async () => {
    const wrapper = createWrapper()
    await flushPromises()

    expect(wrapper.text()).toContain('跨端测试智能迁移与双端一致性对齐中台')
    expect(wrapper.text()).toContain('跨端迁移转译成功率')
    expect(wrapper.text()).toContain('98.6%')
    expect(wrapper.text()).toContain('跨端纳管对齐业务页面')
    expect(wrapper.text()).toContain('双端一致性发布准入率')
    expect(wrapper.text()).toContain('92.4%')
    expect(wrapper.text()).toContain('拦截高危差异红斑数')
  })

  it('loads migrations and parity reports on mount', async () => {
    const wrapper = createWrapper()
    await flushPromises()

    expect(crossPlatformMigrationApi.listHistory).toHaveBeenCalled()
    expect(crossPlatformMigrationApi.listParityReports).toHaveBeenCalled()

    expect(wrapper.text()).toContain('map_web_and_01')
    expect(wrapper.text()).toContain('Web 登录加购与结算全链路用例')
  })

  it('opens CrossPlatformMigrationModal when clicking 发起用例跨端迁移', async () => {
    const wrapper = createWrapper()
    await flushPromises()

    const migBtn = wrapper.findAll('header button').find((b) => b.text().includes('发起用例跨端迁移'))
    expect(migBtn).toBeDefined()
    await migBtn!.trigger('click')
    await flushPromises()

    expect(wrapper.find('.cross-platform-migration-modal-stub').exists()).toBe(true)
  })

  it('opens ParityAlignmentDiffDrawer when clicking 双端功能一致性透视', async () => {
    const wrapper = createWrapper()
    await flushPromises()

    const parityBtn = wrapper.findAll('header button').find((b) => b.text().includes('双端功能一致性透视'))
    expect(parityBtn).toBeDefined()
    await parityBtn!.trigger('click')
    await flushPromises()

    expect(wrapper.find('.parity-alignment-diff-drawer-stub').exists()).toBe(true)
  })

  it('opens ParityAlignmentDiffDrawer with reportId when calling viewParityDetail', async () => {
    const wrapper = createWrapper()
    await flushPromises()

    const vm = wrapper.vm as any
    vm.viewParityDetail('parrep_checkout_center_01')
    await wrapper.vm.$nextTick()

    expect(wrapper.find('.parity-alignment-diff-drawer-stub').exists()).toBe(true)
    expect(vm.selectedReportId).toBe('parrep_checkout_center_01')
  })
})
