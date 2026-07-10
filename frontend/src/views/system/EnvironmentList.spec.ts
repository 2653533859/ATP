import { flushPromises, mount } from '@vue/test-utils'
import { nextTick } from 'vue'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import EnvironmentList from './EnvironmentList.vue'

const { projectList, environmentList, messageError } = vi.hoisted(() => ({
  projectList: vi.fn(),
  environmentList: vi.fn(),
  messageError: vi.fn(),
}))

vi.mock('@/api', () => ({
  projectApi: { list: projectList },
  environmentApi: {
    list: environmentList,
    getVariables: vi.fn(),
    saveVariables: vi.fn(),
    create: vi.fn(),
    update: vi.fn(),
    delete: vi.fn(),
  },
}))

vi.mock('ant-design-vue', () => ({
  message: {
    error: messageError,
    success: vi.fn(),
    warning: vi.fn(),
  },
}))

vi.mock('vue-i18n', () => ({
  useI18n: () => ({
    t: (key: string) => key,
  }),
}))

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
  AModal: passthrough,
  AForm: passthrough,
  'AFormItem': passthrough,
  'ATextarea': passthrough,
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

  it('shows the project-selection empty state after loading projects', async () => {
    const wrapper = mountPage()

    await flushPromises()

    expect(projectList).toHaveBeenCalledOnce()
    expect(wrapper.find('[data-test="empty"]').text()).toBe('system_pages.environment.select_project_first')
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
})
