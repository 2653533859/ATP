import { flushPromises, mount } from '@vue/test-utils'
import { defineComponent, h } from 'vue'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import UserManagementView from './UserManagementView.vue'

const { userList, userCreate, userUpdate, initialPassword, updateInitialPassword, messageError, messageSuccess, messageWarning } = vi.hoisted(() => ({
  userList: vi.fn(),
  userCreate: vi.fn(),
  userUpdate: vi.fn(),
  initialPassword: vi.fn(),
  updateInitialPassword: vi.fn(),
  messageError: vi.fn(),
  messageSuccess: vi.fn(),
  messageWarning: vi.fn(),
}))

vi.mock('vue-i18n', () => ({ useI18n: () => ({ t: (key: string) => key }) }))
vi.mock('@ant-design/icons-vue', () => ({ PlusOutlined: defineComponent({ name: 'PlusOutlined', setup: () => () => null }) }))
vi.mock('ant-design-vue', () => ({
  message: { error: messageError, success: messageSuccess, warning: messageWarning },
}))
vi.mock('@/api', () => ({
  userApi: { list: userList, create: userCreate, update: userUpdate, initialPassword, updateInitialPassword },
}))

const passthrough = defineComponent({
  setup: (_props, { slots }) => () => h('div', slots.default?.()),
})

const USERS = [
  { id: 1, username: 'admin', email: 'admin@example.com', role: 'admin', is_active: true },
  { id: 2, username: 'tester', email: 'tester@example.com', role: 'tester', is_active: false },
]

function mountPage() {
  const names = [
    'AButton', 'ACard', 'AForm', 'AFormItem', 'AInput', 'AInputSearch', 'AInputPassword', 'AModal',
    'ASelect', 'ASelectOption', 'ASwitch', 'ATable', 'ATag',
  ]
  return mount(UserManagementView, {
    global: { stubs: Object.fromEntries(names.map((name) => [name, passthrough])) },
  })
}

beforeEach(() => {
  vi.clearAllMocks()
  userList.mockResolvedValue(USERS)
  userCreate.mockResolvedValue(USERS[0])
  userUpdate.mockResolvedValue(USERS[0])
  initialPassword.mockResolvedValue({ password: 'example-default' })
  updateInitialPassword.mockResolvedValue({ success: true })
})

describe('UserManagementView', () => {
  it('validates and saves a new default password', async () => {
    const wrapper = mountPage()
    await flushPromises()
    const vm = wrapper.vm as any
    await vm.openDefaultPassword()
    expect(vm.defaultPassword).toBe('example-default')
    expect(vm.defaultPasswordVisible).toBe(true)
    vm.defaultPassword = 'short'
    await vm.saveDefaultPassword()
    expect(updateInitialPassword).not.toHaveBeenCalled()
    expect(messageWarning).toHaveBeenCalledWith('user_management.default_password_length')
    vm.defaultPassword = 'new-default-password'
    await vm.saveDefaultPassword()
    expect(updateInitialPassword).toHaveBeenCalledWith('new-default-password')
    expect(vm.defaultPasswordOpen).toBe(false)
    expect(vm.defaultPassword).toBe('')
    wrapper.unmount()
  })
  it('does not replace a manually entered default when loading finishes late', async () => {
    let resolvePassword!: (result: { password: string }) => void
    initialPassword.mockReturnValueOnce(new Promise((resolve) => { resolvePassword = resolve }))
    const wrapper = mountPage()
    await flushPromises()
    const vm = wrapper.vm as any
    const opening = vm.openDefaultPassword()
    vm.defaultPassword = 'custom-password'
    resolvePassword({ password: 'example-default' })
    await opening
    expect(vm.defaultPassword).toBe('custom-password')
    wrapper.unmount()
  })
  it('loads users, maps roles and opens create/edit forms', async () => {
    const wrapper = mountPage()
    await flushPromises()
    const vm = wrapper.vm as any

    expect(userList).toHaveBeenCalledWith(undefined)
    expect(vm.users).toEqual(USERS)
    expect(vm.roleLabel('admin')).toBe('user_management.roles.admin')
    expect(vm.roleLabel('unknown')).toBe('user_management.roles.unknown')

    vm.keyword = ' tester '
    await vm.loadUsers()
    expect(userList).toHaveBeenLastCalledWith('tester')

    await vm.openCreate()
    expect(vm.editing).toBe(null)
    expect(vm.modalOpen).toBe(true)
    expect(vm.form.role).toBe('tester')
    expect(vm.form.is_active).toBe(true)
    expect(vm.form.password).toBe('example-default')

    vm.openEdit(USERS[1])
    expect(vm.editing.id).toBe(2)
    expect(vm.form.username).toBe('tester')
    expect(vm.form.email).toBe('tester@example.com')
    expect(vm.form.password).toBe('')
    expect(vm.form.is_active).toBe(false)
  })

  it('validates required fields and password length before saving', async () => {
    const wrapper = mountPage()
    await flushPromises()
    const vm = wrapper.vm as any

    await vm.handleSave()
    expect(messageWarning).toHaveBeenCalledWith('user_management.required_hint')
    expect(userCreate).not.toHaveBeenCalled()

    vm.form.username = 'admin'
    vm.form.email = 'admin@example.com'
    vm.form.password = 'short'
    await vm.handleSave()
    expect(messageWarning).toHaveBeenCalledWith('user_management.password_too_short')
    expect(userCreate).not.toHaveBeenCalled()
  })

  it('creates and updates users, then reports API failures', async () => {
    const wrapper = mountPage()
    await flushPromises()
    const vm = wrapper.vm as any

    await vm.openCreate()
    vm.form.username = ' new-user '
    vm.form.email = 'new@example.com'
    vm.form.password = 'password-123'
    vm.form.role = 'engineer'
    vm.form.is_active = false
    await vm.handleSave()
    expect(userCreate).toHaveBeenCalledWith({
      username: 'new-user',
      email: 'new@example.com',
      password: 'password-123',
      role: 'engineer',
      is_active: false,
    })
    expect(messageSuccess).toHaveBeenCalledWith('user_management.saved')
    expect(vm.modalOpen).toBe(false)

    vm.openEdit(USERS[0])
    vm.form.username = 'updated'
    vm.form.email = 'updated@example.com'
    vm.form.password = 'new-password-123'
    vm.form.role = 'viewer'
    vm.form.is_active = false
    await vm.handleSave()
    expect(userUpdate).toHaveBeenCalledWith(1, {
      username: 'updated',
      email: 'updated@example.com',
      role: 'viewer',
      is_active: false,
      password: 'new-password-123',
    })

    vm.openEdit(USERS[0])
    vm.form.username = 'without-password'
    vm.form.email = 'without-password@example.com'
    await vm.handleSave()
    expect(userUpdate).toHaveBeenLastCalledWith(1, {
      username: 'without-password',
      email: 'without-password@example.com',
      role: 'admin',
      is_active: true,
    })

    userUpdate.mockRejectedValueOnce(new Error('update failed'))
    await vm.handleSave()
    expect(messageError).toHaveBeenCalledWith('update failed')
    expect(vm.saving).toBe(false)

    userList.mockRejectedValueOnce(new Error('list failed'))
    await vm.loadUsers()
    expect(messageError).toHaveBeenCalledWith('list failed')
    expect(vm.loading).toBe(false)

    userList.mockRejectedValueOnce('list string failure')
    await vm.loadUsers()
    expect(messageError).toHaveBeenCalledWith('list string failure')

    userList.mockRejectedValueOnce({ code: 'unknown' })
    await vm.loadUsers()
    expect(messageError).toHaveBeenCalledWith('user_management.save_failed')
  })

  it('does not overwrite a password entered while the default is loading', async () => {
    let resolvePassword!: (result: { password: string }) => void
    initialPassword.mockReturnValueOnce(new Promise((resolve) => { resolvePassword = resolve }))
    const wrapper = mountPage()
    await flushPromises()
    const vm = wrapper.vm as any
    const opening = vm.openCreate()
    vm.form.password = 'custom-password'
    resolvePassword({ password: 'example-default' })
    await opening
    expect(vm.form.password).toBe('custom-password')
    wrapper.unmount()
  })
})
