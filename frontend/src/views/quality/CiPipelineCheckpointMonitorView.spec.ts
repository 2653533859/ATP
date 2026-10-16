import { mount, flushPromises } from '@vue/test-utils'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import CiPipelineCheckpointMonitorView from './CiPipelineCheckpointMonitorView.vue'
import { ciImpactApi } from '@/api/ciImpact'

const mockReport = {
  checkpoint_id: 'chk_test_001',
  pipeline_name: 'CI-Pipeline-Worker',
  commit_sha: 'a1b2c3d4e5f',
  pr_id: '#1024',
  exit_code: 0,
  overall_status: 'PASSED',
  stages: [
    {
      stage_name: 'Stage 1: AST 差异提取与测试智能推荐',
      status: 'PASSED',
      duration_ms: 12.3,
      summary: '从 Git Diff 提取到 2 个类与 3 个方法，智能推荐 8 个关键测试用例',
      details: { changed_files: 1, selected_cases: 8 },
    },
    {
      stage_name: 'Stage 2: 变更风险多维评分',
      status: 'PASSED',
      duration_ms: 8.5,
      summary: '评定为 LOW 低危变更',
      details: { risk_level: 'LOW' },
    },
    {
      stage_name: 'Stage 3: 偶发抖动测试集抑制过滤',
      status: 'PASSED',
      duration_ms: 5.2,
      summary: '检出 1 个抖动用例，已自动附加退避重试',
      details: { retried: 1, quarantined: 0 },
    },
    {
      stage_name: 'Stage 4: PR 全要素质量门禁裁决',
      status: 'PASSED',
      duration_ms: 6.8,
      summary: '单测通过率 100%, 变异得分 85.0%, 裁决放行 (MERGE_APPROVED)',
      details: { verdict: 'MERGE_APPROVED' },
    },
  ],
  remediation_summary: [],
  console_log_output: `[ATP CI Checkpoint] 流水线执行成功！所有质量与安全门禁全部放行！\n[EXIT CODE]: 0 (SUCCESS)`,
  executed_at: '2026-10-16T15:00:00Z',
}

vi.mock('@/api/ciImpact', () => ({
  ciImpactApi: {
    listCheckpointReports: vi.fn(),
    runPipelineCheckpoint: vi.fn(),
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
  DashboardOutlined: { template: '<span>Dashboard</span>' },
  ReloadOutlined: { template: '<span>Reload</span>' },
  PlayCircleOutlined: { template: '<span>Play</span>' },
  CheckCircleOutlined: { template: '<span>Check</span>' },
  CloseCircleOutlined: { template: '<span>Close</span>' },
  ExclamationCircleOutlined: { template: '<span>Exclamation</span>' },
  CodeOutlined: { template: '<span>Code</span>' },
  CopyOutlined: { template: '<span>Copy</span>' },
  DownOutlined: { template: '<span>Down</span>' },
}))

describe('CiPipelineCheckpointMonitorView.vue', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(ciImpactApi.listCheckpointReports).mockResolvedValue({
      total: 1,
      reports: [mockReport as any],
    })
  })

  it('renders hero banner, Exit Code 0 banner, 4 stages, and terminal window', async () => {
    const wrapper = mount(CiPipelineCheckpointMonitorView, {
      global: {
        stubs: {
          'a-tag': { template: '<span class="ant-tag"><slot /></span>' },
          'a-button': { template: '<button><slot /></button>' },
          'a-space': { template: '<div><slot /></div>' },
          'a-spin': { template: '<div><slot /></div>' },
          'a-modal': { template: '<div><slot /></div>' },
          'a-form': { template: '<form><slot /></form>' },
          'a-form-item': { template: '<div><slot /></div>' },
          'a-input': { template: '<input />' },
          'a-input-number': { template: '<input type="number" />' },
          'a-select': { template: '<select><slot /></select>' },
          'a-select-option': { template: '<option><slot /></option>' },
          'a-switch': { template: '<input type="checkbox" />' },
          'a-textarea': { template: '<textarea />' },
        },
      },
    })

    await flushPromises()

    // 检查标题与 API 调用
    expect(wrapper.text()).toContain('CI/CD 流水线 Checkpoint 检查点全景监控看板')
    expect(ciImpactApi.listCheckpointReports).toHaveBeenCalled()

    // 检查 Exit Code 横幅
    expect(wrapper.text()).toContain('EXIT CODE')
    expect(wrapper.text()).toContain('0')
    expect(wrapper.text()).toContain('SUCCESS / 放行')
    expect(wrapper.text()).toContain('CI-Pipeline-Worker')
    expect(wrapper.text()).toContain('a1b2c3d')

    // 检查 4 个阶段
    expect(wrapper.text()).toContain('Stage 1: AST 差异提取与测试智能推荐')
    expect(wrapper.text()).toContain('Stage 2: 变更风险多维评分')
    expect(wrapper.text()).toContain('Stage 3: 偶发抖动测试集抑制过滤')
    expect(wrapper.text()).toContain('Stage 4: PR 全要素质量门禁裁决')

    // 检查终端控制台日志
    expect(wrapper.text()).toContain('[EXIT CODE]: 0 (SUCCESS)')
  })

  it('supports applying preset blocked and warning', async () => {
    const wrapper = mount(CiPipelineCheckpointMonitorView, {
      global: {
        stubs: {
          'a-tag': { template: '<span class="ant-tag"><slot /></span>' },
          'a-button': { template: '<button><slot /></button>' },
          'a-space': { template: '<div><slot /></div>' },
          'a-spin': { template: '<div><slot /></div>' },
          'a-modal': { template: '<div><slot /></div>' },
          'a-form': { template: '<form><slot /></form>' },
          'a-form-item': { template: '<div><slot /></div>' },
          'a-input': { template: '<input />' },
          'a-input-number': { template: '<input type="number" />' },
          'a-select': { template: '<select><slot /></select>' },
          'a-select-option': { template: '<option><slot /></option>' },
          'a-switch': { template: '<input type="checkbox" />' },
          'a-textarea': { template: '<textarea />' },
        },
      },
    })

    await flushPromises()

    const vm = wrapper.vm as any
    vm.applyPreset('blocked')
    await wrapper.vm.$nextTick()

    expect(wrapper.text()).toContain('1')
    expect(wrapper.text()).toContain('FAILURE / 阻断')
    expect(wrapper.text()).toContain('流水线检查点硬门禁违规 (Code 1)')

    vm.applyPreset('warning')
    await wrapper.vm.$nextTick()

    expect(wrapper.text()).toContain('2')
    expect(wrapper.text()).toContain('WARNING / 告警')
  })
})
