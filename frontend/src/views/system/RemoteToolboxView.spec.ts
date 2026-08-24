import { defineComponent, h } from 'vue'
import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import RemoteToolboxView from './RemoteToolboxView.vue'

const {
  overview,
  push,
  messageError,
  messageSuccess,
} = vi.hoisted(() => ({
  overview: vi.fn(),
  push: vi.fn(),
  messageError: vi.fn(),
  messageSuccess: vi.fn(),
}))

vi.mock('@/api', () => ({
  remoteToolboxApi: { overview },
}))

vi.mock('vue-router', () => ({
  useRouter: () => ({ push }),
}))

vi.mock('vue-i18n', () => ({
  useI18n: () => ({
    locale: { value: 'zh-CN' },
    t: (key: string, params?: Record<string, unknown>) => {
      if (!params) return key
      return `${key}:${JSON.stringify(params)}`
    },
  }),
}))

vi.mock('ant-design-vue', () => ({
  message: { error: messageError, success: messageSuccess },
}))

const passthrough = defineComponent({
  setup: (_props, { slots }) => () => h('div', slots.default?.()),
})

function mountPage() {
  return mount(RemoteToolboxView, {
    global: {
      stubs: {
        AButton: passthrough,
      },
    },
  })
}

const healthyOverview = {
  status: 'degraded' as const,
  checked_at: '2026-08-24T10:00:00Z',
  checks: [
    { key: 'postgres', category: 'infrastructure' as const, status: 'ok' as const, code: 'ok', latency_ms: 1.2, resources: [] },
    { key: 'redis', category: 'infrastructure' as const, status: 'warning' as const, code: 'timeout', latency_ms: 2.4, resources: [] },
    { key: 'minio', category: 'infrastructure' as const, status: 'ok' as const, code: 'ok', latency_ms: 3.1, resources: [] },
    {
      key: 'android_worker', category: 'execution' as const, status: 'ok' as const, code: 'online', latency_ms: 1.5,
      resources: [{ id: 'win-1', name: 'win-1', status: 'ok' as const, summary: '在线', metadata: { capabilities: ['adb', 'android'] } }],
    },
    { key: 'adb', category: 'execution' as const, status: 'ok' as const, code: 'adb_ready', latency_ms: 1.5, resources: [] },
    { key: 'web_worker', category: 'execution' as const, status: 'ok' as const, code: 'local_mode', latency_ms: 0.1, resources: [] },
    { key: 'performance_node', category: 'execution' as const, status: 'warning' as const, code: 'no_node', latency_ms: 4.2, resources: [] },
  ],
}

describe('RemoteToolboxView', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    overview.mockResolvedValue(healthyOverview)
  })

  it('groups all infrastructure and execution checks and exposes safe action links', async () => {
    const wrapper = mountPage()
    await flushPromises()

    expect(overview).toHaveBeenCalledOnce()
    expect(wrapper.findAll('.toolbox-section')).toHaveLength(2)
    expect(wrapper.findAll('.toolbox-check-card')).toHaveLength(7)
    expect(wrapper.text()).toContain('remote_toolbox.code.timeout')
    expect(wrapper.text()).toContain('remote_toolbox.code.adb_ready')
    expect(wrapper.text()).not.toContain('172.31.27.133')

    await wrapper.find('.check-action').trigger('click')
    expect(push).toHaveBeenCalledWith('/system/startup-config')
    wrapper.unmount()
  })

  it('reports a failed refresh without replacing the last successful page state', async () => {
    const wrapper = mountPage()
    await flushPromises()
    overview.mockRejectedValueOnce(new Error('network failure'))

    await (wrapper.vm as any).loadOverview()

    expect(messageError).toHaveBeenCalledWith('remote_toolbox.load_failed')
    expect(wrapper.findAll('.toolbox-check-card')).toHaveLength(7)
    wrapper.unmount()
  })

  it('exports only the already-redacted overview payload', async () => {
    const wrapper = mountPage()
    await flushPromises()
    const createObjectURL = vi.fn(() => 'blob:remote-toolbox')
    const revokeObjectURL = vi.fn()
    vi.stubGlobal('URL', { createObjectURL, revokeObjectURL })
    const click = vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => undefined)

    await (wrapper.vm as any).exportOverview()

    expect(createObjectURL).toHaveBeenCalledOnce()
    expect(click).toHaveBeenCalledOnce()
    expect(revokeObjectURL).toHaveBeenCalledWith('blob:remote-toolbox')
    expect(messageError).not.toHaveBeenCalled()
    expect(messageSuccess).toHaveBeenCalledWith('remote_toolbox.export_success')
    click.mockRestore()
    vi.unstubAllGlobals()
    wrapper.unmount()
  })
})
