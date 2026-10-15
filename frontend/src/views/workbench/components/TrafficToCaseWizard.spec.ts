import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import TrafficToCaseWizard from './TrafficToCaseWizard.vue'

const mockCaseResponse = {
  case_id: 201,
  name: '订单微服务全链路逆向冒烟用例',
  module_id: 1,
  project_id: 1,
  total_steps: 2,
  steps: [
    {
      step_no: 1,
      action: 'POST /api/v1/orders',
      expected_result: '验证 HTTP 响应状态码为 201',
      is_key_step: true,
    },
    {
      step_no: 2,
      action: 'GET /api/v1/orders/{{order_id}}',
      expected_result: '验证 HTTP 响应状态码为 200',
      is_key_step: true,
    },
  ],
  config: { steps: [] },
  dependencies_extracted: [],
  persisted: true,
}

const mockSuiteResponse = {
  suite_id: 301,
  suite_name: '订单全流程逆向测试套件',
  case_id: 201,
  case_name: '订单全流程逆向测试套件-用例',
  project_id: 1,
  module_id: 1,
  total_steps: 2,
  persisted: true,
}

const mockSynthesizeCase = vi.fn().mockResolvedValue(mockCaseResponse)
const mockSynthesizeSuite = vi.fn().mockResolvedValue(mockSuiteResponse)

vi.mock('@/api/trafficRecording', () => ({
  trafficRecordingApi: {
    synthesizeCase: (id: string, data: unknown) => mockSynthesizeCase(id, data),
    synthesizeSuite: (id: string, data: unknown) => mockSynthesizeSuite(id, data),
  },
}))

const globalStubs = {
  'a-modal': { template: '<div class="ant-modal"><slot name="title" /><slot /></div>' },
  'a-steps': { template: '<div class="ant-steps"><slot /></div>' },
  'a-step': { template: '<div class="ant-step" />' },
  'a-card': { template: '<div class="ant-card"><h4>{{ $attrs.title }}</h4><slot /></div>' },
  'a-button': { template: '<button class="ant-btn"><slot /></button>' },
  'a-tag': { template: '<span class="ant-tag"><slot /></span>' },
  'a-form': { template: '<form><slot /></form>' },
  'a-form-item': { template: '<div class="form-item"><slot /></div>' },
  'a-input': { template: '<input />' },
  'a-input-number': { template: '<input type="number" />' },
  'a-textarea': { template: '<textarea />' },
  'a-radio-group': { template: '<div class="ant-radio-group"><slot /></div>' },
  'a-radio-button': { template: '<button class="ant-radio-btn"><slot /></button>' },
  'a-select': { template: '<select><slot /></select>' },
  'a-select-option': { template: '<option><slot /></option>' },
  'a-switch': true,
  'a-spin': { template: '<div><slot /></div>' },
  'a-result': { template: '<div class="ant-result"><h2>{{ $attrs.title }}</h2><slot /><slot name="extra" /></div>' },
  'a-descriptions': { template: '<div><slot /></div>' },
  'a-descriptions-item': { template: '<div><slot /></div>' },
  'a-table': {
    props: ['dataSource'],
    template: `
      <div class="ant-table">
        <div v-for="item in dataSource" :key="item.step_no" class="table-row">
          <span>#{{ item.step_no }}</span>
          <span>{{ item.action }}</span>
          <span>{{ item.expected_result }}</span>
        </div>
      </div>
    `,
  },
}

describe('TrafficToCaseWizard.vue', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders wizard step 1 with initial metadata form', () => {
    const wrapper = mount(TrafficToCaseWizard, {
      props: {
        open: true,
        sessionId: 'rec_sess_1001',
        projectId: 1,
      },
      global: {
        stubs: globalStubs,
      },
    })

    expect(wrapper.text()).toContain('录制流量逆向合成用例与套件向导')
    expect(wrapper.text()).toContain('单场景用例 (TestCase)')
    expect(wrapper.text()).toContain('下一步: 断言策略')
  })

  it('advances through steps and synthesizes case successfully', async () => {
    const wrapper = mount(TrafficToCaseWizard, {
      props: {
        open: true,
        sessionId: 'rec_sess_1001',
        projectId: 1,
      },
      global: {
        stubs: globalStubs,
      },
    })

    // Step 1 -> Step 2
    const nextBtn = wrapper.findAll('button').find((b) => b.text().includes('下一步: 断言策略'))
    expect(nextBtn).toBeDefined()
    await nextBtn!.trigger('click')
    await flushPromises()

    expect(wrapper.text()).toContain('多维自动断言生成规则')
    expect(wrapper.text()).toContain('HTTP 状态码强校验')
    expect(wrapper.text()).toContain('确认合成并落库')

    // Step 2 -> Run Synthesis -> Step 3
    const submitBtn = wrapper.findAll('button').find((b) => b.text().includes('确认合成并落库'))
    expect(submitBtn).toBeDefined()
    await submitBtn!.trigger('click')
    await flushPromises()

    expect(mockSynthesizeCase).toHaveBeenCalledWith('rec_sess_1001', {
      case_name: '订单微服务全链路逆向冒烟用例',
      module_id: 1,
      description: '由微服务反向代理流量录制自动逆向合成',
      priority: 'P1',
      case_level: 'regression',
      persist: true,
    })

    expect(wrapper.emitted('synthesized')).toBeTruthy()
    expect(wrapper.text()).toContain('测试用例逆向合成成功！')
    expect(wrapper.text()).toContain('#201')
    expect(wrapper.text()).toContain('2 步')
    expect(wrapper.text()).toContain('完成并关闭')
  })
})
