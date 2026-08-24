import { test as base, type Page, expect } from '@playwright/test'
import * as data from './mock-data'

/**
 * P2.4 E2E 共享 fixture：
 * - 在 page.goto 之前 page.route 拦截 /api/v1/** 返回 mock；
 * - loginAsAdmin(page) 走真登录流程（mock /auth/login），让前端 auth store
 *   自然通过 /auth/me 恢复 Cookie 会话，避免硬塞 token 带来的状态漂移。
 * - 收集 pageerror：测试结束时任何非白名单的未捕获页面异常都会让用例失败，
 *   所有 spec 自动获得该保护，无需各自监听。
 *
 * 选择器优先级（参考 Playwright 官方）：role > label > text。
 */

// 已知良性的浏览器噪声，不视为页面崩溃
const BENIGN_PAGE_ERRORS = [
  'ResizeObserver loop completed with undelivered notifications.',
  'ResizeObserver loop limit exceeded',
]

export const test = base.extend<{ mockedPage: Page }>({
  mockedPage: async ({ page }, use) => {
    const pageErrors: string[] = []
    page.on('pageerror', (error) => pageErrors.push(error.message))
    await installCommonMocks(page)
    await use(page)
    const unexpected = pageErrors.filter(
      (message) => !BENIGN_PAGE_ERRORS.some((benign) => message.includes(benign)),
    )
    expect(unexpected, 'uncaught page errors during test').toEqual([])
  },
})

export { expect }

/** 注入所有 spec 共用的接口 mock。spec 内可继续 page.route 覆盖。*/
export async function installCommonMocks(page: Page) {
  // auth
  let authenticated = false
  await page.route('**/api/v1/auth/login', (route) => {
    authenticated = true
    return route.fulfill({ json: data.adminTokens })
  })
  await page.route('**/api/v1/auth/me', (route) => {
    if (!authenticated) {
      return route.fulfill({ status: 401, json: { detail: 'Not authenticated' } })
    }
    return route.fulfill({ json: data.adminUser })
  })
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
    route.fulfill({ json: data.cases }),
  )
  await page.route('**/api/v1/runs?**', (route) =>
    route.fulfill({ json: { items: [data.completedRun], total: 1, page: 1, page_size: 5 } }),
  )
  // MainLayout 登录后会轮询该聚合接口更新侧栏徽标；未 mock 时真实后端的 401
  // 会触发响应拦截器清理会话，导致登录回归用例被错误重定向回 /login。
  await page.route('**/api/v1/workbench/overview**', (route) =>
    route.fulfill({ json: data.workbenchOverview }),
  )

  await page.route('**/api/v1/environments**', (route) =>
    route.fulfill({ json: data.environments }),
  )

  await page.route('**/api/v1/suites/200/run', (route) =>
    route.fulfill({ status: 202, json: data.triggeredSuiteRun }),
  )
  await page.route('**/api/v1/suite-runs**', (route) =>
    route.fulfill({ json: data.suiteRuns }),
  )
  await page.route('**/api/v1/suites**', (route) => {
    if (route.request().method() === 'GET') {
      return route.fulfill({ json: data.suites })
    }
    return route.fulfill({ status: 201, json: data.suites[0] })
  })

  await page.route('**/api/v1/plans/300/run', (route) =>
    route.fulfill({ status: 202, json: data.triggeredPlanRun }),
  )
  await page.route('**/api/v1/plan-runs**', (route) =>
    route.fulfill({ json: data.planRuns }),
  )
  await page.route('**/api/v1/plans**', (route) => {
    if (route.request().method() === 'GET') {
      return route.fulfill({ json: data.plans })
    }
    return route.fulfill({ status: 201, json: data.plans[0] })
  })

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
  // Ant Design Vue 会对两个汉字的按钮文案自动插入空格（“登录”→“登 录”）。
  // 允许该渲染差异，同时保留英文环境的登录文案匹配。
  await page.getByRole('button', { name: /登\s*录|Login|Sign in/i }).click()
  await page.waitForURL(/\/dashboard/, { timeout: 10_000 })
}
