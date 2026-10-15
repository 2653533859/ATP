import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import DynamicParamExtractorDrawer from './DynamicParamExtractorDrawer.vue'

const mockSampleEntries = [
  {
    method: 'POST',
    path: '/api/v1/orders',
    status_code: 201,
    duration_ms: 30,
    captured_at: '2026-10-16T10:00:00Z',
    is_noise_filtered: false,
    response_body: { order_id: 'ord_20261016_01', status: 'created' },
  },
  {
    method: 'GET',
    path: '/api/v1/orders/ord_20261016_01',
    status_code: 200,
    duration_ms: 20,
    captured_at: '2026-10-16T10:01:00Z',
    is_noise_filtered: false,
  },
]

const mockExtractResponse = {
  parameterized_entries: [
    {
      method: 'POST',
      path: '/api/v1/orders',
      status_code: 201,
      duration_ms: 30,
      captured_at: '2026-10-16T10:00:00Z',
      is_noise_filtered: false,
      response_body: { order_id: 'ord_20261016_01', status: 'created' },
      extractions: [
        {
          variable: 'order_id',
          type: 'jsonpath',
          expression: '$.order_id',
          description: '从步骤 1 响应中提取 order_id',
        },
      ],
    },
    {
      method: 'GET',
      path: '/api/v1/orders/{{order_id}}',
      status_code: 200,
      duration_ms: 20,
      captured_at: '2026-10-16T10:01:00Z',
      is_noise_filtered: false,
    },
  ],
  discovered_dependencies: [
    {
      producer_step: 0,
      consumer_step: 1,
      variable: 'order_id',
      jsonpath: '$.order_id',
      matched_value: 'ord_20261016_01',
      location: 'url_path',
    },
  ],
  total_dependencies_count: 1,
}

const mockExtractSessionParams = vi.fn().mockResolvedValue(mockExtractResponse)
const mockExtractParams = vi.fn().mockResolvedValue(mockExtractResponse)

vi.mock('@/api/trafficRecording', () => ({
  trafficRecordingApi: {
    extractSessionParams: (id: string) => mockExtractSessionParams(id),
    extractParams: (entries: unknown) => mockExtractParams(entries),
  },
}))

const globalStubs = {
  'a-drawer': { template: '<div class="ant-drawer"><slot name="title" /><slot /></div>' },
  'a-card': { template: '<div class="ant-card"><slot /></div>' },
  'a-button': { template: '<button class="ant-btn"><slot /></button>' },
  'a-tag': { template: '<span class="ant-tag"><slot /></span>' },
  'a-space': { template: '<div><slot /></div>' },
  'a-empty': { template: '<div class="ant-empty"><slot /></div>' },
  'a-tabs': { template: '<div class="ant-tabs"><slot /></div>' },
  'a-tab-pane': { template: '<div class="ant-tab-pane"><slot /></div>' },
  'a-table': {
    props: ['dataSource'],
    template: `
      <div class="ant-table">
        <slot />
        <div v-for="item in dataSource" :key="item.variable" class="table-row">
          <span class="row-step">步骤 #{{ item.producer_step + 1 }} -> 步骤 #{{ item.consumer_step + 1 }}</span>
          <span class="row-var">{{ item.variable }}</span>
          <span class="row-jsonpath">{{ item.jsonpath }}</span>
          <span class="row-val">{{ item.matched_value }}</span>
          <span class="row-loc">{{ item.location }}</span>
        </div>
      </div>
    `,
  },
}

describe('DynamicParamExtractorDrawer.vue', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders drawer and initial state', () => {
    const wrapper = mount(DynamicParamExtractorDrawer, {
      props: {
        open: true,
        sessionId: 'rec_sess_1001',
        entries: mockSampleEntries,
      },
      global: {
        stubs: globalStubs,
      },
    })

    expect(wrapper.text()).toContain('动态参数依赖提取与占位符规则配置')
    expect(wrapper.text()).toContain('执行依赖分析与参数化')
    expect(wrapper.text()).toContain('2 条')
    expect(wrapper.text()).toContain('等待分析')
  })

  it('triggers extraction upon clicking action button and renders results', async () => {
    const wrapper = mount(DynamicParamExtractorDrawer, {
      props: {
        open: true,
        sessionId: 'rec_sess_1001',
        entries: mockSampleEntries,
      },
      global: {
        stubs: globalStubs,
      },
    })

    const runBtn = wrapper.findAll('button').find((b) => b.text().includes('执行依赖分析与参数化'))
    expect(runBtn).toBeDefined()
    await runBtn!.trigger('click')
    await flushPromises()

    expect(mockExtractSessionParams).toHaveBeenCalledWith('rec_sess_1001')
    expect(wrapper.emitted('extracted')).toBeTruthy()
    expect(wrapper.text()).toContain('已完成参数化推导')
    expect(wrapper.text()).toContain('order_id')
    expect(wrapper.text()).toContain('$.order_id')
    expect(wrapper.text()).toContain('ord_20261016_01')
    expect(wrapper.text()).toContain('url_path')
  })
})
