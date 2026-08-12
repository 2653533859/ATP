import { flushPromises, mount } from '@vue/test-utils'
import { defineComponent, h } from 'vue'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import ApiContractAssetsView from './ApiContractAssetsView.vue'

const {
  projectList,
  assetList,
  assetCreate,
  assetUpdate,
  assetDelete,
  compareAssets,
  messageError,
  messageSuccess,
  messageWarning,
} = vi.hoisted(() => ({
  projectList: vi.fn(),
  assetList: vi.fn(),
  assetCreate: vi.fn(),
  assetUpdate: vi.fn(),
  assetDelete: vi.fn(),
  compareAssets: vi.fn(),
  messageError: vi.fn(),
  messageSuccess: vi.fn(),
  messageWarning: vi.fn(),
}))

vi.mock('vue-i18n', () => ({ useI18n: () => ({ t: (key: string) => key }) }))
vi.mock('vue-router', () => ({ useRoute: () => ({ query: {} }) }))
vi.mock('ant-design-vue', () => ({
  message: { error: messageError, success: messageSuccess, warning: messageWarning },
}))
vi.mock('@/api', () => ({
  projectApi: { list: projectList },
  apiContractAssetApi: {
    list: assetList,
    create: assetCreate,
    update: assetUpdate,
    delete: assetDelete,
  },
  apiContractApi: { compareAssets },
}))

const passthrough = (name: string) =>
  defineComponent({ name, setup: (_props, { slots }) => () => h('div', slots.default?.()) })

const buttonStub = defineComponent({
  name: 'AButton',
  props: { disabled: Boolean },
  emits: ['click'],
  setup: (props, { slots, emit }) => () => h('button', {
    disabled: props.disabled,
    onClick: () => emit('click'),
  }, slots.default?.()),
})

const drawerStub = defineComponent({
  name: 'ADrawer',
  setup: (_props, { slots }) => () => h('div', { 'data-test': 'contract-drawer' }, [slots.default?.(), slots.footer?.()]),
})

function mountPage() {
  return mount(ApiContractAssetsView, {
    global: {
      stubs: {
        AAlert: passthrough('AAlert'),
        AButton: buttonStub,
        ACard: passthrough('ACard'),
        ACol: passthrough('ACol'),
        ACollapse: passthrough('ACollapse'),
        ACollapsePanel: passthrough('ACollapsePanel'),
        ADrawer: drawerStub,
        AForm: passthrough('AForm'),
        AFormItem: passthrough('AFormItem'),
        AInput: passthrough('AInput'),
        APopconfirm: passthrough('APopconfirm'),
        ARadioButton: passthrough('ARadioButton'),
        ARadioGroup: passthrough('ARadioGroup'),
        ARow: passthrough('ARow'),
        ASelect: passthrough('ASelect'),
        ASpace: passthrough('ASpace'),
        ATable: passthrough('ATable'),
        ATag: passthrough('ATag'),
        ATextarea: passthrough('ATextarea'),
      },
    },
  })
}

const PROJECTS = [{ id: 1, name: 'Core', owner_id: 1 }]
const ASSETS = [
  {
    id: 11,
    project_id: 1,
    name: 'Orders Provider',
    role: 'provider',
    format: 'openapi',
    description: 'provider contract',
    definition: { openapi: '3.0.0', paths: {} },
    version: 1,
    owner_id: 1,
    created_at: '2026-08-01T10:00:00Z',
    updated_at: '2026-08-01T10:00:00Z',
  },
  {
    id: 12,
    project_id: 1,
    name: 'Orders Consumer',
    role: 'consumer',
    format: 'openapi',
    description: 'consumer contract',
    definition: { openapi: '3.0.0', paths: { '/orders': { get: {} } } },
    version: 2,
    owner_id: 1,
    created_at: '2026-08-02T10:00:00Z',
    updated_at: '2026-08-02T10:00:00Z',
  },
]

beforeEach(() => {
  vi.clearAllMocks()
  projectList.mockResolvedValue(PROJECTS)
  assetList.mockResolvedValue(ASSETS)
  assetCreate.mockResolvedValue(ASSETS[0])
  assetUpdate.mockResolvedValue(ASSETS[0])
  assetDelete.mockResolvedValue(undefined)
  compareAssets.mockResolvedValue({ compatible: false, breaking_changes: [{ severity: 'breaking', location: '$.id', message: 'removed' }], warnings: [], summary: '1 breaking change' })
})

describe('ApiContractAssetsView', () => {
  it('loads project-scoped assets and derives role/version summaries', async () => {
    const wrapper = mountPage()
    await flushPromises()
    const vm = wrapper.vm as any

    expect(projectList).toHaveBeenCalledOnce()
    expect(assetList).toHaveBeenCalledWith(1)
    expect(vm.providerCount).toBe(1)
    expect(vm.consumerCount).toBe(1)
    expect(vm.latestVersion).toBe(2)
  })

  it('validates JSON and creates a contract asset', async () => {
    const wrapper = mountPage()
    await flushPromises()
    const vm = wrapper.vm as any

    vm.openCreate()
    vm.form.name = ''
    await vm.saveAsset()
    expect(messageWarning).toHaveBeenCalledWith('api_contract_assets.name_required')

    vm.form.name = 'Payments Provider'
    vm.form.role = 'provider'
    vm.form.format = 'openapi'
    vm.form.definitionText = '{bad json'
    await vm.saveAsset()
    expect(assetCreate).not.toHaveBeenCalled()
    expect(vm.definitionError).toBe('api_contract_assets.definition_invalid')

    vm.form.definitionText = '{"openapi":"3.0.0","paths":{}}'
    await vm.saveAsset()
    expect(assetCreate).toHaveBeenCalledWith(1, expect.objectContaining({
      name: 'Payments Provider',
      role: 'provider',
      format: 'openapi',
      definition: { openapi: '3.0.0', paths: {} },
    }))
    expect(messageSuccess).toHaveBeenCalledWith('api_contract_assets.saved')
  })

  it('compares selected assets and keeps the breaking result visible', async () => {
    const wrapper = mountPage()
    await flushPromises()
    const vm = wrapper.vm as any

    vm.baselineAssetId = 11
    vm.currentAssetId = 12
    await vm.compareAssets()

    expect(compareAssets).toHaveBeenCalledWith(1, 11, 12)
    expect(vm.comparison.compatible).toBe(false)
    expect(vm.comparison.breaking_changes).toHaveLength(1)
  })
})
