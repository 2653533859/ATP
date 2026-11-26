import { flushPromises, mount } from '@vue/test-utils'
import { defineComponent, h } from 'vue'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import AccountSettingsView from './AccountSettingsView.vue'

const { updateMe, fetchMe, messageError, messageSuccess, messageWarning } = vi.hoisted(() => ({
  updateMe: vi.fn(),
  fetchMe: vi.fn(),
  messageError: vi.fn(),
  messageSuccess: vi.fn(),
  messageWarning: vi.fn(),
}))

vi.mock('vue-i18n', () => ({ useI18n: () => ({ t: (key: string) => key }) }))
vi.mock('ant-design-vue', () => ({
  message: { error: messageError, success: messageSuccess, warning: messageWarning },
}))
vi.mock('@/api', () => ({ authApi: { updateMe } }))
vi.mock('@/stores/auth', () => ({
  useAuthStore: () => ({
    user: { id: 2, username: 'tester', email: 'tester@example.com', role: 'tester', is_active: true },
    fetchMe,
  }),
}))

const passthrough = defineComponent({
  setup: (_props, { slots }) => () => h('div', slots.default?.()),
})

const AlertStub = defineComponent({
  props: { message: { type: String, default: '' } },
  setup: (props) => () => h('div', { class: 'alert-stub' }, props.message),
})

function mountPage() {
  const names = ['AButton', 'ACard', 'AForm', 'AFormItem', 'AInput', 'AInputPassword', 'ADivider', 'ATag']
  return mount(AccountSettingsView, {
    global: {
      stubs: {
        ...Object.fromEntries(names.map((name) => [name, passthrough])),
        AAlert: AlertStub,
      },
    },
  })
}

beforeEach(() => {
  vi.clearAllMocks()
  updateMe.mockResolvedValue({ authenticated: true })
  fetchMe.mockResolvedValue(undefined)
})

describe('AccountSettingsView', () => {
  it('initializes the form from the current user, shows role badge, and validates required fields', async () => {
    const wrapper = mountPage()
    await flushPromises()
    const vm = wrapper.vm as any

    expect(wrapper.text()).toContain('user_management.roles.tester')
    expect(wrapper.text()).toContain('account.self_manage_hint')
    expect(vm.form.username).toBe('tester')
    expect(vm.form.email).toBe('tester@example.com')
    await vm.handleSave()
    expect(messageWarning).toHaveBeenCalledWith('account.required_hint')
    expect(updateMe).not.toHaveBeenCalled()

    vm.form.username = 'tester'
    await vm.handleSave()
    expect(messageWarning).toHaveBeenLastCalledWith('account.required_hint')
    vm.form.email = 'tester@example.com'
    await vm.handleSave()
    expect(messageWarning).toHaveBeenLastCalledWith('account.required_hint')

    vm.form.current_password = 'old-password'
    vm.form.new_password = 'new-password'
    vm.form.confirm_password = 'different'
    await vm.handleSave()
    expect(messageWarning).toHaveBeenCalledWith('account.password_mismatch')
    expect(updateMe).not.toHaveBeenCalled()
  })

  it('saves profile and optional password changes, then clears secret fields', async () => {
    const wrapper = mountPage()
    await flushPromises()
    const vm = wrapper.vm as any

    vm.form.username = ' updated '
    vm.form.email = 'updated@example.com'
    vm.form.current_password = 'old-password'
    vm.form.new_password = 'new-password'
    vm.form.confirm_password = 'new-password'
    await vm.handleSave()

    expect(updateMe).toHaveBeenCalledWith({
      current_password: 'old-password',
      username: 'updated',
      email: 'updated@example.com',
      new_password: 'new-password',
    })
    expect(fetchMe).toHaveBeenCalledOnce()
    expect(messageSuccess).toHaveBeenCalledWith('account.saved')
    expect(vm.form.current_password).toBe('')
    expect(vm.form.new_password).toBe('')
    expect(vm.form.confirm_password).toBe('')

    vm.form.current_password = 'old-password'
    await vm.handleSave()
    expect(updateMe).toHaveBeenLastCalledWith({
      current_password: 'old-password',
      username: 'updated',
      email: 'updated@example.com',
    })
  })

  it('reports update failures and resets saving state', async () => {
    const wrapper = mountPage()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.form.current_password = 'old-password'
    updateMe.mockRejectedValueOnce(new Error('save failed'))

    await vm.handleSave()

    expect(messageError).toHaveBeenCalledWith('save failed')
    expect(vm.saving).toBe(false)

    updateMe.mockRejectedValueOnce('string failure')
    await vm.handleSave()
    expect(messageError).toHaveBeenCalledWith('string failure')

    updateMe.mockRejectedValueOnce({ code: 'unknown' })
    await vm.handleSave()
    expect(messageError).toHaveBeenCalledWith('account.save_failed')
  })
})
