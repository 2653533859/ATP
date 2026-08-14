import { flushPromises, mount } from '@vue/test-utils'
import { defineComponent, h } from 'vue'
import dayjs from 'dayjs'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import AuditLogList from './AuditLogList.vue'

const { auditList, auditExport, messageError, messageSuccess } = vi.hoisted(() => ({
  auditList: vi.fn(),
  auditExport: vi.fn(),
  messageError: vi.fn(),
  messageSuccess: vi.fn(),
}))

vi.mock('vue-i18n', () => ({ useI18n: () => ({ t: (key: string) => key }) }))
vi.mock('ant-design-vue', () => ({ message: { error: messageError, success: messageSuccess } }))
vi.mock('@/api', () => ({ auditLogApi: { list: auditList, export: auditExport } }))

const passthrough = (name: string) =>
  defineComponent({ name, setup: (_props, { slots }) => () => h('div', slots.default?.()) })

function mountPage() {
  return mount(AuditLogList, {
    global: {
      stubs: {
        AButton: passthrough('AButton'),
        ACard: passthrough('ACard'),
        AForm: passthrough('AForm'),
        AFormItem: passthrough('AFormItem'),
        AInputNumber: passthrough('AInputNumber'),
        ASelect: passthrough('ASelect'),
        ARangePicker: passthrough('ARangePicker'),
        ATable: passthrough('ATable'),
        APagination: passthrough('APagination'),
        ATag: passthrough('ATag'),
      },
    },
  })
}

beforeEach(() => {
  vi.clearAllMocks()
  auditList.mockResolvedValue({ items: [], total: 0, page: 1, page_size: 50 })
  auditExport.mockResolvedValue(new Blob(['id,action\n']))
})

describe('AuditLogList', () => {
  it('loads and forwards an ISO time window with the audit query', async () => {
    const wrapper = mountPage()
    await flushPromises()
    const vm = wrapper.vm as any

    expect(vm.actionOptions).toEqual(
      expect.arrayContaining([
        { label: 'audit_log_cleanup', value: 'audit_log_cleanup' },
        { label: 'audit_log_export', value: 'audit_log_export' },
      ]),
    )

    vm.dateRange = [dayjs('2026-08-01T00:00:00Z'), dayjs('2026-08-02T00:00:00Z')]
    await vm.loadLogs(1, 100)

    expect(auditList).toHaveBeenLastCalledWith({
      project_id: undefined,
      user_id: undefined,
      action: undefined,
      created_from: '2026-08-01T00:00:00.000Z',
      created_to: '2026-08-02T00:00:00.000Z',
      page: 1,
      page_size: 100,
    })
  })

  it('clears the time window when filters are reset', async () => {
    const wrapper = mountPage()
    await flushPromises()
    const vm = wrapper.vm as any

    vm.dateRange = [dayjs(), dayjs()]
    vm.filter.action = 'login'
    vm.onReset()
    await flushPromises()

    expect(vm.dateRange).toBeNull()
    expect(vm.filter.action).toBeUndefined()
    expect(auditList).toHaveBeenLastCalledWith({
      project_id: undefined,
      user_id: undefined,
      action: undefined,
      created_from: undefined,
      created_to: undefined,
      page: 1,
      page_size: 50,
    })
  })

  it('exports the current filters with a bounded request', async () => {
    const wrapper = mountPage()
    await flushPromises()
    const vm = wrapper.vm as any
    const createObjectURL = vi.fn(() => 'blob:audit')
    const revokeObjectURL = vi.fn()
    vi.stubGlobal('URL', { createObjectURL, revokeObjectURL })
    vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => undefined)

    vm.filter.project_id = 7
    vm.filter.action = 'login'
    vm.dateRange = [dayjs('2026-08-01T00:00:00Z'), dayjs('2026-08-02T00:00:00Z')]
    await vm.exportLogs()

    expect(auditExport).toHaveBeenCalledWith({
      project_id: 7,
      user_id: undefined,
      action: 'login',
      created_from: '2026-08-01T00:00:00.000Z',
      created_to: '2026-08-02T00:00:00.000Z',
      limit: 5000,
    })
    expect(createObjectURL).toHaveBeenCalledOnce()
    expect(revokeObjectURL).toHaveBeenCalledWith('blob:audit')
    expect(messageSuccess).toHaveBeenCalledWith('audit_logs.export_success')
  })
})
