import { test, expect, loginAsAdmin } from './fixtures/mock-api'

test('管理员设置默认初始密码后，新增用户表单使用新值', async ({ mockedPage }) => {
  await loginAsAdmin(mockedPage)
  let configured = 'old-default'
  await mockedPage.route('**/api/v1/users', (route) => route.fulfill({ json: [] }))
  await mockedPage.route('**/api/v1/users/initial-password', (route) => {
    if (route.request().method() === 'PUT') {
      configured = route.request().postDataJSON().password
      return route.fulfill({ json: { success: true } })
    }
    return route.fulfill({ json: { password: configured } })
  })

  await mockedPage.goto('/system/users')
  await mockedPage.getByRole('button', { name: /设置默认初始密码|Set default initial password/ }).click()
  const dialog = mockedPage.getByRole('dialog')
  const input = dialog.locator('input[autocomplete="new-password"]')
  await expect(input).toHaveValue('old-default')
  await expect(input).toHaveAttribute('type', 'text')
  await input.fill('new-default-password')
  await dialog.getByRole('button', { name: /确\s*定|OK/ }).click()
  await expect.poll(() => configured).toBe('new-default-password')
  await expect(dialog).toBeHidden()

  await mockedPage.getByRole('button', { name: /设置默认初始密码|Set default initial password/ }).click()
  await expect(mockedPage.getByRole('dialog').locator('input[autocomplete="new-password"]')).toHaveValue('new-default-password')
  await mockedPage.getByRole('dialog').getByRole('button', { name: /取\s*消|Cancel/ }).click()

  await mockedPage.getByRole('button', { name: /新增用户|Add user/ }).click()
  await expect(mockedPage.getByRole('dialog').locator('input[type="password"]')).toHaveValue('new-default-password')
})
