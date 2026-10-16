import { mount, flushPromises } from '@vue/test-utils'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import GitDiffAstViewerDrawer from './GitDiffAstViewerDrawer.vue'
import { ciImpactApi } from '@/api/ciImpact'

const mockReport = {
  analysis_id: 'diff_ast_demo_123',
  diff_summary: {
    total_files_changed: 2,
    total_added_lines: 15,
    total_deleted_lines: 4,
    net_lines_delta: 11,
    affected_symbols_count: 3,
    affected_routes_count: 2,
  },
  changed_files: [
    {
      file_path: 'app/api/orders.py',
      is_new_file: false,
      is_deleted_file: false,
      added_lines_count: 10,
      deleted_lines_count: 2,
      changed_line_numbers: [10, 11, 25],
    },
  ],
  affected_symbols: [
    {
      symbol_id: 'app/api/orders.py:calculate_discount',
      symbol_type: 'function',
      symbol_name: 'calculate_discount',
      file_path: 'app/api/orders.py',
      start_line: 8,
      end_line: 15,
      changed_lines: [10, 11],
      change_kind: 'MODIFIED',
      parent_class: null,
      route_method: null,
      route_path: null,
      decorators: [],
      parameters: ['price'],
    },
    {
      symbol_id: 'app/api/orders.py:create_order_endpoint',
      symbol_type: 'route_endpoint',
      symbol_name: 'create_order_endpoint',
      file_path: 'app/api/orders.py',
      start_line: 25,
      end_line: 32,
      changed_lines: [25],
      change_kind: 'MODIFIED',
      parent_class: null,
      route_method: 'POST',
      route_path: '/api/v1/orders/create',
      decorators: ['@router.post'],
      parameters: ['payload'],
    },
  ],
  affected_routes: [
    {
      route_method: 'POST',
      route_path: '/api/v1/orders/create',
      handler_function: 'create_order_endpoint',
      file_path: 'app/api/orders.py',
      symbol_id: 'app/api/orders.py:create_order_endpoint',
      changed_lines_count: 2,
    },
  ],
  analyzed_at: '2026-10-16T10:00:00Z',
}

vi.mock('@/api/ciImpact', () => ({
  ciImpactApi: {
    listDiffAstReports: vi.fn(),
    getDiffAstReport: vi.fn(),
    analyzeDiffAst: vi.fn(),
  },
}))

vi.mock('ant-design-vue', () => ({
  message: {
    success: vi.fn(),
    error: vi.fn(),
  },
}))

vi.mock('@ant-design/icons-vue', () => ({
  CodeOutlined: { template: '<span>Code</span>' },
  ReloadOutlined: { template: '<span>Reload</span>' },
  ThunderboltOutlined: { template: '<span>Thunderbolt</span>' },
}))

describe('GitDiffAstViewerDrawer.vue', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(ciImpactApi.listDiffAstReports).mockResolvedValue({
      total: 1,
      reports: [mockReport as any],
    })
    vi.mocked(ciImpactApi.getDiffAstReport).mockResolvedValue(mockReport as any)
    vi.mocked(ciImpactApi.analyzeDiffAst).mockResolvedValue({
      message: 'Diff AST 解析完成',
      report: mockReport as any,
    })
  })

  it('renders drawer header, KPI cards, and AST symbols/routes tables', async () => {
    const wrapper = mount(GitDiffAstViewerDrawer, {
      props: {
        open: true,
      },
      global: {
        stubs: {
          'a-drawer': { template: '<div class="ant-drawer"><slot /></div>' },
          'a-tag': { template: '<span class="ant-tag"><slot /></span>' },
          'a-space': { template: '<div><slot /></div>' },
          'a-button': { template: '<button><slot /></button>' },
          'a-select': { template: '<select><slot /></select>' },
          'a-card': { template: '<div class="ant-card"><slot /></div>' },
          'a-tabs': { template: '<div><slot /></div>' },
          'a-tab-pane': { template: '<div><slot /></div>' },
          'a-textarea': { template: '<textarea />' },
          'a-table': {
            props: ['dataSource'],
            template: `
              <div class="ant-table-stub">
                <div v-for="item in dataSource" :key="item.symbol_id || item.file_path" class="row">
                  <span v-if="item.symbol_name">{{ item.symbol_name }}</span>
                  <span v-if="item.route_path">{{ item.route_path }}</span>
                  <span v-if="item.file_path">{{ item.file_path }}</span>
                </div>
              </div>
            `,
          },
        },
      },
    })

    await flushPromises()

    // 验证标题与统计卡片
    expect(wrapper.text()).toContain('源码级 Diff 语法树 (AST) 语义提取引擎')
    expect(wrapper.text()).toContain('+15')
    expect(wrapper.text()).toContain('-4')
    expect(wrapper.text()).toContain('3')
    expect(wrapper.text()).toContain('2')

    // 验证 AST 符号与路由表格内容
    expect(wrapper.text()).toContain('calculate_discount')
    expect(wrapper.text()).toContain('/api/v1/orders/create')

    expect(ciImpactApi.listDiffAstReports).toHaveBeenCalled()
  })

  it('triggers AST analysis on button click', async () => {
    const wrapper = mount(GitDiffAstViewerDrawer, {
      props: {
        open: true,
      },
      global: {
        stubs: {
          'a-drawer': { template: '<div class="ant-drawer"><slot /></div>' },
          'a-tag': { template: '<span class="ant-tag"><slot /></span>' },
          'a-space': { template: '<div><slot /></div>' },
          'a-button': { template: '<button><slot /></button>' },
          'a-select': { template: '<select><slot /></select>' },
          'a-card': { template: '<div class="ant-card"><slot /></div>' },
          'a-tabs': { template: '<div><slot /></div>' },
          'a-tab-pane': { template: '<div><slot /></div>' },
          'a-textarea': { template: '<textarea />' },
          'a-table': { template: '<div class="ant-table-stub" />' },
        },
      },
    })

    await flushPromises()

    const vm = wrapper.vm as any
    await vm.handleRunAnalyze()

    expect(ciImpactApi.analyzeDiffAst).toHaveBeenCalledWith(expect.objectContaining({
      diff_text: expect.any(String),
    }))
  })
})
