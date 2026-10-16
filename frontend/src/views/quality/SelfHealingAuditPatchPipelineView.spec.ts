import { mount, flushPromises } from '@vue/test-utils'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import SelfHealingAuditPatchPipelineView from './SelfHealingAuditPatchPipelineView.vue'
import { selfHealingPipelineApi, type HealingAuditPipelineReport } from '@/api/testSelfHealing'

const mockReport: HealingAuditPipelineReport = {
  pipeline_id: 'hlp_audit_test_9001',
  case_id: 'case_ui_cart_button',
  case_name: '电商下单流程 UI 加购按钮定位自愈',
  failure_category: 'UI_LOCATOR_DRIFT',
  patch_type: 'LOCATOR_HEALING',
  original_code: "page.click(\"//button[@id='submit-btn']\")",
  healed_code: "page.click(\"//button[@id='checkout-submit-active']\")",
  patch_diff: '--- 原用例代码\n- page.click("//button[@id=\'submit-btn\']")\n+++ 自适应自愈补丁\n+ page.click("//button[@id=\'checkout-submit-active\']")',
  diff_sha256: 'a1b2c3d4e5f67890123456789abcdef0123456789abcdef0123456789abcdef0',
  dry_run_verified: true,
  is_applied: true,
  is_rolled_back: false,
  stages: [
    {
      stage_index: 1,
      stage_name: 'Stage 1: 故障模式诊断',
      status: 'PASSED',
      duration_ms: 12,
      summary: 'DOM 节点定位符失效，按钮属性已变更',
      details: { error_type: 'UI_LOCATOR_DRIFT' },
    },
    {
      stage_index: 2,
      stage_name: 'Stage 2: 动态补丁合成',
      status: 'PASSED',
      duration_ms: 8,
      summary: '生成自适应定位选择器',
      details: { patch_type: 'LOCATOR_HEALING' },
    },
    {
      stage_index: 3,
      stage_name: 'Stage 3: 隔离沙箱热试跑',
      status: 'PASSED',
      duration_ms: 14,
      summary: '隔离沙箱环境重放通过，目标元素已正确定位',
      details: { verified: true },
    },
    {
      stage_index: 4,
      stage_name: 'Stage 4: 防篡改审计存证与应用',
      status: 'PASSED',
      duration_ms: 5,
      summary: 'SHA-256 存证指纹生成并持久化生效',
      details: { is_applied: true },
    },
  ],
  total_duration_ms: 42,
  verdict_summary: '自愈流水线执行完成并自动生效',
  created_at: '2026-10-16T12:00:00Z',
}

vi.mock('@/api/testSelfHealing', () => ({
  selfHealingPipelineApi: {
    execute: vi.fn(),
    rollback: vi.fn(),
    listReports: vi.fn(),
    getReport: vi.fn(),
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
  SafetyCertificateOutlined: { template: '<span>Safety</span>' },
  ThunderboltOutlined: { template: '<span>Thunderbolt</span>' },
  ReloadOutlined: { template: '<span>Reload</span>' },
  DeleteOutlined: { template: '<span>Delete</span>' },
  CopyOutlined: { template: '<span>Copy</span>' },
  UndoOutlined: { template: '<span>Undo</span>' },
  AuditOutlined: { template: '<span>Audit</span>' },
  ControlOutlined: { template: '<span>Control</span>' },
  FileProtectOutlined: { template: '<span>Protect</span>' },
}))

describe('SelfHealingAuditPatchPipelineView.vue', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(selfHealingPipelineApi.listReports).mockResolvedValue({
      total: 1,
      reports: [mockReport],
    })
    vi.mocked(selfHealingPipelineApi.execute).mockResolvedValue({
      message: '四阶段自愈流水线执行完成',
      report: mockReport,
    })
    vi.mocked(selfHealingPipelineApi.rollback).mockResolvedValue({
      message: '自愈补丁已安全原子回滚',
      pipeline_id: 'hlp_audit_test_9001',
    })
  })

  it('renders header, 4-stage pipeline banner, KPI cards, and SHA-256 fingerprint', async () => {
    const wrapper = mount(SelfHealingAuditPatchPipelineView, {
      global: {
        stubs: {
          'a-button': { template: '<button><slot /></button>' },
          'a-space': { template: '<div><slot /></div>' },
          'a-popconfirm': { template: '<div><slot /></div>' },
          'a-row': { template: '<div><slot /></div>' },
          'a-col': { template: '<div><slot /></div>' },
          'a-radio-group': { template: '<div><slot /></div>' },
          'a-radio-button': { template: '<button><slot /></button>' },
          'a-input': { template: '<input />' },
          'a-textarea': { template: '<textarea />' },
          'a-checkbox': { template: '<input type="checkbox" />' },
          'a-tag': { template: '<span class="ant-tag"><slot /></span>' },
          'a-table': { template: '<div class="ant-table-stub" />' },
          'a-tooltip': { template: '<div><slot /></div>' },
          'a-empty': { template: '<div><slot /></div>' },
        },
      },
    })

    await flushPromises()

    expect(selfHealingPipelineApi.listReports).toHaveBeenCalled()
    expect(wrapper.text()).toContain('端到端测试自愈全流程审计追踪与一键回滚全景大盘')

    // 校验四阶段展示
    expect(wrapper.text()).toContain('Stage 1: 故障模式诊断')
    expect(wrapper.text()).toContain('Stage 2: 动态补丁合成')
    expect(wrapper.text()).toContain('Stage 3: 隔离沙箱热试跑')
    expect(wrapper.text()).toContain('Stage 4: 防篡改审计存证与应用')

    // 校验 SHA-256 存证指纹
    expect(wrapper.text()).toContain('a1b2c3d4e5f67890123456789abcdef0123456789abcdef0123456789abcdef0')
  })

  it('triggers self-healing pipeline execution and performs atomic rollback', async () => {
    const wrapper = mount(SelfHealingAuditPatchPipelineView, {
      global: {
        stubs: {
          'a-button': { template: '<button><slot /></button>' },
          'a-space': { template: '<div><slot /></div>' },
          'a-popconfirm': { template: '<div><slot /></div>' },
          'a-row': { template: '<div><slot /></div>' },
          'a-col': { template: '<div><slot /></div>' },
          'a-radio-group': { template: '<div><slot /></div>' },
          'a-radio-button': { template: '<button><slot /></button>' },
          'a-input': { template: '<input />' },
          'a-textarea': { template: '<textarea />' },
          'a-checkbox': { template: '<input type="checkbox" />' },
          'a-tag': { template: '<span class="ant-tag"><slot /></span>' },
          'a-table': { template: '<div class="ant-table-stub" />' },
          'a-tooltip': { template: '<div><slot /></div>' },
          'a-empty': { template: '<div><slot /></div>' },
        },
      },
    })

    await flushPromises()

    const vm = wrapper.vm as any
    await vm.handleExecuteCurrent()
    await flushPromises()

    expect(selfHealingPipelineApi.execute).toHaveBeenCalled()

    // 触发原子回滚
    await vm.handleRollback('hlp_audit_test_9001')
    await flushPromises()

    expect(selfHealingPipelineApi.rollback).toHaveBeenCalledWith('hlp_audit_test_9001')
    expect(vm.latestReport.is_rolled_back).toBe(true)
  })
})
