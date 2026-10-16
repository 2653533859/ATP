import { mount, flushPromises } from '@vue/test-utils'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import AdaptiveAssertionPatchModal from './AdaptiveAssertionPatchModal.vue'
import { adaptiveAssertionPatchApi } from '@/api/testSelfHealing'

const mockEnvelopePatch = {
  patch_id: 'patch_test_101',
  case_id: 'case_api_auto_patch',
  endpoint: 'POST /api/v1/orders/checkout',
  original_assertion: '$.order_id == 1001',
  patched_assertion: '$.data.order_id == 1001',
  patch_type: 'ENVELOPE_UNWRAP',
  confidence_score: 0.95,
  explanation: '检测到接口引入标准外层包装 (Envelope): 字段由 [$.order_id] 迁移至 [$.data.order_id]。',
  python_code_diff: '--- 原断言代码 (Broken)\n- assert $.order_id == 1001\n+++ 自适应自愈补丁\n+ assert $.data.order_id == 1001',
  is_applied: false,
  created_at: '2026-10-16T12:00:00Z',
}

const mockCamelPatch = {
  patch_id: 'patch_test_102',
  case_id: 'case_api_auto_patch',
  endpoint: 'GET /api/v1/users/profile',
  original_assertion: "response['user_id'] == 888",
  patched_assertion: "response['userId'] == 888",
  patch_type: 'FIELD_RENAME',
  confidence_score: 0.90,
  explanation: '检测到命名规范演变: 键名由 [user_id] 对齐至 [userId]。',
  python_code_diff: '--- 原断言\n- assert response[\'user_id\'] == 888\n+ assert response[\'userId\'] == 888',
  is_applied: false,
  created_at: '2026-10-16T12:05:00Z',
}

vi.mock('@/api/testSelfHealing', () => ({
  adaptiveAssertionPatchApi: {
    derive: vi.fn(),
    apply: vi.fn(),
    listPatches: vi.fn(),
    clearPatches: vi.fn(),
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
  CodeOutlined: { template: '<span>Code</span>' },
  ThunderboltOutlined: { template: '<span>Thunderbolt</span>' },
  CopyOutlined: { template: '<span>Copy</span>' },
  CheckOutlined: { template: '<span>Check</span>' },
  ReloadOutlined: { template: '<span>Reload</span>' },
}))

describe('AdaptiveAssertionPatchModal.vue', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(adaptiveAssertionPatchApi.derive).mockResolvedValue({
      message: '自适应断言补丁推导成功',
      patch: mockEnvelopePatch as any,
    })
    vi.mocked(adaptiveAssertionPatchApi.listPatches).mockResolvedValue({
      total: 1,
      patches: [mockEnvelopePatch as any],
    })
    vi.mocked(adaptiveAssertionPatchApi.apply).mockResolvedValue({
      message: '断言补丁已持久化应用生效',
      patch_id: 'patch_test_101',
    })
  })

  it('renders header, envelope unwrap result, code diff, and applies patch', async () => {
    const wrapper = mount(AdaptiveAssertionPatchModal, {
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
          'a-tag': { template: '<span class="ant-tag"><slot /></span>' },
          'a-tabs': { template: '<div><slot /></div>' },
          'a-tab-pane': { template: '<div><slot /></div>' },
          'a-table': { template: '<div class="ant-table-stub" />' },
        },
      },
    })

    await flushPromises()

    // 检查调用与标题
    expect(adaptiveAssertionPatchApi.derive).toHaveBeenCalled()
    expect(adaptiveAssertionPatchApi.listPatches).toHaveBeenCalled()
    expect(wrapper.text()).toContain('API 响应结构变迁自适应断言推导与自动化补丁引擎')

    // 检查推导结果
    expect(wrapper.text()).toContain('ENVELOPE_UNWRAP')
    expect(wrapper.text()).toContain('95%')
    expect(wrapper.text()).toContain('$.order_id == 1001')
    expect(wrapper.text()).toContain('$.data.order_id == 1001')

    // 检查一键应用补丁
    const vm = wrapper.vm as any
    await vm.handleApplyPatch('patch_test_101')
    expect(adaptiveAssertionPatchApi.apply).toHaveBeenCalledWith('patch_test_101')
  })

  it('switches preset to camel and updates patch type to FIELD_RENAME', async () => {
    vi.mocked(adaptiveAssertionPatchApi.derive).mockResolvedValueOnce({
      message: '推导成功',
      patch: mockEnvelopePatch as any,
    }).mockResolvedValueOnce({
      message: '推导成功',
      patch: mockCamelPatch as any,
    })

    const wrapper = mount(AdaptiveAssertionPatchModal, {
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
          'a-tag': { template: '<span class="ant-tag"><slot /></span>' },
          'a-tabs': { template: '<div><slot /></div>' },
          'a-tab-pane': { template: '<div><slot /></div>' },
          'a-table': { template: '<div class="ant-table-stub" />' },
        },
      },
    })

    await flushPromises()

    const vm = wrapper.vm as any
    await vm.applyPreset('camel')
    await flushPromises()

    expect(adaptiveAssertionPatchApi.derive).toHaveBeenCalledTimes(2)
    expect(wrapper.text()).toContain('FIELD_RENAME')
    expect(wrapper.text()).toContain("response['userId'] == 888")
  })
})
