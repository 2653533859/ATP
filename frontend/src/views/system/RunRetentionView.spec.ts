import { flushPromises, mount } from '@vue/test-utils'
import { defineComponent, h } from 'vue'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import RunRetentionView from './RunRetentionView.vue'

const { preview, perProjectPreview, run, messageError, messageSuccess } = vi.hoisted(() => ({
  preview: vi.fn(),
  perProjectPreview: vi.fn(),
  run: vi.fn(),
  messageError: vi.fn(),
  messageSuccess: vi.fn(),
}))

vi.mock('vue-i18n', () => ({ useI18n: () => ({ t: (key: string) => key }) }))
vi.mock('ant-design-vue', () => ({
  message: { error: messageError, success: messageSuccess },
}))
vi.mock('@/api', () => ({
  adminRunRetentionApi: { preview, perProjectPreview, run },
}))

const passthrough = (name: string) =>
  defineComponent({ name, setup: (_props, { slots }) => () => h('div', slots.default?.()) })

beforeEach(() => {
  vi.clearAllMocks()
  preview.mockResolvedValue({
    cutoff: '2026-08-01T00:00:00Z',
    retention_days: 30,
    plan_runs: 1,
    suite_runs: 1,
    test_runs: 1,
    mobile_runs: 0,
    estimated_objects: 0,
    estimated_objects_sampled: false,
  })
  perProjectPreview.mockResolvedValue({
    global: {
      retention_days: 30,
      plan_runs: 1,
      suite_runs: 1,
      test_runs: 1,
      mobile_runs: 0,
      estimated_objects: 0,
      estimated_objects_sampled: false,
    },
    projects: [],
  })
  run.mockResolvedValue({
    cutoff: '2026-08-01T00:00:00Z',
    retention_days: 30,
    plan_runs: 1,
    suite_runs: 1,
    test_runs: 1,
    mobile_runs: 0,
    deleted_objects: 2,
    projects: [],
  })
})

function mountPage() {
  return mount(RunRetentionView, {
    global: {
      stubs: {
        AAlert: passthrough('AAlert'),
        AButton: passthrough('AButton'),
        ACard: passthrough('ACard'),
        ACol: passthrough('ACol'),
        ADescriptions: passthrough('ADescriptions'),
        ADescriptionsItem: passthrough('ADescriptionsItem'),
        AEmpty: passthrough('AEmpty'),
        AForm: passthrough('AForm'),
        AFormItem: passthrough('AFormItem'),
        AInputNumber: passthrough('AInputNumber'),
        APopconfirm: passthrough('APopconfirm'),
        ARow: passthrough('ARow'),
        ATable: passthrough('ATable'),
        ATag: passthrough('ATag'),
      },
    },
  })
}

describe('RunRetentionView', () => {
  it('refreshes global and project previews after cleanup', async () => {
    const wrapper = mountPage()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.filter.days = 30

    await vm.handleExecute()

    expect(run).toHaveBeenCalledWith(30)
    expect(preview).toHaveBeenCalledWith(30)
    expect(perProjectPreview).toHaveBeenCalledOnce()
    expect(messageSuccess).toHaveBeenCalledWith('system_pages.run_retention.execute_success')
    expect(vm.lastResult.deleted_objects).toBe(2)
    expect(messageError).not.toHaveBeenCalled()
  })

  it('includes project override runs in the cleanup confirmation scope', async () => {
    preview.mockResolvedValue({
      cutoff: '2026-08-01T00:00:00Z',
      retention_days: 30,
      plan_runs: 0,
      suite_runs: 0,
      test_runs: 0,
      mobile_runs: 0,
      estimated_objects: 0,
      estimated_objects_sampled: false,
    })
    perProjectPreview.mockResolvedValue({
      global: {
        retention_days: 30,
        plan_runs: 0,
        suite_runs: 0,
        test_runs: 0,
        mobile_runs: 0,
        estimated_objects: 0,
        estimated_objects_sampled: false,
      },
      projects: [{
        project_id: 7,
        project_name: 'Override project',
        retention_days: 7,
        plan_runs: 1,
        suite_runs: 0,
        test_runs: 2,
        mobile_runs: 1,
        estimated_objects: 4,
        estimated_objects_sampled: true,
      }],
    })

    const wrapper = mountPage()
    const vm = wrapper.vm as any
    await vm.loadAllPreviews()

    expect(vm.totalToDelete).toBe(4)
    expect(vm.estimatedObjectsToDelete).toBe(4)
    expect(vm.estimatedObjectsSampled).toBe(true)
    expect(vm.previewsReady).toBe(true)
  })
})
