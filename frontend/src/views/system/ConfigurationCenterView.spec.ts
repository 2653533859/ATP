import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import ConfigurationCenterView from './ConfigurationCenterView.vue'

const {
  projectList,
  authRole,
  overview,
  revisions,
  diff,
  createRevision,
  rollback,
  push,
  messageError,
  messageSuccess,
} = vi.hoisted(() => ({
  projectList: vi.fn(),
  authRole: 'admin' as string,
  overview: vi.fn(),
  revisions: vi.fn(),
  diff: vi.fn(),
  createRevision: vi.fn(),
  rollback: vi.fn(),
  push: vi.fn(),
  messageError: vi.fn(),
  messageSuccess: vi.fn(),
}))

vi.mock('@/api', () => ({
  projectApi: { list: projectList },
  configurationCenterApi: { overview, revisions, diff, createRevision, rollback },
}))
vi.mock('vue-router', () => ({ useRouter: () => ({ push }) }))
vi.mock('@/stores/auth', () => ({ useAuthStore: () => ({ user: { role: authRole } }) }))
vi.mock('@/utils/permissions', () => ({ hasAnyRole: (role: string, roles: string[]) => roles.includes(role) }))
vi.mock('vue-i18n', () => ({
  useI18n: () => ({
    t: (key: string, params?: Record<string, unknown>) => params ? `${key}:${JSON.stringify(params)}` : key,
  }),
}))
vi.mock('ant-design-vue', () => ({ message: { error: messageError, success: messageSuccess } }))

const PROJECTS = [{ id: 1, name: '订单平台', owner_id: 1 }]
const RESOURCE = {
  domain: 'environment',
  resource_id: 11,
  project_id: 1,
  name: '测试环境',
  status: 'active',
  updated_at: '2026-08-24T10:00:00Z',
  summary: { variable_count: 3, enabled: true },
  route: '/system/environments',
  can_manage: true,
}
const OVERVIEW = {
  checked_at: '2026-08-24T10:00:00Z',
  project_id: null,
  sections: [
    { key: 'environment', title: '环境配置', description: '项目运行环境', route: '/system/environments', project_scoped: true, readonly: false, available: true, count: 1, entries: [RESOURCE] },
    { key: 'ai_llm', title: 'AI 模型', description: '模型服务', route: '/system/ai-llm-configs', project_scoped: false, readonly: false, available: true, count: 0, entries: [] },
  ],
}
const REVISION = {
  id: 41,
  domain: 'environment',
  resource_id: 11,
  project_id: 1,
  resource_name: '测试环境',
  fingerprint: 'abc123',
  reason: '登录流程调整',
  redacted_payload: { variable_count: 3 },
  created_by: 1,
  created_at: '2026-08-24T10:01:00Z',
  updated_at: '2026-08-24T10:01:00Z',
}
const DIFF = {
  revision_id: 41,
  domain: 'environment',
  resource_id: 11,
  project_id: 1,
  resource_name: '测试环境',
  historical_fingerprint: 'abc123',
  current_fingerprint: 'def456',
  current_available: true,
  current_status: 'available' as const,
  changed: true,
  changed_field_count: 1,
  sensitive_changed_field_count: 1,
  truncated: false,
  message: null,
  changes: [{ path: '$.variables.token', change_type: 'changed' as const, changed: true, sensitive: true }],
  impacts: [],
}

function mountPage() {
  return mount(ConfigurationCenterView)
}

beforeEach(() => {
  vi.clearAllMocks()
  projectList.mockResolvedValue(PROJECTS)
  overview.mockResolvedValue(OVERVIEW)
  revisions.mockResolvedValue([REVISION])
  diff.mockResolvedValue(DIFF)
  createRevision.mockResolvedValue(REVISION)
  rollback.mockResolvedValue({
    source_revision_id: REVISION.id,
    resource_id: RESOURCE.resource_id,
    domain: RESOURCE.domain,
    changed: true,
    message: '配置已回退',
    revision: { ...REVISION, id: 42 },
  })
})

describe('ConfigurationCenterView', () => {
  it('loads the project-scoped catalog and selected resource history', async () => {
    const wrapper = mountPage()
    await flushPromises()

    expect(projectList).toHaveBeenCalledOnce()
    expect(overview).toHaveBeenCalledWith(null)
    expect(revisions).toHaveBeenCalledWith({ domain: 'environment', resource_id: 11, project_id: 1, limit: 50 })
    expect(wrapper.text()).toContain('测试环境')
    expect(wrapper.text()).toContain('v41')
    expect(wrapper.findAll('.governance-link')).toHaveLength(4)
    await wrapper.find('.governance-link').trigger('click')
    expect(push).toHaveBeenCalledWith('/system/users')
    wrapper.unmount()
  })

  it('captures a snapshot and loads its diff without exposing secret values', async () => {
    const wrapper = mountPage()
    await flushPromises()
    const vm = wrapper.vm as any

    vm.revisionReason = '登录流程调整'
    await vm.createSnapshot()

    expect(createRevision).toHaveBeenCalledWith({ domain: 'environment', resource_id: 11, reason: '登录流程调整' })
    expect(diff).toHaveBeenCalledWith(REVISION.id)
    expect(wrapper.text()).toContain('configuration_center.redacted')
    expect(wrapper.text()).not.toContain('secret-value')
    expect(messageSuccess).toHaveBeenCalledWith('configuration_center.snapshot_success')
    wrapper.unmount()
  })

  it('requires the explicit ROLLBACK token before restoring a revision', async () => {
    const wrapper = mountPage()
    await flushPromises()
    const vm = wrapper.vm as any

    await vm.selectRevision(REVISION)
    vm.openRollback()
    expect(vm.rollbackOpen).toBe(true)
    await vm.confirmRollback()
    expect(rollback).not.toHaveBeenCalled()

    vm.rollbackToken = 'ROLLBACK'
    await vm.confirmRollback()
    expect(rollback).toHaveBeenCalledWith(REVISION.id)
    expect(messageSuccess).toHaveBeenCalledWith('配置已回退')
    wrapper.unmount()
  })

  it('keeps the catalog visible and reports a refresh failure', async () => {
    const wrapper = mountPage()
    await flushPromises()
    overview.mockRejectedValueOnce(new Error('network failure'))

    await vmLoadOverview(wrapper)

    expect(messageError).not.toHaveBeenCalled()
    expect((wrapper.vm as any).loadError).toBe('network failure')
    expect(wrapper.text()).toContain('测试环境')
    wrapper.unmount()
  })
})

async function vmLoadOverview(wrapper: ReturnType<typeof mount>) {
  await (wrapper.vm as any).loadOverview()
}
