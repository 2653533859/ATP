import { defineComponent, h } from 'vue'
import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import RemoteNodesView from './RemoteNodesView.vue'

const {
  list,
  grants,
  createGrant,
  revokeGrant,
  userList,
  projectList,
  messageError,
  messageSuccess,
} = vi.hoisted(() => ({
  list: vi.fn(),
  grants: vi.fn(),
  createGrant: vi.fn(),
  revokeGrant: vi.fn(),
  userList: vi.fn(),
  projectList: vi.fn(),
  messageError: vi.fn(),
  messageSuccess: vi.fn(),
}))

vi.mock('@/api', () => ({
  remoteNodesApi: { list, grants, createGrant, revokeGrant },
  userApi: { list: userList },
  projectApi: { list: projectList },
}))

vi.mock('vue-i18n', () => ({
  useI18n: () => ({
    locale: { value: 'zh-CN' },
    t: (key: string) => key,
  }),
}))

vi.mock('ant-design-vue', () => ({
  message: { error: messageError, success: messageSuccess },
}))

const passthrough = defineComponent({
  setup: (_props, { slots }) => () => h('div', slots.default?.()),
})

const empty = defineComponent({
  setup: () => () => h('div'),
})

function mountPage() {
  return mount(RemoteNodesView, {
    global: {
      stubs: {
        AButton: passthrough,
        ATable: empty,
        ADrawer: empty,
        AModal: empty,
      },
    },
  })
}

const nodes = [
  {
    client_id: 'win-a',
    machine_name: 'PC-A',
    local_api_origin: null,
    status: 'online' as const,
    last_seen_at: '2026-11-02T10:00:00Z',
    capabilities: [],
  },
]

const grantRows = [
  {
    id: 1,
    node_client_id: 'win-a',
    subject_type: 'user' as const,
    subject_id: 10,
    subject_name: 'eng',
    access_level: 'read_write' as const,
    created_by: 'admin',
    created_at: '2026-11-02T10:00:00Z',
    revoked_at: null,
    revoked_by: null,
  },
]

describe('RemoteNodesView', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    list.mockResolvedValue(nodes)
    grants.mockResolvedValue(grantRows)
    userList.mockResolvedValue([{ id: 10, username: 'eng', email: 'eng@test.local', role: 'engineer', is_active: true }])
    projectList.mockResolvedValue([{ id: 5, name: 'P5' }])
    createGrant.mockResolvedValue(grantRows[0])
    revokeGrant.mockResolvedValue({ ...grantRows[0], revoked_at: '2026-11-02T11:00:00Z', revoked_by: 'admin' })
  })

  it('loads nodes on mount and opens the grant drawer per node', async () => {
    const wrapper = mountPage()
    await flushPromises()
    expect(list).toHaveBeenCalledOnce()

    await (wrapper.vm as any).openGrants(nodes[0])
    await flushPromises()
    expect(grants).toHaveBeenCalledWith('win-a', false)
    expect((wrapper.vm as any).grants).toHaveLength(1)

    ;(wrapper.vm as any).includeRevoked = true
    await (wrapper.vm as any).loadGrants()
    expect(grants).toHaveBeenCalledWith('win-a', true)
    wrapper.unmount()
  })

  it('creates a grant for the selected subject and level', async () => {
    const wrapper = mountPage()
    await flushPromises()
    await (wrapper.vm as any).openGrants(nodes[0])
    await flushPromises()

    ;(wrapper.vm as any).openCreateModal()
    await flushPromises()
    expect(userList).toHaveBeenCalled()

    Object.assign((wrapper.vm as any).createForm, { subject_type: 'user', subject_id: 10, access_level: 'read_only' })
    await (wrapper.vm as any).submitCreate()
    await flushPromises()

    expect(createGrant).toHaveBeenCalledWith('win-a', {
      subject_type: 'user',
      subject_id: 10,
      access_level: 'read_only',
    })
    expect(messageSuccess).toHaveBeenCalledWith('remote_nodes.create_success')
    wrapper.unmount()
  })

  it('revokes a grant and reloads the list', async () => {
    const wrapper = mountPage()
    await flushPromises()
    await (wrapper.vm as any).openGrants(nodes[0])
    await flushPromises()

    await (wrapper.vm as any).handleRevoke(grantRows[0])
    await flushPromises()

    expect(revokeGrant).toHaveBeenCalledWith('win-a', 1)
    expect(messageSuccess).toHaveBeenCalledWith('remote_nodes.revoke_success')
    expect(grants).toHaveBeenCalledTimes(2)
    wrapper.unmount()
  })

  it('reports failures without clearing the existing node list', async () => {
    const wrapper = mountPage()
    await flushPromises()
    list.mockRejectedValueOnce(new Error('network failure'))

    await (wrapper.vm as any).loadNodes()

    expect(messageError).toHaveBeenCalledWith('remote_nodes.load_failed')
    expect((wrapper.vm as any).nodes).toHaveLength(1)
    wrapper.unmount()
  })
})
