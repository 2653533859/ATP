import { mount, flushPromises } from '@vue/test-utils'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import CrossPlatformMigrationModal from './CrossPlatformMigrationModal.vue'
import { crossPlatformMigrationApi } from '@/api/crossPlatformMigration'

const mockMappingResult = {
  mapping_id: 'map_test_123',
  case_id: 'case_migrated_01',
  case_name: 'Web 加购结算用例 ➔ Android 迁移',
  source_platform: 'web',
  target_platform: 'android',
  total_steps: 2,
  mapped_steps_count: 2,
  average_confidence: 0.92,
  unresolved_count: 0,
  unresolved_step_ids: [],
  mapped_steps: [
    {
      step_id: 'step_1',
      action_type: 'TAP',
      source_platform: 'web',
      target_platform: 'android',
      source_locator: { locator_type: 'css', locator_value: '#login-btn', element_text: '登录' },
      target_locator: { locator_type: 'resource_id', locator_value: 'com.shop.app:id/btn_login_submit', element_text: '立即登录' },
      parameters: {},
      confidence: 0.95,
      notes: '从 [web] 自动映射转译至 [android]',
    },
    {
      step_id: 'step_2',
      action_type: 'FILL_TEXT',
      source_platform: 'web',
      target_platform: 'android',
      source_locator: { locator_type: 'id', locator_value: 'username-input', element_text: '手机号' },
      target_locator: { locator_type: 'resource_id', locator_value: 'com.shop.app:id/edit_account_field', element_text: '请输入手机号' },
      parameters: { text: '13800138000' },
      confidence: 0.89,
      notes: '从 [web] 自动映射转译至 [android]',
    },
  ],
  created_at: '2026-10-17 12:00:00',
}

const stubs = {
  'a-modal': { template: '<div class="ant-modal-stub"><slot /></div>' },
  'a-button': { template: '<button><slot /></button>' },
  'a-tag': { template: '<span class="ant-tag-stub"><slot /></span>' },
  'a-radio-group': { template: '<div><slot /></div>' },
  'a-radio-button': { template: '<button><slot /></button>' },
}

describe('CrossPlatformMigrationModal.vue', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.spyOn(crossPlatformMigrationApi, 'translateCase').mockResolvedValue({
      message: '转译成功',
      result: mockMappingResult as any,
    })
  })

  it('renders modal banner, platform selectors, and initial source steps when open', () => {
    const wrapper = mount(CrossPlatformMigrationModal, {
      props: {
        open: true,
      },
      global: { stubs },
    })

    expect(wrapper.text()).toContain('Cross-Platform Test Migration Engine')
    expect(wrapper.text()).toContain('源端平台 (Source):')
    expect(wrapper.text()).toContain('目标端平台 (Target):')
    expect(wrapper.text()).toContain('待迁移测试步骤序列')
  })

  it('loads preset scenario when clicking preset scenario button', async () => {
    const wrapper = mount(CrossPlatformMigrationModal, {
      props: {
        open: true,
      },
      global: { stubs },
    })

    const presetBtns = wrapper.findAll('.preset-btn')
    expect(presetBtns.length).toBeGreaterThan(0)

    // 点击第二个预设: iOS 极速支付 ➔ Web H5 端
    await presetBtns[1].trigger('click')

    const vm = wrapper.vm as any
    expect(vm.sourcePlatform).toBe('ios')
    expect(vm.targetPlatform).toBe('web')
    expect(vm.customCaseName).toContain('iOS 快捷支付用例 ➔ Web 迁移')
  })

  it('triggers translateCase API and displays mapped steps with confidence badges', async () => {
    const wrapper = mount(CrossPlatformMigrationModal, {
      props: {
        open: true,
      },
      global: { stubs },
    })

    const translateBtn = wrapper.findAll('button').find((b) => b.text().includes('开始跨端智能转译'))
    expect(translateBtn).toBeDefined()
    await translateBtn!.trigger('click')
    await flushPromises()

    expect(crossPlatformMigrationApi.translateCase).toHaveBeenCalledWith(
      expect.objectContaining({
        source_platform: 'web',
        target_platform: 'android',
      })
    )

    // 查验转译结果展示
    expect(wrapper.text()).toContain('平均置信度:')
    expect(wrapper.text()).toContain('92.0%')
    expect(wrapper.text()).toContain('com.shop.app:id/btn_login_submit')
    expect(wrapper.text()).toContain('com.shop.app:id/edit_account_field')
  })

  it('emits migrated event and closes modal when clicking 保存并生成目标端新用例', async () => {
    const wrapper = mount(CrossPlatformMigrationModal, {
      props: {
        open: true,
      },
      global: { stubs },
    })

    // 先执行转译
    const translateBtn = wrapper.findAll('button').find((b) => b.text().includes('开始跨端智能转译'))
    await translateBtn!.trigger('click')
    await flushPromises()

    // 点击保存
    const saveBtn = wrapper.findAll('button').find((b) => b.text().includes('保存并生成目标端新用例'))
    expect(saveBtn).toBeDefined()
    await saveBtn!.trigger('click')

    expect(wrapper.emitted('migrated')).toBeDefined()
    expect(wrapper.emitted('migrated')![0][0]).toEqual(mockMappingResult)
    expect(wrapper.emitted('update:open')![0]).toEqual([false])
  })
})
