import { flushPromises, mount } from '@vue/test-utils'
import { defineComponent } from 'vue'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import LoginView from './LoginView.vue'

const { getLocale, login, messageError, push, routeQuery, setLocale } = vi.hoisted(() => ({
  getLocale: vi.fn(() => 'zh-CN'),
  login: vi.fn(),
  messageError: vi.fn(),
  push: vi.fn(),
  routeQuery: {} as Record<string, unknown>,
  setLocale: vi.fn(),
}))

vi.mock('vue-router', () => ({
  useRoute: () => ({ query: routeQuery }),
  useRouter: () => ({ push }),
}))

vi.mock('@/stores/auth', () => ({
  useAuthStore: () => ({ login }),
}))

vi.mock('@/locales', () => ({
  getLocale,
  setLocale,
}))

vi.mock('ant-design-vue', () => ({
  message: { error: messageError },
}))

vi.mock('vue-i18n', () => ({
  useI18n: () => ({ t: (key: string) => key }),
}))

const FormStub = defineComponent({
  emits: ['finish'],
  template: '<form data-test="login-form" @submit.prevent="$emit(\'finish\')"><slot /></form>',
})

const FormItemStub = defineComponent({
  name: 'AFormItem',
  props: ['name', 'rules'],
  template: '<div><slot /></div>',
})

const InputStub = defineComponent({
  props: ['value'],
  emits: ['update:value'],
  template: '<input data-test="username" :value="value" @input="$emit(\'update:value\', $event.target.value)" />',
})

const PasswordStub = defineComponent({
  props: ['value'],
  emits: ['update:value'],
  template: '<input data-test="password" :value="value" @input="$emit(\'update:value\', $event.target.value)" />',
})

const ButtonStub = defineComponent({
  props: ['loading'],
  template: '<button data-test="submit" type="submit" :data-loading="String(Boolean(loading))"><slot /></button>',
})

function mountPage() {
  return mount(LoginView, {
    global: {
      stubs: {
        AForm: FormStub,
        AFormItem: FormItemStub,
        AInput: InputStub,
        AInputPassword: PasswordStub,
        AButton: ButtonStub,
        ARadioGroup: { template: '<div><slot /></div>' },
        ARadioButton: { template: '<button type="button"><slot /></button>' },
        UserOutlined: true,
        LockOutlined: true,
        ThunderboltFilled: true,
      },
    },
  })
}

describe('LoginView', () => {
  beforeEach(() => {
    login.mockReset()
    messageError.mockReset()
    push.mockReset()
    setLocale.mockReset()
    getLocale.mockReturnValue('zh-CN')
    for (const key of Object.keys(routeQuery)) delete routeQuery[key]
  })

  it('declares required validation for username and password', () => {
    const items = mountPage().findAllComponents(FormItemStub)

    expect(items).toHaveLength(3)
    expect(items[0].props('rules')).toEqual([{ required: true, message: 'login.required_username' }])
    expect(items[1].props('rules')).toEqual([{ required: true, message: 'login.required_password' }])
  })

  it('submits credentials, shows loading, and honors the redirect query', async () => {
    let resolveLogin!: () => void
    login.mockReturnValue(new Promise<void>((resolve) => {
      resolveLogin = resolve
    }))
    routeQuery.redirect = '/cases?project_id=7'
    const wrapper = mountPage()

    await wrapper.find('[data-test="username"]').setValue('alice')
    await wrapper.find('[data-test="password"]').setValue('secret')
    await wrapper.find('[data-test="login-form"]').trigger('submit')

    expect(login).toHaveBeenCalledWith('alice', 'secret')
    expect(wrapper.find('[data-test="submit"]').attributes('data-loading')).toBe('true')

    resolveLogin()
    await flushPromises()

    expect(push).toHaveBeenCalledWith('/cases?project_id=7')
    expect(wrapper.find('[data-test="submit"]').attributes('data-loading')).toBe('false')
  })

  it('redirects to the application root when no redirect query is present', async () => {
    login.mockResolvedValue(undefined)
    const wrapper = mountPage()

    await wrapper.find('[data-test="login-form"]').trigger('submit')
    await flushPromises()

    expect(push).toHaveBeenCalledWith('/')
  })

  it('reports login failures, clears loading, and does not navigate', async () => {
    login.mockRejectedValue(new Error('invalid credentials'))
    const wrapper = mountPage()

    await wrapper.find('[data-test="login-form"]').trigger('submit')
    await flushPromises()

    expect(messageError).toHaveBeenCalledWith('invalid credentials')
    expect(push).not.toHaveBeenCalled()
    expect(wrapper.find('[data-test="submit"]').attributes('data-loading')).toBe('false')
  })
})
