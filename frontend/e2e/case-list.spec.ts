import { test, expect, loginAsAdmin } from './fixtures/mock-api'
import * as data from './fixtures/mock-data'

test.describe('case list', () => {
  test('进入 /cases 触发项目列表请求', async ({ mockedPage }) => {
    let projectsHit = false
    await mockedPage.route('**/api/v1/projects', (route) => {
      if (route.request().method() === 'GET') {
        projectsHit = true
        return route.fulfill({ json: data.projects })
      }
      return route.continue()
    })

    await loginAsAdmin(mockedPage)
    await mockedPage.goto('/cases')

    await expect.poll(() => projectsHit, { timeout: 10_000 }).toBeTruthy()
    // 标题或导航中应出现 "用例" 二字（CaseList.vue 用 t('case.title')）
    // 未捕获页面异常由 mockedPage fixture 统一断言（见 fixtures/mock-api.ts）
    await expect(mockedPage.getByRole('heading').filter({ hasText: /用例|Cases/ }).first()).toBeVisible({ timeout: 10_000 })
  })
})
