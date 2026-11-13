import { expect, loginAsAdmin, test } from './fixtures/mock-api'

test.describe('Android Agent 工作台闭环', () => {
  test('支持视觉模型选择、任务创建、人工接管/终态确认、草稿编辑、回放验证与发布用例', async ({ mockedPage: page }) => {

    let sessionState: Record<string, unknown> | null = null
    let nextSeq = 1
    const eventList: Array<Record<string, unknown>> = []
    let currentDraft: Record<string, unknown> | null = null
    const draftHistory: Array<Record<string, unknown>> = []
    let replayRecord: Record<string, unknown> | null = null

    await page.route('**/api/v1/devices', (route) =>
      route.fulfill({
        json: [
          {
            id: 5,
            serial: 'emulator-5554',
            name: 'Pixel 8',
            model: 'Pixel 8',
            brand: 'Google',
            os_type: 'android',
            status: 'online',
          },
        ],
      }),
    )
    await page.route('**/api/v1/devices/workers', (route) => route.fulfill({ json: [] }))
    await page.route('**/api/v1/devices/*/packages**', (route) =>
      route.fulfill({
        json: {
          device_id: 5,
          serial: 'emulator-5554',
          current_package: 'com.example.shop',
          current_activity: '.MainActivity',
          packages: ['com.example.shop', 'com.android.settings'],
          read_at: '2026-11-13T09:00:00Z',
          stale: false,
          source: 'cache',
        },
      }),
    )
    await page.route('**/api/v1/devices/*/package-history**', (route) => route.fulfill({ json: [] }))
    await page.route('**/api/v1/apks**', (route) =>
      route.fulfill({
        json: [
          {
            id: 1,
            filename: 'shop-debug.apk',
            package_name: 'com.example.shop',
            version_name: '2.4.0',
            created_at: '2026-11-12T10:00:00Z',
          },
        ],
      }),
    )
    await page.route('**/api/v1/mobile-special/**', (route) => {
      const url = route.request().url()
      if (url.includes('/statistics/overview')) {
        return route.fulfill({
          json: {
            total_runs: 0,
            completed_runs: 0,
            failed_runs: 0,
            running_runs: 0,
            pass_rate: 0,
            avg_duration_ms: null,
            total_incidents: 0,
            recent_runs_7d: 0,
          },
        })
      }
      return route.fulfill({ json: [] })
    })

    await page.route('**/api/v1/projects/1/android-agent/models', (route) =>
      route.fulfill({
        json: [
          {
            id: 7,
            name: 'GPT-4o Vision',
            provider: 'openai',
            model_name: 'gpt-4o',
            enabled: true,
            supports_vision: true,
            description: 'Vision model',
          },
        ],
      }),
    )

    await page.route('**/api/v1/projects/1/android-agent/sessions', async (route) => {
      const method = route.request().method()
      if (method === 'GET') {
        return route.fulfill({ json: sessionState ? [sessionState] : [] })
      }
      if (method === 'POST') {
        const body = route.request().postDataJSON() as Record<string, unknown>
        sessionState = {
          id: 11,
          project_id: 1,
          device_id: body.device_id ?? 5,
          created_by: 1,
          title: body.title || '搜索并校验库存',
          goal: body.goal,
          expected_outcome: body.expected_outcome,
          package_name: body.package_name,
          llm_config_id: body.llm_config_id ?? 7,
          status: 'created',
          controller: 'agent',
          version: 1,
          control_epoch: 0,
          lease_token: null,
          budget_max_steps: 30,
          budget_max_calls: 40,
          steps_count: 0,
          model_calls_count: 0,
          total_tokens: 0,
          error_code: null,
          context_values: (body.context_values as Record<string, string>) || {},
          terminal_assertions: [],
          started_at: null,
          finished_at: null,
          created_at: '2026-11-13T09:00:00Z',
          updated_at: '2026-11-13T09:00:00Z',
        }
        eventList.push({
          id: nextSeq,
          session_id: 11,
          seq: nextSeq++,
          event_type: 'session_created',
          payload: { summary: '会话已创建' },
          artifact_refs: [],
          created_at: '2026-11-13T09:00:00Z',
        })
        return route.fulfill({ status: 201, json: sessionState })
      }
      return route.continue()
    })

    await page.route('**/api/v1/projects/1/android-agent/sessions?*', (route) =>
      route.fulfill({ json: sessionState ? [sessionState] : [] }),
    )

    await page.route('**/api/v1/projects/1/android-agent/sessions/11', (route) =>
      route.fulfill({ json: sessionState }),
    )

    await page.route('**/api/v1/projects/1/android-agent/sessions/11/start', (route) => {
      sessionState = { ...sessionState, status: 'running', controller: 'agent', version: 2 }
      eventList.push({
        id: nextSeq,
        session_id: 11,
        seq: nextSeq++,
        event_type: 'session_started',
        payload: { action: 'start' },
        artifact_refs: [],
        created_at: '2026-11-13T09:00:05Z',
      })
      return route.fulfill({ json: sessionState })
    })

    await page.route('**/api/v1/projects/1/android-agent/sessions/11/run**', (route) => {
      sessionState = {
        ...sessionState,
        status: 'paused',
        controller: 'agent',
        version: 3,
        steps_count: 2,
        model_calls_count: 2,
        total_tokens: 180,
      }
      eventList.push({
        id: nextSeq,
        session_id: 11,
        seq: nextSeq++,
        event_type: 'model_step',
        payload: { action: 'input', reason: '填写搜索词' },
        artifact_refs: [],
        created_at: '2026-11-13T09:00:10Z',
      })
      return route.fulfill({
        json: { status: 'paused', reason: 'needs_review', steps: 2, model_calls: 2, tokens: 180 },
      })
    })

    await page.route('**/api/v1/projects/1/android-agent/sessions/11/control', async (route) => {
      const body = route.request().postDataJSON() as { action: string }
      const nextVersion = Number(sessionState?.version ?? 1) + 1
      if (body.action === 'takeover') {
        sessionState = { ...sessionState, status: 'paused', controller: 'manual', control_epoch: 1, version: nextVersion }
      } else if (body.action === 'pause') {
        sessionState = { ...sessionState, status: 'paused', version: nextVersion }
      } else if (body.action === 'resume') {
        sessionState = { ...sessionState, status: 'running', controller: 'agent', version: nextVersion }
      } else if (body.action === 'cancel') {
        sessionState = { ...sessionState, status: 'cancelled', controller: 'none', version: nextVersion }
      }
      eventList.push({
        id: nextSeq,
        session_id: 11,
        seq: nextSeq++,
        event_type: `session_${body.action}`,
        payload: { action: body.action },
        artifact_refs: [],
        created_at: '2026-11-13T09:00:15Z',
      })
      return route.fulfill({
        json: {
          session_id: 11,
          status: sessionState?.status,
          controller: sessionState?.controller,
          control_epoch: sessionState?.control_epoch,
          version: sessionState?.version,
          message: 'ok',
        },
      })
    })

    await page.route('**/api/v1/projects/1/android-agent/sessions/11/manual-action', async (route) => {
      const body = route.request().postDataJSON() as { action: string }
      const seq = nextSeq
      eventList.push({
        id: seq,
        session_id: 11,
        seq: nextSeq++,
        event_type: 'manual_action',
        payload: { action: body.action },
        artifact_refs: [],
        created_at: '2026-11-13T09:00:18Z',
      })
      return route.fulfill({
        json: {
          command_id: 81,
          session_id: 11,
          seq,
          control_epoch: 1,
          action: body.action,
          status: 'succeeded',
          idempotency_key: 'manual-e2e',
        },
      })
    })

    await page.route('**/api/v1/projects/1/android-agent/sessions/11/complete', async (route) => {
      const body = route.request().postDataJSON() as {
        terminal_assertions: Array<{ type: string; resource_id: string }>
      }
      sessionState = {
        ...sessionState,
        status: 'completed',
        controller: 'none',
        version: Number(sessionState?.version ?? 1) + 1,
        terminal_assertions: body.terminal_assertions,
      }
      eventList.push({
        id: nextSeq,
        session_id: 11,
        seq: nextSeq++,
        event_type: 'session_completed',
        payload: { summary: '人工确认完成' },
        artifact_refs: [],
        created_at: '2026-11-13T09:00:22Z',
      })
      return route.fulfill({ json: sessionState })
    })

    await page.route('**/api/v1/projects/1/android-agent/sessions/11/events**', (route) =>
      route.fulfill({
        json: {
          items: eventList,
          next_seq: nextSeq - 1,
          has_more: false,
        },
      }),
    )

    await page.route('**/api/v1/projects/1/android-agent/sessions/11/drafts', (route) => {
      if (route.request().method() === 'GET') {
        return route.fulfill({ json: draftHistory })
      }
      currentDraft = {
        id: 30,
        project_id: 1,
        session_id: 11,
        version: 1,
        schema_version: 1,
        status: 'replayable',
        content_hash: 'a'.repeat(64),
        steps: [
          { action: 'start_app', params: { package_name: 'com.example.shop' } },
          { action: 'input', params: { resource_id: 'com.example.shop:id/search' } },
        ],
        assertions: (sessionState?.terminal_assertions as Array<Record<string, unknown>>) || [],
        preconditions: [],
        variables: ['keyword'],
        blocking_issues: [],
        source_map: {},
        environment_snapshot: {},
        published_case_id: null,
        created_at: '2026-11-13T09:00:25Z',
      }
      draftHistory.unshift(currentDraft)
      return route.fulfill({ status: 201, json: currentDraft })
    })

    await page.route('**/api/v1/projects/1/android-agent/drafts/**', async (route) => {
      const url = route.request().url()
      if (route.request().method() === 'PATCH') {
        const body = route.request().postDataJSON() as { assertions?: Array<Record<string, unknown>> }
        currentDraft = {
          ...currentDraft,
          id: 31,
          version: 2,
          status: 'replayable',
          content_hash: 'b'.repeat(64),
          assertions: body.assertions ?? [],
        }
        draftHistory.unshift(currentDraft)
        return route.fulfill({ json: currentDraft })
      }
      if (url.endsWith('/replay-preview')) {
        return route.fulfill({
          json: {
            draft_id: currentDraft?.id,
            draft_version: currentDraft?.version,
            content_hash: currentDraft?.content_hash,
            ready: true,
            frozen_snapshot: {},
            items: [{ code: 'DRAFT_READY', status: 'pass', message: '结构完整，可直接发起回放' }],
          },
        })
      }
      if (url.endsWith('/replays')) {
        replayRecord = {
          id: 90,
          draft_id: currentDraft?.id,
          draft_version: currentDraft?.version,
          status: 'queued',
          case_id: 100,
          run_id: 200,
        }
        return route.fulfill({
          status: 201,
          json: {
            replay: replayRecord,
            case_id: 100,
            run_id: 200,
            frozen_snapshot: {},
          },
        })
      }
      if (url.endsWith('/publish')) {
        currentDraft = { ...currentDraft, status: 'verified', published_case_id: 100 }
        return route.fulfill({
          json: {
            draft_id: currentDraft.id,
            draft_version: currentDraft.version,
            case_id: 100,
            verified_replay_id: 90,
            published: true,
            idempotent_replay: false,
          },
        })
      }
      return route.fulfill({ json: currentDraft })
    })

    await page.route('**/api/v1/projects/1/android-agent/replays/90', (route) => {
      replayRecord = { ...replayRecord, status: 'passed' }
      if (currentDraft) {
        currentDraft = { ...currentDraft, status: 'verified' }
        draftHistory[0] = currentDraft
      }
      return route.fulfill({ json: replayRecord })
    })

    await loginAsAdmin(page)
    await page.goto('/mobile-special/workbench')

    const panel = page.getByTestId('android-agent-panel')
    await expect(panel).toBeVisible({ timeout: 10_000 })
    await expect(panel.locator('.agent-sensitive-hint')).toBeVisible()

    // 1. 任务设定：选择设备、点击 APK 快捷包名、填写标题与目标/变量，并自动带出视觉模型
    await panel.locator('#agent-title-input').fill('电商搜索商品回放')
    await panel.locator('.field-device .ant-select').click()
    await page.locator('.ant-select-dropdown:visible .ant-select-item-option').filter({ hasText: 'Pixel 8' }).click()
    await panel.locator('.apk-quick-chip', { hasText: 'com.example.shop' }).click()
    await panel.locator('#agent-goal-input').fill('搜索商品并打开详情页')
    await panel.locator('#agent-outcome-input').fill('详情页显示商品库存信息')
    await panel.getByRole('button', { name: /添加变量|Add variable/i }).click()
    await panel.getByPlaceholder(/变量名|Variable key/i).fill('keyword')
    await panel.getByPlaceholder(/变量值|Variable value/i).fill('sunny')

    await panel.getByRole('button', { name: /创建会话|Create session/i }).click()
    await expect(panel.locator('.agent-session')).toBeVisible()

    // 2. 启动 + 驱动一轮模型 + 人工接管并登记单步动作
    await panel.getByRole('button', { name: /开始执行|Start/i }).click()
    await panel.getByRole('button', { name: /执行一轮|Run round/i }).click()
    await expect(panel.locator('.agent-event-row')).toHaveCount(3)

    await panel.getByRole('button', { name: /接\s*管|Take over/i }).click()
    const manualConsole = panel.getByTestId('agent-manual-console')
    await expect(manualConsole).toBeVisible()
    await manualConsole.getByPlaceholder(/resource_id/i).fill('com.example.shop:id/search_btn')
    await manualConsole.getByRole('button', { name: /执行人工指令|Execute manual action/i }).click()
    await expect(panel.locator('.agent-event-row')).toHaveCount(5)

    // 3. 确认终态断言并完成会话
    await panel.getByRole('button', { name: /确认终态并完成|Confirm & Complete/i }).click()
    const completeForm = panel.getByTestId('agent-complete-form')
    await expect(completeForm).toBeVisible()
    await completeForm.getByPlaceholder(/com\.example\.shop:id\/product_stock/i).fill('com.example.shop:id/stock')
    await completeForm.getByRole('checkbox').check()
    await completeForm.getByRole('button', { name: /确认完成会话|Confirm completion/i }).click()
    await expect(completeForm).toBeHidden()

    // 4. 生成草稿、编辑断言升版并验证独立回放状态、发布为正式用例
    await panel.getByRole('button', { name: /生成草稿|Compile draft/i }).click()
    await expect(panel.locator('.agent-draft-status')).toBeVisible()

    await panel.getByRole('button', { name: /编辑草稿断言|Edit draft assertions/i }).click()
    const draftEditor = panel.getByTestId('agent-draft-editor')
    await expect(draftEditor).toBeVisible()
    await draftEditor.getByPlaceholder(/com\.example\.shop:id\/product_stock/i).fill('com.example.shop:id/stock_v2')
    await draftEditor.getByRole('button', { name: /保存为新草稿版本|Save as new draft version/i }).click()
    await expect(panel.locator('.agent-draft')).toContainText('v2')

    await panel.locator('.agent-replay').getByRole('checkbox').check()
    await panel.getByRole('button', { name: /回放前核对|Replay precheck/i }).click()
    await expect(panel.locator('.agent-preview-items')).toContainText('DRAFT_READY')

    await panel.getByRole('button', { name: /发起独立回放|Start standalone replay/i }).click()
    await expect(panel.locator('.agent-replay-status')).toContainText('queued')
    await panel.getByRole('button', { name: /刷新回放状态|Refresh replay/i }).click()
    await expect(panel.locator('.agent-replay-status')).toContainText('passed')
    await expect(panel.getByRole('button', { name: /查看回放运行 #200|View replay run #200/i })).toBeVisible()

    await panel.getByRole('button', { name: /保存为正式用例|Save as formal case/i }).click()
    await expect(panel.locator('.agent-published')).toContainText('100')
    await expect(panel.getByRole('button', { name: /打开正式用例 #100|Open formal case #100/i })).toBeVisible()
  })
})
