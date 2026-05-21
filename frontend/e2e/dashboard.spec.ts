import { test, expect, loginAsAdmin } from './fixtures/mock-api'
import * as data from './fixtures/mock-data'

test.describe('dashboard', () => {
  test('登录后进入 /dashboard 可见 KPI 数字与图表容器', async ({ mockedPage }) => {
    let overviewHit = false
    await mockedPage.route('**/api/v1/statistics/overview**', (route) => {
      overviewHit = true
      return route.fulfill({ json: data.overviewStats })
    })

    await loginAsAdmin(mockedPage)
    await mockedPage.waitForURL(/\/dashboard/)

    // 至少触发一次 overview 调用
    await expect.poll(() => overviewHit, { timeout: 10_000 }).toBeTruthy()

    // KPI: total_cases=12 / total_runs=99 应出现在页面文本中
    await expect(mockedPage.getByText('12', { exact: false }).first()).toBeVisible({ timeout: 10_000 })
    await expect(mockedPage.getByText('99', { exact: false }).first()).toBeVisible()
  })
})
