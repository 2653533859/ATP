import { test, expect, loginAsAdmin } from './fixtures/mock-api'

test.describe('login flow', () => {
  test('未登录访问根路径应重定向到 /login', async ({ mockedPage }) => {
    await mockedPage.goto('/')
    await expect(mockedPage).toHaveURL(/\/login/)
    await expect(
      mockedPage.getByRole('heading', { name: /ATP (自动化测试平台|Automated Testing Platform)/i }),
    ).toBeVisible()
    await expect(mockedPage.getByPlaceholder(/用户名|Username/i)).toBeVisible()
  })

  test('凭证正确时登录成功并进入 dashboard', async ({ mockedPage }) => {
    await loginAsAdmin(mockedPage)
    await expect(mockedPage).toHaveURL(/\/dashboard/)
  })

  test('登录后 token 写入 localStorage 且 me 接口被调用', async ({ mockedPage }) => {
    let meCalled = false
    await mockedPage.route('**/api/v1/auth/me', (route) => {
      meCalled = true
      return route.fulfill({
        json: { id: 1, username: 'admin', is_active: true, email: 'admin@example.com', role: 'admin' },
      })
    })

    await loginAsAdmin(mockedPage)

    const token = await mockedPage.evaluate(() => localStorage.getItem('access_token'))
    expect(token).toBe('e2e-access-token')
    // me 接口可能被多次触发（refresh、首屏加载等），允许 >=1 次
    expect(meCalled).toBeTruthy()
  })
})
