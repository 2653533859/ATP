import { defineComponent, h, ref } from 'vue'
import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import KnowledgeHubView from './KnowledgeHubView.vue'

const {
  knowledgeCreate,
  knowledgeGet,
  knowledgeList,
  projectList,
  routerPush,
  routerReplace,
} = vi.hoisted(() => ({
  knowledgeCreate: vi.fn(),
  knowledgeGet: vi.fn(),
  knowledgeList: vi.fn(),
  projectList: vi.fn(),
  routerPush: vi.fn(),
  routerReplace: vi.fn(),
}))

vi.mock('vue-router', () => ({
  useRoute: () => ({ query: { project_id: '1' } }),
  useRouter: () => ({ push: routerPush, replace: routerReplace }),
}))
vi.mock('vue-i18n', () => ({
  useI18n: () => ({ locale: ref('zh-CN'), t: (key: string, values?: Record<string, unknown>) => values ? `${key}:${JSON.stringify(values)}` : key }),
}))
vi.mock('ant-design-vue', () => ({
  message: { error: vi.fn(), success: vi.fn(), info: vi.fn() },
}))
vi.mock('@/stores/auth', () => ({
  useAuthStore: () => ({ user: { role: 'admin' } }),
}))
vi.mock('@/api', () => ({
  knowledgeApi: {
    list: knowledgeList,
    get: knowledgeGet,
    create: knowledgeCreate,
    update: vi.fn(),
    delete: vi.fn(),
  },
  projectApi: { list: projectList },
}))
vi.mock('@ant-design/icons-vue', () => {
  const iconStub = { setup: () => () => null }
  return {
    AppstoreOutlined: iconStub,
    ArrowRightOutlined: iconStub,
    BookOutlined: iconStub,
    BulbOutlined: iconStub,
    ExperimentOutlined: iconStub,
    FileTextOutlined: iconStub,
    FolderOpenOutlined: iconStub,
    GlobalOutlined: iconStub,
    LinkOutlined: iconStub,
    LockOutlined: iconStub,
    DeleteOutlined: iconStub,
    EditOutlined: iconStub,
    PlusOutlined: iconStub,
    ReloadOutlined: iconStub,
    SafetyCertificateOutlined: iconStub,
    SearchOutlined: iconStub,
  }
})

const passthrough = defineComponent({
  setup: (_props, { slots }) => () => h('div', slots.default?.()),
})

const globalStubs = Object.fromEntries(
  ['AAlert', 'AButton', 'ADrawer', 'AEmpty', 'AForm', 'AFormItem', 'AInput', 'APopconfirm', 'ASelect', 'ASpin', 'ATag', 'ATextarea']
    .map((name) => [name, passthrough]),
)

const entry = {
  key: 'entry:1',
  document_id: 1,
  source_type: 'runbook',
  title: '登录排查手册',
  excerpt: '先确认认证服务和 Redis 状态。',
  project_id: 1,
  project_name: '核心项目',
  source_ref: 'SOP-LOGIN',
  tags: ['登录'],
  status: 'published',
  match_terms: [],
  match_score: 0,
  target_path: null,
  is_global: false,
  is_editable: true,
  updated_at: '2026-08-24T10:00:00Z',
}

const builtin = {
  key: 'defect:2',
  source_type: 'defect',
  title: '登录超时',
  excerpt: '历史失败模式',
  project_id: 1,
  project_name: '核心项目',
  source_ref: 'BUG-2',
  tags: ['P1'],
  status: 'open',
  match_terms: ['登录'],
  match_score: 12,
  target_path: '/bugs?project_id=1&defect_id=2',
  is_global: false,
  is_editable: false,
  updated_at: '2026-08-23T10:00:00Z',
}

beforeEach(() => {
  vi.clearAllMocks()
  projectList.mockResolvedValue([{ id: 1, name: '核心项目', owner_id: 1, current_user_role: 'owner' }])
  knowledgeList.mockResolvedValue({ items: [entry, builtin], total: 2, page: 1, page_size: 40, source_counts: { runbook: 1, defect: 1 } })
  knowledgeGet.mockResolvedValue({ ...entry, summary: '认证服务异常时的排查顺序。', content: '先确认认证服务和 Redis 状态。', version: 2, author_id: 7, created_at: entry.updated_at })
  routerReplace.mockResolvedValue(undefined)
})

function mountView() {
  return mount(KnowledgeHubView, { global: { stubs: globalStubs } })
}

describe('KnowledgeHubView', () => {
  it('loads the selected project and opens the selected manual entry', async () => {
    const wrapper = mountView()
    await flushPromises()

    expect(knowledgeList).toHaveBeenCalledWith({ project_id: 1, keyword: undefined, source_type: undefined, status: undefined })
    expect(knowledgeGet).toHaveBeenCalledWith(1)
    expect((wrapper.vm as any).selectedDetail.content).toContain('Redis')
    expect((wrapper.vm as any).sourceCounts.runbook).toBe(1)
    wrapper.unmount()
  })

  it('searches by source filter and opens built-in source routes without editing them', async () => {
    const wrapper = mountView()
    await flushPromises()
    const vm = wrapper.vm as any
    await vm.selectSource('defect')

    expect(knowledgeList).toHaveBeenLastCalledWith({ project_id: 1, keyword: undefined, source_type: 'defect', status: undefined })
    await vm.selectItem(builtin)
    await vm.openSource(builtin)
    expect(routerPush).toHaveBeenCalledWith('/bugs?project_id=1&defect_id=2')
    expect(vm.selectedDetail).toBe(null)
    expect(vm.selectedItem.is_editable).toBe(false)
    wrapper.unmount()
  })

  it('creates a project knowledge entry from trimmed editable form data', async () => {
    knowledgeCreate.mockResolvedValue({ ...entry, title: '新的经验' })
    const wrapper = mountView()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.openCreate()
    vm.form.title = '  新的经验  '
    vm.form.content = '  检查 Worker 日志  '
    vm.form.summary = '  可复用排查顺序  '
    vm.form.tags = ['Worker', 'Worker']
    await vm.saveEntry()

    expect(knowledgeCreate).toHaveBeenCalledWith(expect.objectContaining({
      project_id: 1,
      title: '新的经验',
      content: '检查 Worker 日志',
      summary: '可复用排查顺序',
      tags: ['Worker'],
    }))
    wrapper.unmount()
  })
})
