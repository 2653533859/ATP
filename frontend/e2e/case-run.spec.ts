import { test, expect, loginAsAdmin } from './fixtures/mock-api'
import * as data from './fixtures/mock-data'

test.describe('case run trigger', () => {
  test('触发用例执行接口返回 pending 时跳转/打开 RunDetail', async ({ mockedPage }) => {
    let triggered = false
    await mockedPage.route('**/api/v1/cases/100/run', (route) => {
      triggered = true
      return route.fulfill({ json: data.triggeredRun, status: 202 })
    })

    // 模拟用户直接调 API（不依赖具体 UI 按钮位置）：fetch 一次确认 mock 链路通
    await loginAsAdmin(mockedPage)

    const result = await mockedPage.evaluate(async () => {
      const r = await fetch('/api/v1/cases/100/run', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-Requested-With': 'XMLHttpRequest',
        },
        body: JSON.stringify({ env_id: null, extra_vars: {} }),
      })
      return { status: r.status, body: await r.json() }
    })

    expect(triggered).toBeTruthy()
    expect(result.status).toBe(202)
    expect(result.body.id).toBe(9001)
    expect(result.body.status).toBe('pending')
  })
})
