import { test, expect, loginAsAdmin } from './fixtures/mock-api'
import * as data from './fixtures/mock-data'

test.describe('run detail report', () => {
  test('打开已完成 run 详情可见步骤 passed 标签', async ({ mockedPage }) => {
    await mockedPage.route('**/api/v1/runs/9000', (route) =>
      route.fulfill({ json: data.completedRun }),
    )
    await mockedPage.route('**/api/v1/runs/9000/bug-link', (route) =>
      route.fulfill({ json: null, status: 404 }),
    )
    await mockedPage.route('**/api/v1/bug-trackers**', (route) =>
      route.fulfill({ json: [] }),
    )
    await mockedPage.route('**/api/v1/defects?**', (route) =>
      route.fulfill({ json: { items: [], total: 0, page: 1, page_size: 20 } }),
    )

    await loginAsAdmin(mockedPage)
    await mockedPage.goto('/runs/9000')

    // 步骤名 "主请求" 应渲染
    await expect(mockedPage.getByText('主请求').first()).toBeVisible({ timeout: 10_000 })
    // passed 状态文字（小写 enum） 应至少出现一次
    await expect(mockedPage.getByText(/passed/i).first()).toBeVisible()
  })
})
