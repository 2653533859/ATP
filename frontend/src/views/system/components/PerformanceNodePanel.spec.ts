import { defineComponent, h } from 'vue'
import { mount } from '@vue/test-utils'
import { describe, expect, it, vi } from 'vitest'

import PerformanceNodePanel from './PerformanceNodePanel.vue'

vi.mock('vue-i18n', () => ({
  useI18n: () => ({
    t: (key: string, params?: Record<string, unknown> | string) => {
      if (typeof params === 'string') return `${key}:${params}`
      if (params && 'value' in params) return `${key}:${String(params.value)}`
      return key
    },
  }),
}))

const buttonStub = defineComponent({
  emits: ['click'],
  setup: (_props, { emit, slots }) => () => h('button', { onClick: () => emit('click') }, slots.default?.()),
})

const popconfirmStub = defineComponent({
  emits: ['confirm'],
  setup: (_props, { emit, slots }) => () => h('div', [
    slots.default?.(),
    h('button', { class: 'confirm-delete', onClick: () => emit('confirm') }, 'confirm'),
  ]),
})

const passthrough = defineComponent({
  setup: (_props, { slots, attrs }) => () => h('div', attrs, slots.default?.()),
})

function node(overrides: Record<string, unknown> = {}) {
  return {
    id: 1,
    name: 'Load node',
    node_id: 'node-1',
    queue_name: 'performance.node-1',
    status: 'online',
    max_vus: 100,
    max_concurrency: 3,
    capabilities: { executors: ['k6', 'jmeter'] },
    enabled: true,
    last_heartbeat_at: '2026-09-08T09:05:00',
    last_error: 'worker unavailable',
    created_at: '2026-09-08T08:00:00',
    updated_at: '2026-09-08T09:05:00',
    ...overrides,
  } as any
}

function mountPanel(nodes = [node()]) {
  return mount(PerformanceNodePanel, {
    props: { nodes, loading: false },
    global: {
      stubs: {
        AButton: buttonStub,
        APopconfirm: popconfirmStub,
        ASpace: passthrough,
        AEmpty: passthrough,
        ABadge: passthrough,
        ATag: passthrough,
        DeleteOutlined: true,
        EditOutlined: true,
        PlusOutlined: true,
        ReloadOutlined: true,
      },
    },
  })
}

describe('PerformanceNodePanel', () => {
  it('preserves status, executor, capacity, heartbeat and error presentation', () => {
    const wrapper = mountPanel([
      node(),
      node({ id: 2, name: 'String node', capabilities: { executors: 'k6, locust' }, status: 'draining' }),
      node({ id: 3, name: 'Legacy node', capabilities: { executor: 'jmeter' }, status: 'disabled' }),
      node({ id: 4, name: 'Fallback node', capabilities: {}, status: 'offline', max_vus: null, max_concurrency: null }),
    ])

    const text = wrapper.text()
    expect(text).toContain('performance.node_status.online:online')
    expect(text).toContain('k6, jmeter')
    expect(text).toContain('k6, locust')
    expect(text).toContain('jmeter')
    expect(text).toContain('performance.node_vus_limit:∞')
    expect(text).toContain('performance.node_concurrency_limit:∞')
    expect(text).toContain('worker unavailable')
    expect(text).toContain('performance.node_last_heartbeat:9/8 09:05')
  })

  it('emits refresh, create, edit and delete actions', async () => {
    const item = node()
    const wrapper = mountPanel([item])
    const buttons = wrapper.findAll('button')

    await buttons[0].trigger('click')
    await buttons[1].trigger('click')
    await buttons[2].trigger('click')
    await wrapper.find('.confirm-delete').trigger('click')

    expect(wrapper.emitted('refresh')).toHaveLength(1)
    expect(wrapper.emitted('create')).toHaveLength(1)
    expect(wrapper.emitted('edit')).toEqual([[item]])
    expect(wrapper.emitted('delete')).toEqual([[item]])
  })
})
