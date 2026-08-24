import { flushPromises, mount } from '@vue/test-utils'
import { defineComponent, h } from 'vue'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import DefectListView from './DefectListView.vue'

const { projectList, memberList, defectList, defectUpdate } = vi.hoisted(() => ({
  projectList: vi.fn(),
  memberList: vi.fn(),
  defectList: vi.fn(),
  defectUpdate: vi.fn(),
}))

vi.mock('vue-i18n', () => ({
  useI18n: () => ({ t: (key: string, params?: Record<string, unknown>) => params ? `${key}:${JSON.stringify(params)}` : key }),
}))
vi.mock('vue-router', () => ({
  useRoute: () => ({ query: {} }),
  useRouter: () => ({ replace: vi.fn(), push: vi.fn() }),
}))
vi.mock('ant-design-vue', () => ({
  message: { error: vi.fn(), success: vi.fn(), warning: vi.fn() },
}))
vi.mock('@/api', () => ({
  projectApi: { list: projectList },
  projectMemberApi: { list: memberList },
  defectApi: { list: defectList, update: defectUpdate },
}))

const passthrough = (name: string) =>
  defineComponent({ name, setup: (_props, { slots }) => () => h('div', slots.default?.()) })

const tableStub = defineComponent({
  name: 'ATable',
  props: ['dataSource'],
  setup: (props, { slots }) => () => h(
    'div',
    (props.dataSource || []).map((record: Record<string, unknown>) => h(
      'div',
      { class: 'defect-row', key: String(record.id) },
      slots.bodyCell?.({ column: { key: 'title' }, record }),
    )),
  ),
})

const globalStubs = {
  AAlert: passthrough('AAlert'),
  AButton: passthrough('AButton'),
  ABadge: passthrough('ABadge'),
  ACard: passthrough('ACard'),
  ACol: passthrough('ACol'),
  ADescriptions: passthrough('ADescriptions'),
  ADescriptionsItem: passthrough('ADescriptionsItem'),
  ADrawer: passthrough('ADrawer'),
  AEmpty: passthrough('AEmpty'),
  AForm: passthrough('AForm'),
  AFormItem: passthrough('AFormItem'),
  AInput: passthrough('AInput'),
  AModal: passthrough('AModal'),
  APagination: passthrough('APagination'),
  ARow: passthrough('ARow'),
  ASelect: passthrough('ASelect'),
  ASpace: passthrough('ASpace'),
  ATable: tableStub,
  ATag: passthrough('ATag'),
  ATextarea: passthrough('ATextarea'),
}

beforeEach(() => {
  vi.clearAllMocks()
  projectList.mockResolvedValue([{ id: 1, name: 'Core' }])
  memberList.mockResolvedValue([{ user_id: 8, username: 'qa', email: 'qa@example.com', role: 'editor', created_at: '2026-08-24T00:00:00Z' }])
  defectList.mockResolvedValue({ items: [], total: 0, page: 1, page_size: 20 })
  defectUpdate.mockResolvedValue(undefined)
})

describe('DefectListView', () => {
  it('loads project members and defects on mount', async () => {
    const wrapper = mount(DefectListView, { global: { stubs: globalStubs } })
    await flushPromises()

    expect(projectList).toHaveBeenCalledOnce()
    expect(defectList).toHaveBeenCalledWith({
      project_id: undefined,
      status: undefined,
      priority: undefined,
      severity: undefined,
      page: 1,
      page_size: 20,
    })
    expect(wrapper.text()).toContain('defect.title')
    wrapper.unmount()
  })
})
