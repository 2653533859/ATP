import { mount, flushPromises } from '@vue/test-utils'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import TrafficDiffComparatorViewer from './TrafficDiffComparatorViewer.vue'
import { trafficDiffApi } from '@/api/trafficGateway'

const mockDiffReport = {
  report_id: 'diff_test_001',
  similarity_score_pct: 100.0,
  is_identical: true,
  total_differences_count: 0,
  critical_diffs_count: 0,
  warning_diffs_count: 0,
  ignored_noise_fields_count: 3,
  diff_summary: '完美一致！响应体经动态噪声过滤后与基线完全相同 (已智能忽略 3 处时间戳/UUID/Token 噪声)。',
  baseline_status_code: 200,
  replayed_status_code: 200,
  created_at: '2026-10-16T12:30:00Z',
  differences: [],
}

const mockCriticalReport = {
  report_id: 'diff_test_crit_002',
  similarity_score_pct: 35.0,
  is_identical: false,
  total_differences_count: 4,
  critical_diffs_count: 3,
  warning_diffs_count: 1,
  ignored_noise_fields_count: 2,
  diff_summary: '检出 3 处阻断级核心差异与 1 处警告差异，相似度得分仅为 35.0%，需重点排查缺失字段与业务值篡改！',
  baseline_status_code: 200,
  replayed_status_code: 200,
  created_at: '2026-10-16T12:35:00Z',
  differences: [
    {
      path: '$.data.order_id',
      diff_type: 'TYPE_CHANGED',
      severity: 'CRITICAL',
      baseline_value: 'integer',
      replayed_value: 'string',
      description: '字段类型发生漂移: 由 [integer] 变为 [string]',
    },
    {
      path: '$.data.amount',
      diff_type: 'MODIFIED',
      severity: 'CRITICAL',
      baseline_value: 100.0,
      replayed_value: 150.0,
      description: '核心金额值变更: 基线 100.0 vs 回放 150.0',
    },
    {
      path: '$.data.obsolete_tag',
      diff_type: 'DELETED',
      severity: 'CRITICAL',
      baseline_value: 'old_v1',
      replayed_value: null,
      description: '关键字段缺失: 回放响应中未找到字段 [obsolete_tag]',
    },
    {
      path: '$.data.new_feature_tag',
      diff_type: 'ADDED',
      severity: 'WARNING',
      baseline_value: null,
      replayed_value: 'beta',
      description: '新增返回字段: 回放响应中出现新字段 [new_feature_tag]',
    },
  ],
}

vi.mock('@/api/trafficGateway', () => ({
  trafficDiffApi: {
    listReports: vi.fn(),
    compareResponses: vi.fn(),
    compareTrafficIds: vi.fn(),
    getReport: vi.fn(),
    getDefaultNoiseRules: vi.fn(),
    clearReports: vi.fn(),
  },
}))

vi.mock('ant-design-vue', () => ({
  message: {
    success: vi.fn(),
    warning: vi.fn(),
    error: vi.fn(),
    info: vi.fn(),
  },
}))

vi.mock('@ant-design/icons-vue', () => ({
  ApartmentOutlined: { template: '<span>Apartment</span>' },
  ReloadOutlined: { template: '<span>Reload</span>' },
  ThunderboltOutlined: { template: '<span>Thunderbolt</span>' },
  CheckCircleOutlined: { template: '<span>Check</span>' },
}))

describe('TrafficDiffComparatorViewer.vue', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(trafficDiffApi.listReports).mockResolvedValue({
      total: 1,
      reports: [mockDiffReport as any],
    })
    vi.mocked(trafficDiffApi.compareResponses).mockResolvedValue({
      message: '响应体智能差分比对完成',
      report: mockDiffReport as any,
    })
  })

  it('renders drawer header, banner with 100% similarity, and noise filter tag', async () => {
    const wrapper = mount(TrafficDiffComparatorViewer, {
      props: {
        open: true,
      },
      global: {
        stubs: {
          'a-drawer': { template: '<div class="ant-drawer"><slot /></div>' },
          'a-tag': { template: '<span class="ant-tag"><slot /></span>' },
          'a-button': { template: '<button><slot /></button>' },
          'a-space': { template: '<div><slot /></div>' },
          'a-textarea': { template: '<textarea />' },
          'a-radio-group': { template: '<div><slot /></div>' },
          'a-radio-button': { template: '<button><slot /></button>' },
          'a-spin': { template: '<div><slot /></div>' },
          'a-table': { template: '<div class="ant-table-stub" />' },
        },
      },
    })

    await flushPromises()

    // 检查标题与说明
    expect(wrapper.text()).toContain('微服务响应体智能去噪与字段级语义差分引擎')
    expect(trafficDiffApi.listReports).toHaveBeenCalled()

    // 检查 100% 相似度与完美一致裁决
    expect(wrapper.text()).toContain('100.0%')
    expect(wrapper.text()).toContain('IDENTICAL')
    expect(wrapper.text()).toContain('自动过滤 3 处时间戳/UUID/Token 动态噪声')
  })

  it('runs compare on critical drift preset and renders differences in table', async () => {
    vi.mocked(trafficDiffApi.compareResponses).mockResolvedValue({
      message: '检出核心差异',
      report: mockCriticalReport as any,
    })

    const wrapper = mount(TrafficDiffComparatorViewer, {
      props: {
        open: true,
      },
      global: {
        stubs: {
          'a-drawer': { template: '<div class="ant-drawer"><slot /></div>' },
          'a-tag': { template: '<span class="ant-tag"><slot /></span>' },
          'a-button': { template: '<button><slot /></button>' },
          'a-space': { template: '<div><slot /></div>' },
          'a-textarea': { template: '<textarea />' },
          'a-radio-group': { template: '<div><slot /></div>' },
          'a-radio-button': { template: '<button><slot /></button>' },
          'a-spin': { template: '<div><slot /></div>' },
          'a-table': {
            props: ['dataSource'],
            template: `
              <div class="ant-table-stub">
                <div v-for="item in dataSource" :key="item.path" class="row">
                  <span class="path">{{ item.path }}</span>
                  <span class="type">{{ item.diff_type }}</span>
                  <span class="sev">{{ item.severity }}</span>
                </div>
              </div>
            `,
          },
        },
      },
    })

    await flushPromises()

    const vm = wrapper.vm as any
    await vm.applyPreset('critical_drift')
    await flushPromises()

    // 检查得分与阻断徽章
    expect(wrapper.text()).toContain('35.0%')
    expect(wrapper.text()).toContain('CRITICAL DRIFT')

    // 检查表格中呈现的差异项
    expect(wrapper.text()).toContain('$.data.order_id')
    expect(wrapper.text()).toContain('TYPE_CHANGED')
    expect(wrapper.text()).toContain('$.data.amount')
    expect(wrapper.text()).toContain('MODIFIED')
    expect(wrapper.text()).toContain('$.data.obsolete_tag')
    expect(wrapper.text()).toContain('DELETED')
  })
})
