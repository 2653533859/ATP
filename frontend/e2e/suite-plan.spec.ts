import { test, expect, loginAsAdmin } from './fixtures/mock-api'

async function selectProject(page: import('@playwright/test').Page, targetText: string) {
  const targetAlreadyLoaded = await page.getByText(targetText).isVisible({ timeout: 1_000 }).catch(() => false)
  if (targetAlreadyLoaded) return

  await page.locator('.page-shell .toolbar .ant-select-selector').first().click()
  await page.getByTitle('E2E 测试项目').click()
}

test.describe('suite and plan workflows', () => {
  test('套件页可加载套件、触发执行并打开执行记录', async ({ mockedPage }) => {
    let runRequested = false
    let runsRequested = false

    await mockedPage.route('**/api/v1/suites/200/run', (route) => {
      runRequested = true
      return route.fulfill({ status: 202, json: {
        id: 9201,
        suite_id: 200,
        triggered_by: 1,
        trace_id: 'e2e-suite-trace',
        status: 'pending',
        environment: null,
        duration_ms: null,
        error_message: null,
        result_summary: { total: 1, passed: 0, failed: 0, error: 0 },
        case_run_ids: [],
        created_at: '2026-05-21T10:10:00Z',
      } })
    })
    await mockedPage.route('**/api/v1/suite-runs**', async (route) => {
      runsRequested = true
      return route.fallback()
    })

    await loginAsAdmin(mockedPage)
    await mockedPage.goto('/suites')

    await expect(mockedPage.getByRole('heading', { name: /测试套件|Test Suites/i })).toBeVisible()
    await expect(mockedPage.getByText('E2E 冒烟套件')).toBeVisible()

    const suiteRow = mockedPage.getByRole('row').filter({ hasText: 'E2E 冒烟套件' })
    await suiteRow.getByRole('button', { name: /执行|Run/i }).click()
    await mockedPage.locator('.ant-modal').getByRole('button', { name: /执行|Run/i }).click()

    await expect.poll(() => runRequested, { timeout: 10_000 }).toBeTruthy()
    await expect.poll(() => runsRequested, { timeout: 10_000 }).toBeTruthy()
    await expect(mockedPage.getByText(/执行记录 - E2E 冒烟套件|Run history - E2E 冒烟套件/i)).toBeVisible()
    await expect(mockedPage.getByText(/1 通过|1 passed/i).first()).toBeVisible()
  })

  test('计划页可加载计划、手动触发并查看计划执行记录', async ({ mockedPage }) => {
    let runRequested = false
    let runsRequested = false

    await mockedPage.route('**/api/v1/plans/300/run', (route) => {
      runRequested = true
      return route.fulfill({ status: 202, json: {
        id: 9301,
        plan_id: 300,
        triggered_by: 1,
        trace_id: 'e2e-plan-trace',
        trigger_type: 'manual',
        status: 'pending',
        duration_ms: null,
        error_message: null,
        suite_run_ids: [],
        result_summary: { total: 1, passed: 0, failed: 0, error: 0 },
        created_at: '2026-05-21T10:20:00Z',
      } })
    })
    await mockedPage.route('**/api/v1/plan-runs**', async (route) => {
      runsRequested = true
      return route.fallback()
    })

    await loginAsAdmin(mockedPage)
    await mockedPage.goto('/plans')
    await selectProject(mockedPage, 'E2E 每日计划')

    await expect(mockedPage.getByRole('heading', { name: /测试计划|Test Plans/i })).toBeVisible()
    await expect(mockedPage.getByText('E2E 每日计划')).toBeVisible()

    const planRow = mockedPage.getByRole('row').filter({ hasText: 'E2E 每日计划' })
    await planRow.getByRole('button', { name: /执行|Run/i }).click()
    await expect.poll(() => runRequested, { timeout: 10_000 }).toBeTruthy()

    await planRow.getByRole('button', { name: /记录|History/i }).click()
    await expect.poll(() => runsRequested, { timeout: 10_000 }).toBeTruthy()
    await expect(mockedPage.getByText(/执行记录|Execution history/i).last()).toBeVisible()
    await expect(mockedPage.getByText(/1\s*\/\s*1|1.*passed/i).first()).toBeVisible()
  })
})
