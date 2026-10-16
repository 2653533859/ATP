import { mount, flushPromises } from '@vue/test-utils'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import IncidentKnowledgeFingerprintDrawer from './IncidentKnowledgeFingerprintDrawer.vue'
import { incidentFingerprintApi } from '@/api/rootCauseDiagnosis'

const mockMatchedReport = {
  query_fingerprint_tokens: ['order', 'service', 'deadlock', 'found'],
  matches_count: 1,
  matches: [
    {
      incident: {
        incident_id: 'inc_mysql_deadlock',
        title: 'MySQL 订单结算事务行锁并发争用死锁',
        category: 'DATABASE',
        service_name: 'order-service',
        error_pattern: 'Deadlock found when trying to get lock',
        signature_tokens: ['deadlock', 'found', 'lock'],
        root_cause_explanation: '高并发下循环等待死锁',
        verified_resolution: '统一加锁顺序: 必须按 order_id 升序排列加锁。',
        external_ticket_ref: 'JIRA-4891',
        occurrences_count: 5,
        created_at: '2026-10-16T12:00:00Z',
      },
      similarity_score: 0.85,
      match_tier: 'HIGH_SIMILARITY',
      matched_tokens: ['deadlock', 'found', 'order', 'service'],
    },
  ],
  best_match_resolution: '统一加锁顺序: 必须按 order_id 升序排列加锁。',
  recommendation_summary: '成功匹配到 1 条历史相似缺陷！最高相似度达到 85.0% (HIGH_SIMILARITY)。',
  matched_at: '2026-10-16T12:00:00Z',
}

const mockUnmatchedReport = {
  query_fingerprint_tokens: ['unknown', 'crash'],
  matches_count: 0,
  matches: [],
  best_match_resolution: null,
  recommendation_summary: '在知识库中未检索到高度相似的历史缺陷，可能属于新引入问题。',
  matched_at: '2026-10-16T12:05:00Z',
}

const mockIncidents = [
  {
    incident_id: 'inc_mysql_deadlock',
    title: 'MySQL 订单结算事务行锁并发争用死锁',
    category: 'DATABASE',
    service_name: 'order-service',
    error_pattern: 'Deadlock found',
    signature_tokens: ['deadlock'],
    root_cause_explanation: '循环等待死锁',
    verified_resolution: '统一加锁顺序',
    external_ticket_ref: 'JIRA-4891',
    occurrences_count: 5,
    created_at: '2026-10-16T12:00:00Z',
  },
]

vi.mock('@/api/rootCauseDiagnosis', () => ({
  incidentFingerprintApi: {
    match: vi.fn(),
    registerIncident: vi.fn(),
    listIncidents: vi.fn(),
    deleteIncident: vi.fn(),
    clearIncidents: vi.fn(),
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
  BookOutlined: { template: '<span>Book</span>' },
  ThunderboltOutlined: { template: '<span>Thunderbolt</span>' },
  CopyOutlined: { template: '<span>Copy</span>' },
  ReloadOutlined: { template: '<span>Reload</span>' },
}))

describe('IncidentKnowledgeFingerprintDrawer.vue', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(incidentFingerprintApi.match).mockResolvedValue(mockMatchedReport as any)
    vi.mocked(incidentFingerprintApi.listIncidents).mockResolvedValue({
      total: 1,
      incidents: mockIncidents as any,
    })
    vi.mocked(incidentFingerprintApi.registerIncident).mockResolvedValue({
      message: '录入成功',
      incident: mockIncidents[0] as any,
    })
    vi.mocked(incidentFingerprintApi.deleteIncident).mockResolvedValue({
      message: '已删除',
      incident_id: 'inc_mysql_deadlock',
    })
  })

  it('renders header, match banner, verified resolution, and matched tokens', async () => {
    const wrapper = mount(IncidentKnowledgeFingerprintDrawer, {
      props: {
        open: true,
      },
      global: {
        stubs: {
          'a-drawer': { template: '<div class="ant-drawer"><slot /></div>' },
          'a-button': { template: '<button><slot /></button>' },
          'a-space': { template: '<div><slot /></div>' },
          'a-input': { template: '<input />' },
          'a-textarea': { template: '<textarea />' },
          'a-input-number': { template: '<input type="number" />' },
          'a-tag': { template: '<span class="ant-tag"><slot /></span>' },
          'a-tabs': { template: '<div><slot /></div>' },
          'a-tab-pane': { template: '<div><slot /></div>' },
          'a-popconfirm': { template: '<div><slot /></div>' },
          'a-table': { template: '<div class="ant-table-stub" />' },
        },
      },
    })

    await flushPromises()

    // 检查调用与标题
    expect(incidentFingerprintApi.match).toHaveBeenCalled()
    expect(incidentFingerprintApi.listIncidents).toHaveBeenCalled()
    expect(wrapper.text()).toContain('历史已知缺陷向量指纹特征相似度检索与经验推荐')

    // 检查匹配横幅与解决方案
    expect(wrapper.text()).toContain('命中 1 条历史相似缺陷')
    expect(wrapper.text()).toContain('统一加锁顺序: 必须按 order_id 升序排列加锁')
    expect(wrapper.text()).toContain('HIGH_SIMILARITY (85%)')
    expect(wrapper.text()).toContain('JIRA-4891')
  })

  it('switches preset to new_bug and checks unmatched state', async () => {
    vi.mocked(incidentFingerprintApi.match).mockResolvedValueOnce(mockMatchedReport as any).mockResolvedValueOnce(mockUnmatchedReport as any)

    const wrapper = mount(IncidentKnowledgeFingerprintDrawer, {
      props: {
        open: true,
      },
      global: {
        stubs: {
          'a-drawer': { template: '<div class="ant-drawer"><slot /></div>' },
          'a-button': { template: '<button><slot /></button>' },
          'a-space': { template: '<div><slot /></div>' },
          'a-input': { template: '<input />' },
          'a-textarea': { template: '<textarea />' },
          'a-input-number': { template: '<input type="number" />' },
          'a-tag': { template: '<span class="ant-tag"><slot /></span>' },
          'a-tabs': { template: '<div><slot /></div>' },
          'a-tab-pane': { template: '<div><slot /></div>' },
          'a-popconfirm': { template: '<div><slot /></div>' },
          'a-table': { template: '<div class="ant-table-stub" />' },
        },
      },
    })

    await flushPromises()

    const vm = wrapper.vm as any
    await vm.applyPreset('new_bug')
    await flushPromises()

    expect(incidentFingerprintApi.match).toHaveBeenCalledTimes(2)
    expect(wrapper.text()).toContain('未检索到相似已知缺陷')

    // 测试删除条目
    await vm.handleDeleteIncident('inc_mysql_deadlock')
    expect(incidentFingerprintApi.deleteIncident).toHaveBeenCalledWith('inc_mysql_deadlock')
  })
})
