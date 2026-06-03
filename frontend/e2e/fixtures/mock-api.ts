import { test as base, type Page, expect } from '@playwright/test'
import * as data from './mock-data'

/**
 * P2.4 E2E 共享 fixture：
 * - 在 page.goto 之前 page.route 拦截 /api/v1/** 返回 mock；
 * - loginAsAdmin(page) 走真登录流程（mock /auth/login），让前端 auth store
 *   自然写入 localStorage，避免硬塞 token 带来的状态漂移。
 *
 * 选择器优先级（参考 Playwright 官方）：role > label > text。
 */
export const test = base.extend<{ mockedPage: Page }>({
  mockedPage: async ({ page }, use) => {
    await installCommonMocks(page)
    await use(page)
  },
})

export { expect }

/** 注入所有 spec 共用的接口 mock。spec 内可继续 page.route 覆盖。*/
export async function installCommonMocks(page: Page) {
  // auth
  await page.route('**/api/v1/auth/login', (route) =>
    route.fulfill({ json: data.adminTokens }),
  )
  await page.route('**/api/v1/auth/me', (route) =>
    route.fulfill({ json: data.adminUser }),
  )
  await page.route('**/api/v1/auth/refresh', (route) =>
    route.fulfill({ json: data.adminTokens }),
  )

  // projects + modules + cases 列表（dashboard / list 等通用读）
  await page.route('**/api/v1/projects', (route) => {
    if (route.request().method() === 'GET') {
      return route.fulfill({ json: data.projects })
    }
    return route.continue()
  })
  await page.route('**/api/v1/projects/1/modules', (route) =>
    route.fulfill({ json: data.modules }),
  )
  await page.route('**/api/v1/cases?**', (route) =>
    route.fulfill({ json: { items: data.cases, total: data.cases.length, page: 1, page_size: 20 } }),
  )

  // user/session-adjacent best-effort reads used by first-screen dashboards.
  await page.route('**/api/v1/users/me/settings/dashboard.layout', (route) =>
    route.fulfill({ status: 404, json: { detail: 'Not found' } }),
  )
  await page.route('**/api/v1/storage/alert', (route) =>
    route.fulfill({ json: { alert: null } }),
  )
  await page.route('**/api/v1/traces/config', (route) =>
    route.fulfill({ json: { jaeger_ui_url: '' } }),
  )

  // statistics
  await page.route('**/api/v1/statistics/overview**', (route) =>
    route.fulfill({ json: data.overviewStats }),
  )
  await page.route('**/api/v1/statistics/pass-rate-trend**', (route) =>
    route.fulfill({ json: data.passRateTrend }),
  )
  await page.route('**/api/v1/statistics/duration-trend**', (route) =>
    route.fulfill({ json: data.durationTrend }),
  )
  await page.route('**/api/v1/statistics/**', (route) =>
    route.fulfill({ json: [] }),
  )

  // WebSocket：mock 模式直接拒绝建连，让前端走 fallback；
  // Playwright 的 page.route 不直接支持 ws，但失败会被 utils/websocket.ts 自动重试上限后吞掉。
}

/** 走真登录流程：点击登录 → mock /auth/login 返回 token → 进入 dashboard */
export async function loginAsAdmin(page: Page) {
  await page.goto('/login')
  await page.getByPlaceholder(/用户名|Username/i).fill('admin')
  await page.getByPlaceholder(/密码|Password/i).fill('Admin@123456')
  await page.getByRole('button', { name: /登录|Login|Sign in/i }).click()
  await page.waitForURL(/\/dashboard/, { timeout: 10_000 })
}
