import { mount, flushPromises } from '@vue/test-utils'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import PrCommentBotPreviewDrawer from './PrCommentBotPreviewDrawer.vue'
import { ciImpactApi } from '@/api/ciImpact'

const mockGateReport = {
  gate_id: 'gate_test_1024',
  pr_id: '#1024',
  commit_sha: 'a1b2c3d4e5f',
  author: 'dev-alice',
  target_branch: 'main',
  verdict: 'MERGE_APPROVED',
  is_mergeable: true,
  overall_compliance_score: 100.0,
  blocking_reasons: [],
  warning_reasons: [],
  evaluated_rules: [
    {
      rule_id: 'RULE_UNIT_TEST_PASS_RATE',
      rule_name: '单元测试全量通过硬门禁',
      passed: true,
      severity: 'blocking',
      measured_value: '100.0%',
      threshold_value: '>= 100.0%',
    },
    {
      rule_id: 'RULE_MUTATION_SCORE',
      rule_name: '代码变异测试充分性门禁',
      passed: true,
      severity: 'blocking',
      measured_value: '85.0%',
      threshold_value: '>= 70.0%',
    },
  ],
  remediation_steps: [],
  evaluated_at: '2026-10-16T14:00:00Z',
}

const mockMarkdown = `## 🤖 ATP CI 自动化质量门禁审核卡片\n\n### 🟢 [ATP CI Gatekeeper] PR 合并准入审核通过 (MERGE APPROVED)\n\n> 🎉 **所有质量与安全门禁指标全部达标，准许合并入主干分支！**\n`

const mockCommentPayload = {
  comment_id: 'comment_gh_999',
  pr_id: '#1024',
  platform: 'github',
  repo_name: '2653533859/ATP',
  markdown_body: mockMarkdown,
  verdict: 'MERGE_APPROVED',
  delivered_successfully: true,
  created_at: '2026-10-16T14:30:00Z',
}

vi.mock('@/api/ciImpact', () => ({
  ciImpactApi: {
    listPrGateReports: vi.fn(),
    generatePrComment: vi.fn(),
    dispatchPrComment: vi.fn(),
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
  RobotOutlined: { template: '<span>Robot</span>' },
  GithubOutlined: { template: '<span>Github</span>' },
  GitlabOutlined: { template: '<span>Gitlab</span>' },
  CodeOutlined: { template: '<span>Code</span>' },
  FileMarkdownOutlined: { template: '<span>Markdown</span>' },
  ReloadOutlined: { template: '<span>Reload</span>' },
  CopyOutlined: { template: '<span>Copy</span>' },
  SendOutlined: { template: '<span>Send</span>' },
  CheckCircleOutlined: { template: '<span>Check</span>' },
  EyeOutlined: { template: '<span>Eye</span>' },
}))

describe('PrCommentBotPreviewDrawer.vue', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(ciImpactApi.listPrGateReports).mockResolvedValue({
      total: 1,
      reports: [mockGateReport as any],
    })
    vi.mocked(ciImpactApi.generatePrComment).mockResolvedValue({
      message: 'PR 评论卡片 Markdown 生成成功',
      gate_id: 'gate_test_1024',
      markdown: mockMarkdown,
    })
    vi.mocked(ciImpactApi.dispatchPrComment).mockResolvedValue({
      message: 'PR 审查评论已投递',
      comment: mockCommentPayload as any,
    })
  })

  it('renders drawer header, markdown editor, and git preview bubble', async () => {
    const wrapper = mount(PrCommentBotPreviewDrawer, {
      props: {
        open: true,
      },
      global: {
        stubs: {
          'a-drawer': { template: '<div class="ant-drawer"><slot /></div>' },
          'a-tag': { template: '<span class="ant-tag"><slot /></span>' },
          'a-button': { template: '<button><slot /></button>' },
          'a-space': { template: '<div><slot /></div>' },
          'a-input': { template: '<input />' },
          'a-select': { template: '<select><slot /></select>' },
          'a-select-option': { template: '<option><slot /></option>' },
          'a-checkbox': { template: '<input type="checkbox" />' },
          'a-textarea': { template: '<textarea />' },
        },
      },
    })

    await flushPromises()

    // 检查标题与机制说明
    expect(wrapper.text()).toContain('PR Reviewer 交互式机器评论卡片自动广播与多平台发布')

    // 检查 API 调用
    expect(ciImpactApi.listPrGateReports).toHaveBeenCalled()
    expect(ciImpactApi.generatePrComment).toHaveBeenCalledWith(expect.objectContaining({
      gate_id: 'gate_test_1024',
    }))

    // 检查仿真渲染卡片
    expect(wrapper.text()).toContain('atp-robot')
    expect(wrapper.text()).toContain('MERGE APPROVED')
    expect(wrapper.text()).toContain('单元测试全量通过硬门禁')
    expect(wrapper.text()).toContain('代码变异测试充分性门禁')
  })

  it('dispatches comment and displays success feedback alert', async () => {
    const wrapper = mount(PrCommentBotPreviewDrawer, {
      props: {
        open: true,
      },
      global: {
        stubs: {
          'a-drawer': { template: '<div class="ant-drawer"><slot /></div>' },
          'a-tag': { template: '<span class="ant-tag"><slot /></span>' },
          'a-button': { template: '<button><slot /></button>' },
          'a-space': { template: '<div><slot /></div>' },
          'a-input': { template: '<input />' },
          'a-select': { template: '<select><slot /></select>' },
          'a-select-option': { template: '<option><slot /></option>' },
          'a-checkbox': { template: '<input type="checkbox" />' },
          'a-textarea': { template: '<textarea />' },
        },
      },
    })

    await flushPromises()

    const vm = wrapper.vm as any
    await vm.handleDispatch()

    expect(ciImpactApi.dispatchPrComment).toHaveBeenCalledWith(expect.objectContaining({
      gate_id: 'gate_test_1024',
      repo_name: '2653533859/ATP',
      platform: 'github',
    }))

    await wrapper.vm.$nextTick()
    expect(wrapper.text()).toContain('评论卡片已成功推送至 GITHUB PR 评论区')
  })
})
