import { flushPromises, mount } from '@vue/test-utils'
import { defineComponent, h } from 'vue'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import StorageManagementView from './StorageManagementView.vue'

const {
  storageStats,
  storagePreview,
  storageExecute,
  storageReconcile,
  storageAlert,
  projectList,
  policyList,
  policyCreate,
  policyUpdate,
  policyDelete,
  modalConfirm,
  messageError,
  messageSuccess,
  messageWarning,
} = vi.hoisted(() => ({
  storageStats: vi.fn(),
  storagePreview: vi.fn(),
  storageExecute: vi.fn(),
  storageReconcile: vi.fn(),
  storageAlert: vi.fn(),
  projectList: vi.fn(),
  policyList: vi.fn(),
  policyCreate: vi.fn(),
  policyUpdate: vi.fn(),
  policyDelete: vi.fn(),
  modalConfirm: vi.fn(),
  messageError: vi.fn(),
  messageSuccess: vi.fn(),
  messageWarning: vi.fn(),
}))

vi.mock('vue-i18n', () => ({ useI18n: () => ({ t: (key: string) => key }) }))
vi.mock('ant-design-vue', () => ({
  message: { error: messageError, success: messageSuccess, warning: messageWarning },
  Modal: { confirm: modalConfirm },
}))
vi.mock('@/api', () => ({
  projectApi: {
    list: projectList,
  },
  storageApi: {
    stats: storageStats,
    previewCleanup: storagePreview,
    executeCleanup: storageExecute,
    reconcileDatasetStorage: storageReconcile,
    getAlert: storageAlert,
    listPolicies: policyList,
    createPolicy: policyCreate,
    updatePolicy: policyUpdate,
    deletePolicy: policyDelete,
  },
}))

const passthrough = (name: string) =>
  defineComponent({ name, setup: (_props, { slots }) => () => h('div', slots.default?.()) })

const buttonStub = defineComponent({
  name: 'AButton',
  props: { disabled: Boolean },
  emits: ['click'],
  setup: (props, { slots, emit }) => () => h('button', { disabled: props.disabled, onClick: () => emit('click') }, slots.default?.()),
})

const popconfirmStub = defineComponent({
  name: 'APopconfirm',
  emits: ['confirm'],
  setup: (_props, { slots, emit }) => () => h('span', { 'data-test': 'confirm', onClick: () => emit('confirm') }, slots.default?.()),
})

function mountPage() {
  return mount(StorageManagementView, {
    global: {
      stubs: {
        AButton: buttonStub,
        ACard: passthrough('ACard'),
        ACheckbox: passthrough('ACheckbox'),
        ACheckboxGroup: passthrough('ACheckboxGroup'),
        ACol: passthrough('ACol'),
        ADescriptions: passthrough('ADescriptions'),
        ADescriptionsItem: passthrough('ADescriptionsItem'),
        ADrawer: passthrough('ADrawer'),
        AForm: passthrough('AForm'),
        AFormItem: passthrough('AFormItem'),
        AInput: passthrough('AInput'),
        AInputNumber: passthrough('AInputNumber'),
        APopconfirm: popconfirmStub,
        ARow: passthrough('ARow'),
        ASelect: passthrough('ASelect'),
        ASpace: passthrough('ASpace'),
        ASwitch: passthrough('ASwitch'),
        ATable: passthrough('ATable'),
        ATag: passthrough('ATag'),
        ATextarea: passthrough('ATextarea'),
      },
    },
  })
}

const STATS = {
  bucket: 'atp',
  total_object_count: 12,
  total_bytes: 2048,
  prefixes: [{ prefix: 'reports/', object_count: 3, total_bytes: 1024 }],
}
const POLICIES = [{ id: 3, name: 'Reports', prefix: 'reports/', retention_days: 14, max_size_gb: 2, enabled: true, description: 'keep reports' }]
const PREVIEW = {
  scanned_object_count: 4,
  expired_object_count: 2,
  size_evicted_count: 0,
  deletable_count: 1,
  blocked_count: 1,
  orphan_reference_count: 1,
  deletable_objects: [{ object_name: 'reports/old.json', last_modified: '2026-07-01T00:00:00Z', referenced_by_count: 0 }],
  blocked_objects: [],
  orphan_references: [],
}

beforeEach(() => {
  vi.clearAllMocks()
  storageStats.mockResolvedValue(STATS)
  policyList.mockResolvedValue(POLICIES)
  storagePreview.mockResolvedValue(PREVIEW)
  storageExecute.mockResolvedValue({ requested_count: 1, deleted_count: 1, skipped_referenced_count: 0, missing_count: 0, repaired_reference_count: 1 })
  storageReconcile.mockResolvedValue({
    project_id: 1,
    dry_run: true,
    scanned_count: 5,
    referenced_count: 3,
    orphan_count: 2,
    orphaned_objects: ['datasets/1/orphan-a.json', 'datasets/1/orphan-b.json'],
    truncated: false,
    deleted_count: 0,
    errors: [],
  })
  storageAlert.mockResolvedValue({ alert: null })
  projectList.mockResolvedValue([{ id: 1, name: 'ATP Demo' }])
  policyCreate.mockResolvedValue({ id: 4 })
  policyUpdate.mockResolvedValue({})
  policyDelete.mockResolvedValue({})
})

describe('StorageManagementView mount', () => {
  it('loads storage statistics and policies and applies enabled prefixes', async () => {
    const wrapper = mountPage()
    await flushPromises()
    const vm = wrapper.vm as any

    expect(storageStats).toHaveBeenCalledOnce()
    expect(policyList).toHaveBeenCalledOnce()
    expect(vm.stats.bucket).toBe('atp')
    expect(vm.selectedPrefixes).toEqual(['reports/'])
    expect(projectList).toHaveBeenCalledOnce()
    expect(vm.datasetProjectId).toBe(1)
    expect(storageAlert).toHaveBeenCalledOnce()
    expect(vm.storageAlert).toBeNull()
  })

  it('generates a cleanup preview with the selected scope', async () => {
    const wrapper = mountPage()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.retentionDays = 7
    vm.selectedPrefixes = ['reports/', 'scripts/']

    await vm.loadPreview()
    expect(storagePreview).toHaveBeenCalledWith({ prefixes: ['reports/', 'scripts/'], retention_days: 7 })
    expect(vm.preview.deletable_count).toBe(1)
  })

  it('executes cleanup only through the confirmation callback and refreshes data', async () => {
    const wrapper = mountPage()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.preview = PREVIEW
    vm.repairOrphans = true

    await wrapper.vm.$nextTick()
    await wrapper.findAll('button').find((button) => button.text() === 'system_pages.storage.execute_cleanup')!.trigger('click')
    expect(modalConfirm).toHaveBeenCalledOnce()
    await modalConfirm.mock.calls[0][0].onOk()

    expect(storageExecute).toHaveBeenCalledWith({
      object_names: ['reports/old.json'],
      repair_orphan_references: true,
    })
    expect(messageSuccess).toHaveBeenCalledWith('system_pages.storage.msg.execute_success')
    expect(storageStats).toHaveBeenCalledTimes(2)
    expect(storagePreview).toHaveBeenCalledTimes(1)
  })

  it('reconciles the selected project before allowing orphan purge', async () => {
    const wrapper = mountPage()
    await flushPromises()
    const vm = wrapper.vm as any

    vm.datasetProjectId = 1
    vm.runDatasetReconcile()
    await flushPromises()

    expect(storageReconcile).toHaveBeenCalledWith(1, false)
    expect(vm.datasetReconcile.orphan_count).toBe(2)
    expect(vm.datasetObjectRows).toEqual([
      { object_name: 'datasets/1/orphan-a.json' },
      { object_name: 'datasets/1/orphan-b.json' },
    ])

    vm.runDatasetReconcile(true)
    expect(modalConfirm).toHaveBeenCalledOnce()
    await modalConfirm.mock.calls[0][0].onOk()

    expect(storageReconcile).toHaveBeenLastCalledWith(1, true)
    expect(messageSuccess).toHaveBeenCalledWith('system_pages.storage.msg.dataset_purge_success')
  })

  it('loads and displays the current storage capacity alert', async () => {
    storageAlert.mockResolvedValueOnce({
      alert: {
        bucket: 'atp',
        total_bytes: 3 * 1024 * 1024 * 1024,
        total_gb: 3,
        threshold_gb: 2,
        triggered_at: '2026-08-12T08:00:00Z',
      },
    })
    const wrapper = mountPage()
    await flushPromises()
    const vm = wrapper.vm as any

    expect(vm.storageAlert.total_gb).toBe(3)
    expect(wrapper.text()).toContain('system_pages.storage.alert_triggered')

    storageAlert.mockResolvedValueOnce({ alert: null })
    await vm.loadAlert()
    expect(vm.storageAlert).toBeNull()
  })

  it('requires a project and a fresh scan before purging', async () => {
    const wrapper = mountPage()
    await flushPromises()
    const vm = wrapper.vm as any

    vm.datasetProjectId = undefined
    vm.runDatasetReconcile()
    expect(messageWarning).toHaveBeenCalledWith('system_pages.storage.msg.select_project')

    vm.datasetProjectId = 1
    vm.datasetReconcile = null
    vm.runDatasetReconcile(true)
    expect(messageWarning).toHaveBeenCalledWith('system_pages.storage.msg.scan_before_purge')
  })

  it('validates and saves both new and edited policies, then deletes a policy', async () => {
    const wrapper = mountPage()
    await flushPromises()
    const vm = wrapper.vm as any

    vm.openCreatePolicy()
    await vm.submitPolicyForm()
    expect(messageWarning).toHaveBeenCalledWith('system_pages.storage.msg.name_prefix_required')

    vm.policyForm.name = 'Scripts'
    vm.policyForm.prefix = 'scripts/'
    vm.policyForm.retention_days = 30
    vm.policyForm.max_size_gb = 1.5
    vm.policyForm.description = 'script files'
    await vm.submitPolicyForm()
    expect(policyCreate).toHaveBeenCalledWith({
      name: 'Scripts', prefix: 'scripts/', retention_days: 30, max_size_gb: 1.5, enabled: true, description: 'script files',
    })

    vm.openEditPolicy(POLICIES[0])
    await vm.submitPolicyForm()
    expect(policyUpdate).toHaveBeenCalledWith(3, expect.objectContaining({ name: 'Reports', prefix: 'reports/' }))

    await vm.handleDeletePolicy(POLICIES[0])
    expect(policyDelete).toHaveBeenCalledWith(3)
    expect(messageSuccess).toHaveBeenCalledWith('system_pages.storage.msg.policy_deleted')
  })

  it('surfaces API errors and resets loading state', async () => {
    storageStats.mockRejectedValueOnce(new Error('storage unavailable'))
    const wrapper = mountPage()
    await flushPromises()
    const vm = wrapper.vm as any

    expect(messageError).toHaveBeenCalledWith('storage unavailable')
    expect(vm.statsLoading).toBe(false)
  })
})
