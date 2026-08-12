import { flushPromises, mount } from '@vue/test-utils'
import { defineComponent, h } from 'vue'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import UserManagementView from './UserManagementView.vue'

const { userList, userCreate, userUpdate, messageError, messageSuccess, messageWarning } = vi.hoisted(() => ({
  userList: vi.fn(),
  userCreate: vi.fn(),
  userUpdate: vi.fn(),
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
  userApi: { list: userList, create: userCreate, update: userUpdate },
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
})

describe('UserManagementView', () => {
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

    vm.openCreate()
    expect(vm.editing).toBe(null)
    expect(vm.modalOpen).toBe(true)
    expect(vm.form.role).toBe('tester')
    expect(vm.form.is_active).toBe(true)

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

    vm.openCreate()
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
})
