import { mount, flushPromises } from '@vue/test-utils'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import VisualCoverageGapInspectorDrawer from './VisualCoverageGapInspectorDrawer.vue'
import { coverageLineageApi } from '@/api/coverageLineage'

const mockReport = {
  report_id: 'covrep_12345',
  project_id: 'proj_ecommerce',
  total_nodes_count: 4,
  gap_nodes_count: 2,
  overall_coverage_rate: 0.75,
  high_risk_gaps_count: 1,
  nodes: [
    {
      node_id: 'req_01',
      node_name: '用户全流程结算与支付需求',
      category: 'requirement',
      expected_branches: ['正常购买', '账户余额不足'],
      covered_branches: ['正常购买'],
      missing_branches: ['账户余额不足'],
      coverage_rate: 0.5,
      is_gap: true,
      risk_level: 'HIGH',
      linked_case_ids: ['case_001'],
      depth: 1,
      children: [],
    },
    {
      node_id: 'api_02',
      node_name: 'POST /api/v1/orders/checkout 接口',
      category: 'api_endpoint',
      expected_branches: ['200_SUCCESS'],
      covered_branches: ['200_SUCCESS'],
      missing_branches: [],
      coverage_rate: 1.0,
      is_gap: false,
      risk_level: 'NONE',
      linked_case_ids: ['case_002'],
      depth: 2,
      children: [],
    },
  ],
  edges: [],
  tree_hierarchy: [
    {
      node_id: 'req_01',
      node_name: '用户全流程结算与支付需求',
      category: 'requirement',
      expected_branches: ['正常购买', '账户余额不足'],
      covered_branches: ['正常购买'],
      missing_branches: ['账户余额不足'],
      coverage_rate: 0.5,
      is_gap: true,
      risk_level: 'HIGH',
      linked_case_ids: ['case_001'],
      depth: 1,
      children: [
        {
          node_id: 'api_02',
          node_name: 'POST /api/v1/orders/checkout 接口',
          category: 'api_endpoint',
          expected_branches: ['200_SUCCESS'],
          covered_branches: ['200_SUCCESS'],
          missing_branches: [],
          coverage_rate: 1.0,
          is_gap: false,
          risk_level: 'NONE',
          linked_case_ids: ['case_002'],
          depth: 2,
          children: [],
        },
      ],
    },
  ],
  analyzed_at: '2026-10-17T12:00:00Z',
}

vi.mock('@/api/coverageLineage', () => ({
  coverageLineageApi: {
    analyzeLineage: vi.fn(),
    synthesizeCases: vi.fn(),
  },
}))

vi.mock('ant-design-vue', () => ({
  message: {
    success: vi.fn(),
    error: vi.fn(),
  },
}))

describe('VisualCoverageGapInspectorDrawer.vue', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(coverageLineageApi.analyzeLineage).mockResolvedValue({
      message: '分析完成',
      report: mockReport as any,
    })
    vi.mocked(coverageLineageApi.synthesizeCases).mockResolvedValue({
      message: '合成完成',
      total_synthesized: 1,
      drafts: [
        {
          draft_id: 'draft_synth_01',
          source_node_id: 'req_01',
          target_branch: '账户余额不足',
          title: '[业务漏测补全] 结算支付 - 账户余额不足',
          case_type: 'hybrid',
          priority: 'P0',
          preconditions: '测试账号余额清空',
          steps: [
            {
              step_number: 1,
              step_name: '发起结算请求',
              action_type: 'http_request',
              input_payload: {},
              expected_result: '接口抛出余额不足异常',
            },
          ],
          expected_outcome: '成功捕获并拦截余额不足异常',
          suggested_tags: ['requirement', 'auto-synthesized'],
          created_at: '2026-10-17T12:00:00Z',
        },
      ],
    })
  })

  function createWrapper(props = {}) {
    return mount(VisualCoverageGapInspectorDrawer, {
      props: {
        open: true,
        projectId: 'proj_ecommerce',
        ...props,
      },
      global: {
        stubs: {
          'a-drawer': {
            template: '<div v-if="open" class="ant-drawer"><slot /></div>',
            props: ['open'],
          },
          'a-button': {
            template: '<button type="button" @click="$emit(\'click\')"><slot /></button>',
            props: ['type', 'loading', 'disabled'],
          },
          'a-tag': {
            template: '<span class="ant-tag"><slot /></span>',
          },
          'a-space': {
            template: '<div class="ant-space"><slot /></div>',
          },
          'a-switch': {
            template: '<button type="button" class="ant-switch" @click="$emit(\'update:checked\', !$attrs.checked)"><slot /></button>',
          },
          'a-spin': {
            template: '<div class="ant-spin"><slot /></div>',
            props: ['spinning'],
          },
          'a-empty': {
            template: '<div class="ant-empty"><slot /></div>',
          },
          'a-descriptions': {
            template: '<div class="ant-descriptions"><slot /></div>',
          },
          'a-descriptions-item': {
            template: '<div class="ant-descriptions-item"><slot /></div>',
            props: ['label'],
          },
        },
      },
    })
  }

  it('renders overall coverage rate and lineage tree nodes', async () => {
    const wrapper = createWrapper()
    await flushPromises()

    expect(wrapper.text()).toContain('75.0%')
    expect(wrapper.text()).toContain('全链路综合覆盖率')
    expect(wrapper.text()).toContain('总业务与契约节点: 4')
    expect(wrapper.text()).toContain('漏测盲区节点: 2')
    expect(wrapper.text()).toContain('用户全流程结算与支付需求')
  })

  it('allows clicking a node to view missing branch details', async () => {
    const wrapper = createWrapper()
    await flushPromises()

    const rows = wrapper.findAll('.lineage-tree-row')
    await rows[0].trigger('click')
    await flushPromises()

    expect(wrapper.text()).toContain('检出未被覆盖的业务/异常分支')
    expect(wrapper.text()).toContain('账户余额不足')
    expect(wrapper.text()).toContain('已覆盖正常分支:')
    expect(wrapper.text()).toContain('正常购买')
  })

  it('synthesizes test case drafts when clicking synthesize button', async () => {
    const wrapper = createWrapper()
    await flushPromises()

    const synthBtn = wrapper.find('.gaps-box-head button')
    if (synthBtn.exists()) {
      await synthBtn.trigger('click')
      await flushPromises()

      expect(coverageLineageApi.synthesizeCases).toHaveBeenCalled()
      expect(wrapper.text()).toContain('已自动推导补测用例草稿')
      expect(wrapper.text()).toContain('[业务漏测补全] 结算支付 - 账户余额不足')
      expect(wrapper.text()).toContain('P0')
    }
  })
})
