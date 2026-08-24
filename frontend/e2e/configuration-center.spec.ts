import { test, expect, loginAsAdmin } from './fixtures/mock-api'

const overview = {
  checked_at: '2026-08-24T12:00:00Z',
  project_id: null,
  sections: [
    {
      key: 'environment',
      title: '项目环境',
      description: '项目执行时注入的环境和变量数量',
      route: '/system/environments',
      project_scoped: true,
      readonly: false,
      available: true,
      count: 1,
      entries: [
        {
          domain: 'environment',
          resource_id: 501,
          project_id: 1,
          name: 'E2E 环境',
          status: 'active',
          updated_at: '2026-08-24T11:00:00Z',
          summary: { variable_count: 2, secret_count: 1 },
          route: '/system/environments?project_id=1',
          can_manage: true,
        },
      ],
    },
    {
      key: 'startup',
      title: '启动配置',
      description: '当前进程的安全启动档案',
      route: '/system/startup-config',
      project_scoped: false,
      readonly: true,
      available: true,
      count: 1,
      entries: [],
    },
  ],
}

const revision = {
  id: 701,
  domain: 'environment',
  resource_id: 501,
  project_id: 1,
  resource_name: 'E2E 环境',
  fingerprint: 'revision-fingerprint',
  reason: '变更前备份',
  redacted_payload: { resource: { variables: [{ key: 'BASE_URL', value: '******' }] } },
  created_by: 1,
  created_at: '2026-08-24T10:00:00Z',
  updated_at: '2026-08-24T10:00:00Z',
}

const diff = {
  revision_id: 701,
  domain: 'environment',
  resource_id: 501,
  project_id: 1,
  resource_name: 'E2E 环境',
  historical_fingerprint: 'revision-fingerprint',
  current_fingerprint: 'current-fingerprint',
  current_available: true,
  current_status: 'available',
  changed: true,
  changed_field_count: 1,
  sensitive_changed_field_count: 1,
  truncated: false,
  message: null,
  changes: [{ path: 'resource.variables[0].value', change_type: 'changed', changed: true, sensitive: true }],
  impacts: [],
}

async function installConfigurationMocks(page: Parameters<typeof loginAsAdmin>[0]) {
  let rollbackBody: unknown = null
  await page.route('**/api/v1/configuration-center/overview**', (route) =>
    route.fulfill({ json: overview }),
  )
  await page.route('**/api/v1/configuration-center/revisions?**', (route) =>
    route.fulfill({ json: [revision] }),
  )
  await page.route('**/api/v1/configuration-center/revisions/701/diff', (route) =>
    route.fulfill({ json: diff }),
  )
  await page.route('**/api/v1/configuration-center/revisions/701/rollback', async (route) => {
    rollbackBody = route.request().postDataJSON()
    await route.fulfill({
      json: {
        source_revision_id: 701,
        resource_id: 501,
        domain: 'environment',
        changed: true,
        message: '配置已回退，并生成新的回滚版本',
        revision: { ...revision, id: 702, reason: '配置回滚' },
      },
    })
  })
  return { getRollbackBody: () => rollbackBody }
}

test.describe('configuration center', () => {
  test('管理员可以查看版本差异并通过明确确认词回退', async ({ mockedPage }) => {
    const mockState = await installConfigurationMocks(mockedPage)
    await loginAsAdmin(mockedPage)
    await mockedPage.goto('/system/config')

    await expect(mockedPage.getByRole('heading', { name: /配置中心|Configuration center/i })).toBeVisible()
    await expect(mockedPage.getByRole('heading', { name: 'E2E 环境' })).toBeVisible()
    await expect(mockedPage.getByRole('button', { name: /v701.*变更前备份/i })).toBeVisible()

    await mockedPage.getByRole('button', { name: /v701.*变更前备份/i }).click()
    await expect(mockedPage.getByText(/变更摘要|Change summary/i)).toBeVisible()
    await mockedPage.getByRole('button', { name: /回退到此版本|Rollback to this version/i }).click()
    const confirmation = mockedPage.getByPlaceholder('ROLLBACK')
    await expect(confirmation).toBeVisible()
    await confirmation.fill('ROLLBACK')
    await mockedPage.getByRole('button', { name: /确认回退|Confirm rollback/i }).click()

    await expect.poll(() => mockState.getRollbackBody()).toEqual({ confirmation: 'ROLLBACK' })
    await expect(mockedPage.getByText(/配置已回退|rolled back/i)).toBeVisible()
  })

  test('普通测试角色访问配置中心会被路由权限拦截', async ({ mockedPage }) => {
    await mockedPage.route('**/api/v1/auth/me', (route) =>
      route.fulfill({
        json: {
          id: 8,
          username: 'tester',
          email: 'tester@example.com',
          is_active: true,
          role: 'tester',
        },
      }),
    )
    await loginAsAdmin(mockedPage)
    await mockedPage.goto('/system/config')

    await expect(mockedPage).toHaveURL(/\/dashboard/)
    await expect(mockedPage.getByText('配置中心')).not.toBeVisible()
  })
})
