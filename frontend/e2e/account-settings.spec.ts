import { test, expect, loginAsAdmin } from './fixtures/mock-api'

test('账号设置通过保存按钮提交密码修改', async ({ mockedPage }) => {
  await loginAsAdmin(mockedPage)

  let submitted: Record<string, unknown> | undefined
  await mockedPage.route('**/api/v1/auth/me', async (route) => {
    if (route.request().method() === 'PATCH') {
      submitted = route.request().postDataJSON()
      return route.fulfill({ json: { authenticated: true } })
    }
    return route.fulfill({
      json: { id: 1, username: 'admin', email: 'admin@example.com', role: 'admin', is_active: true },
    })
  })

  await mockedPage.goto('/account')
  await mockedPage.locator('input[autocomplete="current-password"]').fill('old-password')
  await mockedPage.locator('input[autocomplete="new-password"]').first().fill('new-password')
  await mockedPage.locator('input[autocomplete="new-password"]').last().fill('new-password')
  await mockedPage.getByRole('button', { name: /保存|Save/ }).click()

  await expect.poll(() => submitted).toEqual({
    current_password: 'old-password',
    username: 'admin',
    email: 'admin@example.com',
    new_password: 'new-password',
  })
  await expect(mockedPage.locator('input[autocomplete="current-password"]')).toHaveValue('')
})
