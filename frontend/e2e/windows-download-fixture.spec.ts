import { test, expect } from './fixtures/mock-api'

test.describe('Windows Web 下载验收夹具', () => {
  test('静态页面可以触发可保存的下载文件', async ({ mockedPage }) => {
    await mockedPage.goto('/atp-windows-download.html')
    await expect(mockedPage.getByRole('heading', { name: 'ATP Windows Web 下载验收' })).toBeVisible()

    const downloadPromise = mockedPage.waitForEvent('download')
    await mockedPage.getByRole('link', { name: '下载 Windows 冒烟文件' }).click()
    const download = await downloadPromise

    expect(download.suggestedFilename()).toBe('atp-windows-smoke.txt')
    expect(await download.path()).toBeTruthy()
    await expect(mockedPage.getByText('已触发下载')).toBeVisible()
  })
})
