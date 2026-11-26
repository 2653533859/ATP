import { flushPromises, mount } from '@vue/test-utils'
import { nextTick } from 'vue'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import EnvironmentList from './EnvironmentList.vue'

const { projectList, environmentList, environmentCreate, environmentSaveVariables, messageError, messageWarning } = vi.hoisted(() => ({
  projectList: vi.fn(),
  environmentList: vi.fn(),
  environmentCreate: vi.fn(),
  environmentSaveVariables: vi.fn(),
  messageError: vi.fn(),
  messageWarning: vi.fn(),
}))

vi.mock('@/api', () => ({
  projectApi: { list: projectList },
  environmentApi: {
    list: environmentList,
    getVariables: vi.fn(),
    saveVariables: environmentSaveVariables,
    create: environmentCreate,
    update: vi.fn(),
    delete: vi.fn(),
  },
}))

vi.mock('ant-design-vue', () => ({
  message: {
    error: messageError,
    success: vi.fn(),
    warning: messageWarning,
    info: vi.fn(),
  },
}))

vi.mock('vue-i18n', () => ({
  useI18n: () => ({
    t: (key: string) => key,
  }),
}))
vi.mock('vue-router', () => ({ useRoute: () => ({ query: {} }) }))

const passthrough = { template: '<div><slot /></div>' }

const stubs = {
  ASpace: passthrough,
  AButton: passthrough,
  ACard: passthrough,
  AList: passthrough,
  'AListItem': passthrough,
  'AListItemMeta': passthrough,
  APopconfirm: passthrough,
  AInput: passthrough,
  'AInputPassword': passthrough,
  ASwitch: passthrough,
  ATable: passthrough,
  ADropdown: passthrough,
  AMenu: passthrough,
  AMenuItem: passthrough,
  AModal: passthrough,
  APopover: passthrough,
  AForm: passthrough,
  'AFormItem': passthrough,
  'ATextarea': passthrough,
  ASelectOption: passthrough,
  ASelect: {
    template: '<button data-test="project-select" @click="$emit(\'update:value\', 1); $emit(\'change\', 1)">select</button>',
  },
  ASpin: {
    props: ['spinning'],
    template: '<div data-test="loading" :data-spinning="String(spinning)"><slot /></div>',
  },
  AEmpty: {
    props: ['description'],
    template: '<div data-test="empty">{{ description }}</div>',
  },
}

function mountPage() {
  return mount(EnvironmentList, { global: { stubs } })
}

describe('EnvironmentList', () => {
  beforeEach(() => {
    projectList.mockReset()
    environmentList.mockReset()
    messageError.mockReset()
    projectList.mockResolvedValue([{ id: 1, name: 'Demo', owner_id: 1 }])
    environmentList.mockResolvedValue([])
  })

  it('selects the first project from the workspace context after loading projects', async () => {
    const wrapper = mountPage()

    await flushPromises()

    expect(projectList).toHaveBeenCalledOnce()
    expect(environmentList).toHaveBeenCalledWith(1)
    expect(wrapper.find('[data-test="empty"]').text()).toBe('system_pages.environment.no_environments')
    expect(wrapper.find('[data-test="loading"]').attributes('data-spinning')).toBe('false')
  })

  it('shows the environment empty state while an environment request is pending and after it resolves empty', async () => {
    let resolveEnvironments!: (value: never[]) => void
    environmentList.mockReturnValue(new Promise((resolve) => {
      resolveEnvironments = resolve
    }))
    const wrapper = mountPage()

    await flushPromises()
    await wrapper.find('[data-test="project-select"]').trigger('click')
    await nextTick()

    expect(wrapper.find('[data-test="loading"]').attributes('data-spinning')).toBe('true')
    expect(wrapper.findAll('[data-test="empty"]').map((empty) => empty.text())).toContain('system_pages.environment.no_environments')

    resolveEnvironments([])
    await flushPromises()

    expect(wrapper.find('[data-test="empty"]').text()).toBe('system_pages.environment.no_environments')
    expect(wrapper.find('[data-test="loading"]').attributes('data-spinning')).toBe('false')
  })

  it('reports an environment loading error and leaves the page in an empty state', async () => {
    const error = new Error('environment request failed')
    environmentList.mockRejectedValue(error)
    const wrapper = mountPage()

    await flushPromises()
    await wrapper.find('[data-test="project-select"]').trigger('click')
    await flushPromises()

    expect(messageError).toHaveBeenCalledWith('environment request failed')
    expect(wrapper.find('[data-test="empty"]').text()).toBe('system_pages.environment.no_environments')
    expect(wrapper.find('[data-test="loading"]').attributes('data-spinning')).toBe('false')
  })

  it('appends preset variables without overwriting existing or secret keys', async () => {
    const wrapper = mountPage()
    await flushPromises()

    const vm = wrapper.vm as unknown as {
      editingVars: Array<{ key: string; value: string; is_secret: boolean; _wasSecret: boolean }>
      handleApplyEnvPreset: (payload: { key: string }) => void
    }

    vm.editingVars = [
      { key: 'base_url', value: 'https://custom.internal', is_secret: false, _wasSecret: false },
      { key: 'token', value: '', is_secret: true, _wasSecret: true },
    ]
    vm.handleApplyEnvPreset({ key: 'jwt_auth' })

    expect(vm.editingVars.find((item) => item.key === 'base_url')?.value).toBe('https://custom.internal')
    expect(vm.editingVars.find((item) => item.key === 'token')?._wasSecret).toBe(true)
    expect(vm.editingVars.some((item) => item.key === 'auth_username')).toBe(true)
    expect(vm.editingVars.some((item) => item.key === 'auth_password' && item.is_secret)).toBe(true)
  })

  it('populates starter preset variables when creating a new environment with initialPresetId', async () => {
    environmentCreate.mockResolvedValueOnce({ id: 77, name: 'Staging', project_id: 1, description: '', created_at: '', updated_at: '' })
    environmentSaveVariables.mockResolvedValueOnce([])

    const wrapper = mountPage()
    await flushPromises()

    const vm = wrapper.vm as unknown as {
      envForm: { name: string; description: string }
      initialPresetId: string | undefined
      handleSaveEnv: () => Promise<void>
    }

    vm.envForm.name = 'Staging'
    vm.initialPresetId = 'rest_basic'
    await vm.handleSaveEnv()

    expect(environmentCreate).toHaveBeenCalledWith(expect.objectContaining({ name: 'Staging', project_id: 1 }))
    expect(environmentSaveVariables).toHaveBeenCalledWith(77, {
      variables: expect.arrayContaining([
        expect.objectContaining({ key: 'base_url', is_secret: false }),
      ]),
    })

    // Starter variable save failure should warn instead of failing silently
    messageWarning.mockClear()
    environmentCreate.mockResolvedValueOnce({ id: 78, name: 'QA2', project_id: 1, description: '', created_at: '', updated_at: '' })
    environmentSaveVariables.mockRejectedValueOnce(new Error('save failed'))
    vm.envForm.name = 'QA2'
    vm.initialPresetId = 'rest_basic'
    await vm.handleSaveEnv()
    expect(messageWarning).toHaveBeenCalledWith('system_pages.environment.msg.save_vars_failed')
  })
})
