import { flushPromises, mount } from '@vue/test-utils'
import { defineComponent, h } from 'vue'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import ProjectList from './ProjectList.vue'

const {
  projectList,
  projectCreate,
  projectUpdate,
  projectDelete,
  projectCopy,
  projectExport,
  projectArchive,
  projectRestore,
  previewImport,
  importProject,
  llmList,
  routerPush,
  messageError,
  messageSuccess,
  messageWarning,
} = vi.hoisted(() => ({
  projectList: vi.fn(),
  projectCreate: vi.fn(),
  projectUpdate: vi.fn(),
  projectDelete: vi.fn(),
  projectCopy: vi.fn(),
  projectExport: vi.fn(),
  projectArchive: vi.fn(),
  projectRestore: vi.fn(),
  previewImport: vi.fn(),
  importProject: vi.fn(),
  llmList: vi.fn(),
  routerPush: vi.fn(),
  messageError: vi.fn(),
  messageSuccess: vi.fn(),
  messageWarning: vi.fn(),
}))

vi.mock('vue-i18n', () => ({
  useI18n: () => ({
    t: (key: string, params?: Record<string, unknown>) =>
      params ? `${key}:${Object.values(params).join('|')}` : key,
  }),
}))
vi.mock('vue-router', () => ({
  createRouter: () => ({ push: routerPush, beforeEach: vi.fn() }),
  createWebHistory: () => ({}),
  useRouter: () => ({ push: routerPush }),
}))
vi.mock('ant-design-vue', () => ({
  message: { error: messageError, success: messageSuccess, warning: messageWarning },
}))
vi.mock('@/api', () => ({
  projectApi: {
    list: projectList,
    create: projectCreate,
    update: projectUpdate,
    delete: projectDelete,
    copy: projectCopy,
    export: projectExport,
    archive: projectArchive,
    restore: projectRestore,
    previewImport,
    importProject,
  },
  aiLLMConfigApi: { list: llmList },
}))

const passthrough = defineComponent({
  setup: (_props, { slots }) => () => h('div', [slots.default?.(), slots.title?.(), slots.extra?.()]),
})

const buttonStub = defineComponent({
  props: { disabled: { type: Boolean, default: false } },
  setup: (props, { slots }) => () => h('button', { disabled: props.disabled }, slots.default?.()),
})

function mountPage() {
  const names = [
    'AAlert', 'AButton', 'ACard', 'ACol', 'AEmpty', 'AForm', 'AFormItem', 'AInput', 'AInputSearch',
    'AModal', 'APopconfirm', 'ARow', 'ASelect', 'ASelectOption', 'ASpace', 'ASpin', 'AStatistic', 'ATag',
    'ATextarea', 'AUpload', 'MemberManageDrawer',
  ]
  return mount(ProjectList, {
    global: {
      stubs: {
        ...Object.fromEntries(names.map((name) => [name, passthrough])),
        AButton: buttonStub,
        'a-button': buttonStub,
      },
    },
  })
}

const PROJECTS = [
  { id: 1, name: 'Core', description: 'API tests', ai_llm_config_id: 7, status: 'active' },
  { id: 2, name: 'Archived', description: null, ai_llm_config_id: null, status: 'archived' },
]

beforeEach(() => {
  vi.clearAllMocks()
  projectList.mockResolvedValue(PROJECTS)
  llmList.mockResolvedValue([
    { id: 7, name: 'GPT', provider: 'openai', model_name: 'model-a', enabled: true },
    { id: 8, name: 'Disabled', provider: 'local', model_name: 'model-b', enabled: false },
  ])
  projectCreate.mockResolvedValue(PROJECTS[0])
  projectUpdate.mockResolvedValue(PROJECTS[0])
  projectDelete.mockResolvedValue(undefined)
  projectCopy.mockResolvedValue(PROJECTS[0])
  projectExport.mockResolvedValue({ project: { name: 'Core' } })
  projectArchive.mockResolvedValue(PROJECTS[0])
  projectRestore.mockResolvedValue(PROJECTS[0])
  previewImport.mockResolvedValue({ valid: true, conflicts: [], warnings: [] })
  importProject.mockResolvedValue(PROJECTS[0])
})

describe('ProjectList', () => {
  it('loads projects and computes filters, summaries, options, and drawer state', async () => {
    const wrapper = mountPage()
    await flushPromises()
    const vm = wrapper.vm as any

    expect(projectList).toHaveBeenCalledOnce()
    expect(llmList).toHaveBeenCalledOnce()
    expect(wrapper.findAll('button').some((button) =>
      button.text().includes('common.edit') && button.attributes('disabled') !== undefined,
    )).toBe(true)
    expect(vm.aiBoundCount).toBe(1)
    expect(vm.llmOptions).toEqual([{ label: 'GPT (openai/model-a)', value: 7 }])
    expect(vm.llmConfigLabel(7)).toBe('GPT')
    expect(vm.llmConfigLabel(99)).toBe('#99')
    expect(vm.llmConfigLabel(null)).toBe('project.unbound')
    expect(vm.templateOptions).toHaveLength(5)

    vm.keyword = 'api'
    expect(vm.filteredProjects).toHaveLength(1)
    vm.keyword = 'missing'
    expect(vm.filteredProjects).toHaveLength(0)
    vm.keyword = ''
    vm.openMembers(PROJECTS[1])
    expect(vm.memberProjectId).toBe(2)
    expect(vm.memberProjectStatus).toBe('archived')
    vm.openCreate()
    expect(vm.showModal).toBe(true)
    expect(vm.form.name).toBe('')
    vm.openEdit(PROJECTS[0])
    expect(vm.editingId).toBe(1)
    expect(vm.form.name).toBe('Core')
    vm.openCopy(PROJECTS[0])
    expect(vm.copySource.id).toBe(1)
    vm.saving = true
    vm.handleCancel()
    expect(vm.showModal).toBe(true)
    vm.saving = false
    vm.handleCancel()
    expect(vm.showModal).toBe(false)
  })

  it('creates and updates projects with validation and error handling', async () => {
    const wrapper = mountPage()
    await flushPromises()
    const vm = wrapper.vm as any

    await vm.handleSave()
    expect(messageWarning).toHaveBeenCalledWith('project.msg.name_required')

    vm.form.name = '  New project  '
    vm.form.description = ' description '
    vm.form.ai_llm_config_id = 7
    vm.form.template = 'web'
    await vm.handleSave()
    expect(projectCreate).toHaveBeenCalledWith({
      name: 'New project', description: 'description', ai_llm_config_id: 7, template: 'web',
    })
    expect(messageSuccess).toHaveBeenCalledWith('project.msg.create_success')

    vm.editingId = 1
    vm.form.name = 'Updated'
    await vm.handleSave()
    expect(projectUpdate).toHaveBeenCalledWith(1, {
      name: 'Updated', description: undefined, ai_llm_config_id: null,
    })

    projectCreate.mockRejectedValueOnce(new Error('create failed'))
    vm.editingId = null
    vm.form.name = 'Broken'
    await vm.handleSave()
    expect(messageError).toHaveBeenCalledWith('create failed')
    expect(vm.saving).toBe(false)
  })

  it('copies, exports, archives, restores, and deletes projects', async () => {
    const wrapper = mountPage()
    await flushPromises()
    const vm = wrapper.vm as any

    vm.openCopy(PROJECTS[0])
    vm.copyName = ''
    await vm.handleCopy()
    expect(messageWarning).toHaveBeenCalledWith('project.msg.copy_name_required')
    vm.copyName = 'Core copy'
    await vm.handleCopy()
    expect(projectCopy).toHaveBeenCalledWith(1, { name: 'Core copy' })

    const anchor = { href: '', download: '', click: vi.fn() }
    const createUrl = vi.spyOn(URL, 'createObjectURL').mockReturnValue('blob:project')
    const revokeUrl = vi.spyOn(URL, 'revokeObjectURL').mockImplementation(() => undefined)
    const createElement = vi.spyOn(document, 'createElement').mockReturnValue(anchor as unknown as HTMLElement)
    await vm.handleExport(PROJECTS[0])
    expect(anchor.download).toBe('Core-project.json')
    expect(anchor.click).toHaveBeenCalledOnce()
    expect(createUrl).toHaveBeenCalledOnce()
    expect(revokeUrl).toHaveBeenCalledWith('blob:project')
    createElement.mockRestore()
    createUrl.mockRestore()
    revokeUrl.mockRestore()

    await vm.handleArchive(1)
    await vm.handleRestore(2)
    await vm.handleDelete(1)
    expect(projectArchive).toHaveBeenCalledWith(1)
    expect(projectRestore).toHaveBeenCalledWith(2)
    expect(projectDelete).toHaveBeenCalledWith(1)

    projectCopy.mockRejectedValueOnce(new Error('copy failed'))
    vm.copySource = PROJECTS[0]
    vm.copyName = 'retry'
    await vm.handleCopy()
    projectExport.mockRejectedValueOnce(new Error('export failed'))
    await vm.handleExport(PROJECTS[0])
    projectArchive.mockRejectedValueOnce(new Error('archive failed'))
    await vm.handleArchive(1)
    projectRestore.mockRejectedValueOnce(new Error('restore failed'))
    await vm.handleRestore(2)
    projectDelete.mockRejectedValueOnce(new Error('delete failed'))
    await vm.handleDelete(1)
    expect(messageError).toHaveBeenCalled()

    projectList.mockRejectedValueOnce(new Error('load failed'))
    await vm.loadProjects()
    expect(messageError).toHaveBeenCalledWith('load failed')
    llmList.mockRejectedValueOnce({ response: { status: 403 } })
    await vm.loadLLMConfigs()
    llmList.mockRejectedValueOnce(new Error('llm load failed'))
    await vm.loadLLMConfigs()
    expect(messageError).toHaveBeenCalledWith('project.msg.load_ai_failed')
  })

  it('previews and imports valid files, while rejecting invalid or failed imports', async () => {
    const wrapper = mountPage()
    await flushPromises()
    const vm = wrapper.vm as any
    const validFile = { name: 'project.json', text: () => Promise.resolve('{"project":{"name":"Core"}}') }
    const invalidFile = { name: 'broken.json', text: () => Promise.resolve('{broken') }

    expect(await vm.handleImportFile(validFile)).toBe(false)
    expect(previewImport).toHaveBeenCalledWith({
      payload: { project: { name: 'Core' } }, conflict_policy: 'fail',
    })
    expect(vm.importModalOpen).toBe(true)
    vm.importPolicy = 'rename'
    await vm.refreshImportPreview()
    expect(previewImport).toHaveBeenLastCalledWith({
      payload: { project: { name: 'Core' } }, conflict_policy: 'rename',
    })
    await vm.handleImport()
    expect(importProject).toHaveBeenCalledWith({
      payload: { project: { name: 'Core' } }, conflict_policy: 'rename',
    })
    expect(vm.importModalOpen).toBe(false)

    await vm.handleImportFile(invalidFile)
    expect(messageError).toHaveBeenCalledWith(expect.stringContaining('Expected property name'))
    vm.importPayload = { project: { name: 'Core' } }
    vm.importPreview = { valid: false, conflicts: ['duplicate'], warnings: [] }
    await vm.handleImport()
    expect(importProject).toHaveBeenCalledOnce()

    previewImport.mockRejectedValueOnce(new Error('preview failed'))
    vm.importPayload = { project: { name: 'Core' } }
    await vm.refreshImportPreview()
    expect(vm.importPreview).toBe(null)
    importProject.mockRejectedValueOnce(new Error('import failed'))
    vm.importPreview = { valid: true, conflicts: [], warnings: [] }
    await vm.handleImport()
    expect(vm.importing).toBe(false)
    vm.importModalOpen = true
    vm.importing = true
    vm.resetImport()
    expect(vm.importModalOpen).toBe(true)
    vm.importing = false
    vm.resetImport()
    expect(vm.importModalOpen).toBe(false)
  })
})
