import { flushPromises, mount } from '@vue/test-utils'
import { defineComponent, h } from 'vue'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import CaseDetail from './CaseDetail.vue'

const { caseGet, caseVersions, projectGetModules, projectList } = vi.hoisted(() => ({
  caseGet: vi.fn(),
  caseVersions: vi.fn(),
  projectGetModules: vi.fn(),
  projectList: vi.fn(),
}))

vi.mock('vue-router', () => ({
  useRoute: () => ({ params: { caseId: '10' }, query: {} }),
  useRouter: () => ({ back: vi.fn(), push: vi.fn() }),
}))
vi.mock('vue-i18n', () => ({
  useI18n: () => ({ t: (key: string) => key }),
}))
vi.mock('ant-design-vue', () => ({
  Empty: { PRESENTED_IMAGE_SIMPLE: 'empty' },
  message: { error: vi.fn(), success: vi.fn(), warning: vi.fn() },
}))
vi.mock('@/stores/auth', () => ({
  useAuthStore: () => ({ user: { role: 'engineer' }, fetchMe: vi.fn() }),
}))
vi.mock('@/api', () => ({
  caseApi: {
    get: caseGet,
    versions: caseVersions,
    copy: vi.fn(),
    run: vi.fn(),
    submitReview: vi.fn(),
    approve: vi.fn(),
    reject: vi.fn(),
    deprecate: vi.fn(),
    reactivate: vi.fn(),
  },
  environmentApi: { list: vi.fn().mockResolvedValue([]) },
  projectApi: { list: projectList, getModules: projectGetModules },
}))

const passthrough = (name: string) => defineComponent({
  name,
  props: ['title'],
  setup: (props, { slots }) => () => h('div', { 'data-card-title': props.title }, [slots.extra?.(), slots.default?.()]),
})

function mountDetail() {
  return mount(CaseDetail, {
    global: {
      stubs: {
        AAlert: passthrough('AAlert'),
        AButton: passthrough('AButton'),
        ACard: passthrough('ACard'),
        ACol: passthrough('ACol'),
        ADescriptions: passthrough('ADescriptions'),
        ADescriptionsItem: passthrough('ADescriptionsItem'),
        ADropdown: passthrough('ADropdown'),
        AEmpty: passthrough('AEmpty'),
        AMenu: passthrough('AMenu'),
        AMenuItem: passthrough('AMenuItem'),
        AModal: passthrough('AModal'),
        ARow: passthrough('ARow'),
        ASelect: passthrough('ASelect'),
        ASpace: passthrough('ASpace'),
        ASpin: passthrough('ASpin'),
        ATable: passthrough('ATable'),
        ATag: passthrough('ATag'),
        ATooltip: passthrough('ATooltip'),
        CaseHistoryDrawer: passthrough('CaseHistoryDrawer'),
        DownOutlined: true,
      },
    },
  })
}

describe('CaseDetail scenario flow visibility', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    projectList.mockResolvedValue([])
    projectGetModules.mockResolvedValue([])
    caseVersions.mockResolvedValue([])
  })

  it('hides API scenario pipeline for Web lowcode cases even when config.steps exists', async () => {
    caseGet.mockResolvedValueOnce({
      id: 10,
      case_code: 'WEB-10',
      name: 'Web 低代码登录',
      case_type: 'web',
      status: 'active',
      review_status: 'approved',
      priority: 'P1',
      case_level: 'smoke',
      automation_status: 'automated',
      script_status: 'generated',
      is_ready_for_execution: true,
      module_id: 1,
      creator_id: 1,
      tags: [],
      preconditions: [],
      postconditions: [],
      steps: [],
      config: { steps: [{ action: 'goto', name: '打开首页', params: { url: 'https://demo.test' } }] },
      created_at: '',
      updated_at: '',
    })

    const wrapper = mountDetail()
    await flushPromises()
    expect(wrapper.find('.api-steps-flow').exists()).toBe(false)
    wrapper.unmount()
  })

  it('renders API scenario pipeline for API cases with config.steps', async () => {
    caseGet.mockResolvedValueOnce({
      id: 11,
      case_code: 'API-11',
      name: 'API 场景流',
      case_type: 'api',
      status: 'active',
      review_status: 'approved',
      priority: 'P1',
      case_level: 'smoke',
      automation_status: 'automated',
      script_status: 'generated',
      is_ready_for_execution: true,
      module_id: 1,
      creator_id: 1,
      tags: [],
      preconditions: [],
      postconditions: [],
      steps: [],
      config: { steps: [{ name: '获取 Token', method: 'POST', url: '/auth/login' }] },
      created_at: '',
      updated_at: '',
    })

    const wrapper = mountDetail()
    await flushPromises()
    expect(wrapper.find('.api-steps-flow').exists()).toBe(true)
    expect(wrapper.text()).toContain('获取 Token')
    wrapper.unmount()
  })
})
