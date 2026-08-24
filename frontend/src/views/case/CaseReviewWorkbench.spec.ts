import { flushPromises, mount } from '@vue/test-utils'
import { defineComponent, h } from 'vue'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import CaseReviewWorkbench from './CaseReviewWorkbench.vue'

const { caseGet, caseReviewBatch, caseReviewHistory, caseReviewList, messageError, messageSuccess, messageWarning, projectList, routerPush, routerReplace } = vi.hoisted(() => ({
  caseGet: vi.fn(),
  caseReviewBatch: vi.fn(),
  caseReviewHistory: vi.fn(),
  caseReviewList: vi.fn(),
  messageError: vi.fn(),
  messageSuccess: vi.fn(),
  messageWarning: vi.fn(),
  projectList: vi.fn(),
  routerPush: vi.fn(),
  routerReplace: vi.fn(),
}))

vi.mock('vue-router', () => ({
  useRoute: () => ({ query: {} }),
  useRouter: () => ({ push: routerPush, replace: routerReplace }),
}))
vi.mock('vue-i18n', () => ({ useI18n: () => ({ t: (key: string) => key }) }))
vi.mock('ant-design-vue', () => ({ message: { error: messageError, success: messageSuccess, warning: messageWarning } }))
vi.mock('@/api', () => ({
  caseApi: { get: caseGet },
  caseReviewApi: { batch: caseReviewBatch, history: caseReviewHistory, list: caseReviewList },
  projectApi: { list: projectList },
}))
vi.mock('./CaseHistoryDrawer.vue', () => ({ default: defineComponent({ name: 'CaseHistoryDrawer', setup: () => () => h('div') }) }))

const passthrough = (name: string) => defineComponent({ name, setup: (_props, { slots }) => () => h('div', slots.default?.()) })
const buttonStub = defineComponent({
  name: 'AButton',
  props: { disabled: Boolean },
  emits: ['click'],
  setup: (props, { emit, slots }) => () => h('button', { disabled: props.disabled, onClick: () => emit('click') }, slots.default?.()),
})
const tableStub = defineComponent({
  name: 'ATable',
  props: ['dataSource'],
  setup: (props, { slots }) => () => h(
    'div',
    { 'data-test': 'review-table' },
    (props.dataSource || []).map((record: Record<string, unknown>) => h(
      'div',
      { class: 'review-row', key: String(record.id) },
      slots.bodyCell?.({ column: { key: 'case' }, record }),
    )),
  ),
})

const PROJECTS = [{ id: 7, name: '核心项目' }]
const ITEM = {
  id: 11,
  project_id: 7,
  project_name: '核心项目',
  module_id: 9,
  module_name: '登录模块',
  name: '登录成功',
  case_code: 'API-0011',
  summary: '验证正常登录',
  case_type: 'api',
  priority: 'P1',
  case_level: 'core',
  review_status: 'pending',
  automation_status: 'manual',
  creator_id: 1,
  owner_id: null,
  submitted_at: '2026-08-24T10:00:00Z',
  reviewed_at: null,
  reviewed_by: null,
  reviewer_name: null,
  review_comment: null,
  step_count: 2,
  snapshot_count: 1,
  latest_snapshot_version: 1,
  created_at: '2026-08-24T09:00:00Z',
  updated_at: '2026-08-24T10:00:00Z',
}

function mountPage() {
  return mount(CaseReviewWorkbench, {
    global: {
      stubs: {
        AButton: buttonStub,
        ADrawer: passthrough('ADrawer'),
        AEmpty: passthrough('AEmpty'),
        AForm: passthrough('AForm'),
        AFormItem: passthrough('AFormItem'),
        AInputSearch: passthrough('AInputSearch'),
        AModal: passthrough('AModal'),
        ASelect: passthrough('ASelect'),
        ASpace: passthrough('ASpace'),
        ASpin: passthrough('ASpin'),
        ATable: tableStub,
        ATag: passthrough('ATag'),
        ATimeline: passthrough('ATimeline'),
        ATimelineItem: passthrough('ATimelineItem'),
      },
    },
  })
}

beforeEach(() => {
  vi.clearAllMocks()
  projectList.mockResolvedValue(PROJECTS)
  caseReviewList.mockResolvedValue({ items: [ITEM], total: 1, page: 1, page_size: 20, counts: { all: 1, pending: 1, approved: 0, rejected: 0 } })
  caseReviewHistory.mockResolvedValue([])
  caseGet.mockResolvedValue({ ...ITEM })
  caseReviewBatch.mockResolvedValue({ requested: 1, processed: 1, processed_ids: [11], skipped_ids: [] })
})

describe('CaseReviewWorkbench', () => {
  it('loads project options and the pending review queue', async () => {
    const wrapper = mountPage()
    await flushPromises()

    expect(projectList).toHaveBeenCalledOnce()
    expect(caseReviewList).toHaveBeenCalledWith(expect.objectContaining({ review_status: 'pending', page: 1 }))
    expect(wrapper.findAll('.review-row')).toHaveLength(1)
    expect(wrapper.text()).toContain('API-0011')
  })

  it('submits a batch review and refreshes the queue', async () => {
    const wrapper = mountPage()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.selectedRowKeys = [11]
    vm.openBatch('approve')
    await vm.submitBatch()
    await flushPromises()

    expect(caseReviewBatch).toHaveBeenCalledWith({ case_ids: [11], action: 'approve', comment: undefined })
    expect(messageSuccess).toHaveBeenCalled()
    expect(caseReviewList).toHaveBeenCalledTimes(2)
    expect(vm.selectedRowKeys).toEqual([])
  })
})
