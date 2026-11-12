import { enableAutoUnmount, flushPromises, mount } from '@vue/test-utils'
import { defineComponent, h, ref } from 'vue'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import AndroidAgentPanel from './AndroidAgentPanel.vue'

const {
  compileDraft,
  control,
  createSession,
  events,
  getSession,
  publishDraft,
  replayPreview,
  startReplay,
  startSession,
  messageSuccess,
  messageInfo,
  runSession,
  devicePackages,
} = vi.hoisted(() => ({
  compileDraft: vi.fn(),
  control: vi.fn(),
  createSession: vi.fn(),
  events: vi.fn(),
  getSession: vi.fn(),
  publishDraft: vi.fn(),
  replayPreview: vi.fn(),
  startReplay: vi.fn(),
  startSession: vi.fn(),
  messageSuccess: vi.fn(),
  messageInfo: vi.fn(),
  runSession: vi.fn(),
  devicePackages: vi.fn(),
}))

vi.mock('vue-i18n', () => ({
  useI18n: () => ({ locale: ref('zh-CN'), t: (key: string, params?: Record<string, unknown>) =>
    params ? key + ':' + JSON.stringify(params) : key }),
}))
vi.mock('ant-design-vue', () => ({
  message: { success: messageSuccess, error: vi.fn(), warning: vi.fn(), info: messageInfo },
}))
vi.mock('@/api', () => ({
  androidAgentApi: {
    compileDraft,
    control,
    createSession,
    events,
    getSession,
    publishDraft,
    replayPreview,
    runSession,
    startReplay,
    startSession,
  },
  deviceApi: { packages: devicePackages },
}))

const passthrough = (name: string) =>
  defineComponent({ name, setup: (_props, { slots }) => () => h('div', slots.default?.()) })

const globalStubs = {
  AAlert: passthrough('AAlert'),
  AButton: defineComponent({
    name: 'AButton',
    props: ['disabled', 'loading', 'danger', 'type'],
    emits: ['click'],
    setup: (props, { slots, emit }) => () =>
      h('button', { disabled: props.disabled, onClick: () => emit('click') }, slots.default?.()),
  }),
  ACheckbox: defineComponent({
    name: 'ACheckbox',
    props: ['checked'],
    emits: ['update:checked'],
    setup: (props, { slots, emit }) => () =>
      h(
        'label',
        {},
        [h('input', { type: 'checkbox', checked: props.checked, onChange: (e: Event) => emit('update:checked', (e.target as HTMLInputElement).checked) }), slots.default?.()],
      ),
  }),
  AInput: passthrough('AInput'),
  AAutoComplete: passthrough('AAutoComplete'),
  AInputNumber: passthrough('AInputNumber'),
  ASelect: defineComponent({
    name: 'ASelect',
    props: ['options', 'value', 'placeholder', 'size', 'loading'],
    emits: ['update:value'],
    setup: (props, { emit }) => () =>
      h(
        'select',
        {
          class: 'a-select-stub',
          onChange: (e: Event) => emit('update:value', Number((e.target as HTMLSelectElement).value)),
        },
        (props.options ?? []).map((option: { value: number; label: string }) =>
          h('option', { value: option.value }, option.label),
        ),
      ),
  }),
  ATag: passthrough('ATag'),
}

const sessionFixture = {
  id: 11,
  project_id: 1,
  device_id: 5,
  created_by: 1,
  title: '搜索商品',
  goal: '搜索商品并打开详情',
  expected_outcome: '详情页商品名称等于 测试商品',
  package_name: 'com.example.shop',
  llm_config_id: null,
  status: 'running',
  controller: 'agent',
  version: 3,
  control_epoch: 0,
  lease_token: 'token',
  budget_max_steps: 30,
  budget_max_calls: 40,
  steps_count: 4,
  model_calls_count: 5,
  total_tokens: 1200,
  error_code: null,
  context_values: {},
  started_at: '2026-11-11T02:00:00Z',
  finished_at: null,
  created_at: '2026-11-11T01:59:00Z',
  updated_at: '2026-11-11T02:01:00Z',
}

enableAutoUnmount(afterEach)

beforeEach(() => {
  vi.clearAllMocks()
  createSession.mockResolvedValue(sessionFixture)
  startSession.mockResolvedValue({ ...sessionFixture, status: 'running' })
  getSession.mockResolvedValue(sessionFixture)
  events.mockResolvedValue({ items: [{ id: 1, session_id: 11, seq: 1, event_type: 'session_created', payload: {}, artifact_refs: [], created_at: '2026-11-11T01:59:00Z' }], next_seq: 1, has_more: false })
  control.mockResolvedValue({ session_id: 11, status: 'paused', controller: 'agent', control_epoch: 1, version: 4, message: 'ok' })
  compileDraft.mockResolvedValue({
    id: 3,
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
    assertions: [{ type: 'element_visible', resource_id: 'com.example.shop:id/stock' }],
    preconditions: [],
    variables: ['keyword'],
    blocking_issues: [],
    source_map: {},
    environment_snapshot: {},
    published_case_id: null,
    created_at: '2026-11-11T02:02:00Z',
  })
  replayPreview.mockResolvedValue({
    draft_id: 3,
    draft_version: 1,
    content_hash: 'a'.repeat(64),
    ready: true,
    frozen_snapshot: {},
    items: [{ code: 'DRAFT_READY', status: 'pass', message: 'ok' }],
  })
  startReplay.mockResolvedValue({ replay: { id: 9, draft_id: 3, draft_version: 1, status: 'queued', case_id: 100, run_id: 200 }, case_id: 100, run_id: 200, frozen_snapshot: {} })
  runSession.mockResolvedValue({ status: 'needs_review', reason: 'cannot_progress', steps: 2, model_calls: 3, tokens: 90 })
  publishDraft.mockResolvedValue({ draft_id: 3, draft_version: 1, case_id: 100, verified_replay_id: 9, published: true, idempotent_replay: false })
  devicePackages.mockResolvedValue({
    device_id: 5,
    serial: 'emulator-5554',
    current_package: null,
    current_activity: null,
    packages: [],
  })
})

function mountPanel(overrides: Record<string, unknown> = {}) {
  return mount(AndroidAgentPanel, {
    props: {
      projectId: 1,
      devices: [{ id: 5, serial: 'emulator-5554', name: 'Pixel 6', status: 'online' }],
      modules: [{ id: 1, name: '默认模块' }],
      canModify: true,
      ...overrides,
    },
    global: { stubs: globalStubs },
  })
}

describe('AndroidAgentPanel', () => {
  it('创建会话后展示状态、用量与轨迹事件', async () => {
    const wrapper = mountPanel()
    wrapper.vm.formDeviceId = 5
    wrapper.vm.formPackage = 'com.example.shop'
    wrapper.vm.formGoal = '搜索商品'
    wrapper.vm.formOutcome = '详情页可见'
    await flushPromises()

    await wrapper.vm.createSession()
    await flushPromises()

    expect(createSession).toHaveBeenCalledWith(
      1,
      expect.objectContaining({ device_id: 5, package_name: 'com.example.shop', goal: '搜索商品' }),
      expect.stringContaining('agent-session-'),
    )
    expect(events).toHaveBeenCalledWith(1, 11, 0, 200)
    expect(wrapper.text()).toContain('android_agent.steps_used')
    expect(wrapper.findAll('.agent-event-row')).toHaveLength(1)
  })

  it('选择设备后读取该设备已安装包名并回填当前前台应用', async () => {
    devicePackages.mockResolvedValue({
      device_id: 5,
      serial: 'emulator-5554',
      current_package: 'com.hopesen.aiphytraining',
      current_activity: '.view.list.ExaminationListActivity',
      packages: ['com.hopesen.aiphytraining', 'com.mgtv.tv'],
    })
    const wrapper = mountPanel()
    wrapper.vm.formDeviceId = 5
    await flushPromises()

    expect(devicePackages).toHaveBeenCalledWith(5)
    expect(wrapper.vm.formPackage).toBe('com.hopesen.aiphytraining')
    expect(wrapper.vm.devicePackages).toEqual(['com.hopesen.aiphytraining', 'com.mgtv.tv'])
    expect(wrapper.text()).toContain('android_agent.foreground_hint')
  })

  it('已手动填写包名时读取设备包名不覆盖用户输入', async () => {
    devicePackages.mockResolvedValue({
      device_id: 5,
      serial: 'emulator-5554',
      current_package: 'com.hopesen.aiphytraining',
      current_activity: '.MainActivity',
      packages: ['com.hopesen.aiphytraining'],
    })
    const wrapper = mountPanel()
    wrapper.vm.formDeviceId = 5
    wrapper.vm.formPackage = 'com.example.custom'
    await flushPromises()

    await wrapper.vm.loadDevicePackages()
    await flushPromises()

    expect(wrapper.vm.formPackage).toBe('com.example.custom')
  })

  it('暂停请求携带当前版本号，用于服务端乐观并发校验', async () => {
    const wrapper = mountPanel()
    wrapper.vm.session = sessionFixture
    await flushPromises()

    await wrapper.vm.control('pause')
    await flushPromises()

    expect(control).toHaveBeenCalledWith(1, 11, 'pause', 3)
    expect(wrapper.vm.session?.status).toBe('paused')
  })

  it('草稿阻断项可见，且阻断时不可发起回放', async () => {
    compileDraft.mockResolvedValue({
      ...(await compileDraft()),
      status: 'blocked',
      blocking_issues: [{ code: 'session_not_completed', message: '会话未成功结束' }],
    })
    const wrapper = mountPanel()
    wrapper.vm.session = { ...sessionFixture, status: 'failed' }
    await flushPromises()

    await wrapper.vm.compileDraft()
    await flushPromises()

    expect(wrapper.text()).toContain('session_not_completed')
    expect(wrapper.vm.canStartReplay).toBe(false)
    expect(wrapper.vm.canPublish).toBe(false)
  })

  it('确认初始状态并选择模块后才发起独立回放', async () => {
    const wrapper = mountPanel()
    wrapper.vm.session = { ...sessionFixture, status: 'completed' }
    await flushPromises()
    await wrapper.vm.compileDraft()
    await flushPromises()

    expect(wrapper.vm.canStartReplay).toBe(false)
    wrapper.vm.replayStateConfirmed = true
    wrapper.vm.replayModuleId = 1
    await flushPromises()
    expect(wrapper.vm.canStartReplay).toBe(true)

    await wrapper.vm.startReplay()
    await flushPromises()
    expect(startReplay).toHaveBeenCalledWith(
      1,
      3,
      expect.objectContaining({ initial_state_confirmed: true, module_id: 1, idempotency_key: 'agent-replay-3-1' }),
    )
    expect(messageSuccess).toHaveBeenCalled()
  })

  it('保存正式用例后回显用例编号', async () => {
    const wrapper = mountPanel()
    wrapper.vm.session = { ...sessionFixture, status: 'completed' }
    await flushPromises()
    await wrapper.vm.compileDraft()
    await flushPromises()

    await wrapper.vm.publishDraft()
    await flushPromises()

    expect(publishDraft).toHaveBeenCalledWith(1, 3, 'agent-publish-3-1')
    expect(wrapper.vm.publishedCaseId).toBe(100)
  })

  it('设备被占用时展示可读提示而不是原始异常', async () => {
    createSession.mockRejectedValue({ response: { data: { detail: 'Device lease unavailable: device_busy' } } })
    const wrapper = mountPanel()
    wrapper.vm.formDeviceId = 5
    wrapper.vm.formPackage = 'com.example.shop'
    wrapper.vm.formGoal = 'g'
    wrapper.vm.formOutcome = 'o'
    await flushPromises()

    await wrapper.vm.createSession()
    await flushPromises()

    expect(wrapper.vm.errorMessage).toBe('android_agent.error_device_busy')
  })
})

describe('AndroidAgentPanel loop', () => {
  it('只有 running 会话可以驱动模型循环', async () => {
    const wrapper = mountPanel()
    wrapper.vm.session = { ...sessionFixture, status: 'paused' }
    await flushPromises()
    expect(wrapper.vm.canRunLoop).toBe(false)

    wrapper.vm.session = { ...sessionFixture, status: 'running' }
    await flushPromises()
    expect(wrapper.vm.canRunLoop).toBe(true)
  })

  it('执行一轮后回显收敛结果并刷新会话', async () => {
    const wrapper = mountPanel()
    wrapper.vm.session = sessionFixture
    await flushPromises()

    await wrapper.vm.runLoop()
    await flushPromises()

    expect(runSession).toHaveBeenCalledWith(1, 11)
    expect(messageInfo).toHaveBeenCalled()
    expect(getSession).toHaveBeenCalledWith(1, 11)
  })
})
