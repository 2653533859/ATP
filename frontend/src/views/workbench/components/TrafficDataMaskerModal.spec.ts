import { mount, flushPromises } from '@vue/test-utils'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import TrafficDataMaskerModal from './TrafficDataMaskerModal.vue'
import { trafficMaskerApi } from '@/api/trafficGateway'

const mockRules = [
  {
    rule_id: 'rule_phone',
    name: '大陆手机号脱敏',
    category: 'PHONE',
    strategy: 'MASK',
    field_key_patterns: ['phone', 'mobile'],
    enabled: true,
  },
  {
    rule_id: 'rule_id_card',
    name: '居民身份证号脱敏',
    category: 'ID_CARD',
    strategy: 'MASK',
    field_key_patterns: ['id_card', 'idcard'],
    enabled: true,
  },
  {
    rule_id: 'rule_password',
    name: '登录密码与密钥擦除',
    category: 'PASSWORD',
    strategy: 'REDACT',
    field_key_patterns: ['password', 'pwd'],
    enabled: true,
  },
]

vi.mock('@/api/trafficGateway', () => ({
  trafficMaskerApi: {
    getRules: vi.fn(),
    updateRules: vi.fn(),
    resetRules: vi.fn(),
    maskText: vi.fn(),
    maskPayload: vi.fn(),
    maskTrafficItem: vi.fn(),
    batchMaskTraffic: vi.fn(),
  },
}))

vi.mock('ant-design-vue', () => ({
  message: {
    success: vi.fn(),
    warning: vi.fn(),
    error: vi.fn(),
    info: vi.fn(),
  },
}))

vi.mock('@ant-design/icons-vue', () => ({
  SafetyCertificateOutlined: { template: '<span>Safety</span>' },
  SettingOutlined: { template: '<span>Setting</span>' },
  ReloadOutlined: { template: '<span>Reload</span>' },
  SaveOutlined: { template: '<span>Save</span>' },
  ExperimentOutlined: { template: '<span>Experiment</span>' },
  ThunderboltOutlined: { template: '<span>Thunderbolt</span>' },
}))

describe('TrafficDataMaskerModal.vue', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(trafficMaskerApi.getRules).mockResolvedValue({
      total: 3,
      rules: mockRules as any,
    })
    vi.mocked(trafficMaskerApi.updateRules).mockResolvedValue({
      message: '脱敏规则已成功更新并生效',
      rules: mockRules as any,
    })
    vi.mocked(trafficMaskerApi.resetRules).mockResolvedValue({
      message: '已重置为出厂规则',
      rules: mockRules as any,
    })
    vi.mocked(trafficMaskerApi.maskPayload).mockResolvedValue({
      masked_payload: {
        username: 'alice',
        password: '[REDACTED]',
        mobile: '138****5678',
      },
    })
    vi.mocked(trafficMaskerApi.maskText).mockResolvedValue({
      original: 'phone 13812345678',
      masked: 'phone 138****5678',
    })
  })

  it('renders modal banner, rules matrix table, and runs initial mask on open', async () => {
    const wrapper = mount(TrafficDataMaskerModal, {
      props: {
        open: true,
      },
      global: {
        stubs: {
          'a-modal': { template: '<div class="ant-modal"><slot /></div>' },
          'a-tag': { template: '<span class="ant-tag"><slot /></span>' },
          'a-button': { template: '<button><slot /></button>' },
          'a-space': { template: '<div><slot /></div>' },
          'a-input': { template: '<input />' },
          'a-textarea': { template: '<textarea />' },
          'a-select': { template: '<select><slot /></select>' },
          'a-select-option': { template: '<option><slot /></option>' },
          'a-switch': { template: '<input type="checkbox" />' },
          'a-radio-group': { template: '<div><slot /></div>' },
          'a-radio-button': { template: '<button><slot /></button>' },
          'a-table': {
            props: ['dataSource'],
            template: `
              <div class="ant-table-stub">
                <div v-for="item in dataSource" :key="item.rule_id" class="row">
                  <span class="rule-name">{{ item.name }}</span>
                  <span class="category">{{ item.category }}</span>
                </div>
              </div>
            `,
          },
        },
      },
    })

    await flushPromises()

    // 检查标题与说明
    expect(wrapper.text()).toContain('生产数据合规脱敏防护引擎')
    expect(trafficMaskerApi.getRules).toHaveBeenCalled()
    expect(trafficMaskerApi.maskPayload).toHaveBeenCalled()

    // 检查规则列表
    expect(wrapper.text()).toContain('大陆手机号脱敏')
    expect(wrapper.text()).toContain('居民身份证号脱敏')
    expect(wrapper.text()).toContain('登录密码与密钥擦除')

    // 检查沙箱预览区
    expect(wrapper.text()).toContain('在线脱敏演练沙箱')
    expect(wrapper.text()).toContain('[REDACTED]')
    expect(wrapper.text()).toContain('138****5678')
  })

  it('allows saving rules and switching to sample presets', async () => {
    const wrapper = mount(TrafficDataMaskerModal, {
      props: {
        open: true,
      },
      global: {
        stubs: {
          'a-modal': { template: '<div class="ant-modal"><slot /></div>' },
          'a-tag': { template: '<span class="ant-tag"><slot /></span>' },
          'a-button': { template: '<button><slot /></button>' },
          'a-space': { template: '<div><slot /></div>' },
          'a-input': { template: '<input />' },
          'a-textarea': { template: '<textarea />' },
          'a-select': { template: '<select><slot /></select>' },
          'a-select-option': { template: '<option><slot /></option>' },
          'a-switch': { template: '<input type="checkbox" />' },
          'a-radio-group': { template: '<div><slot /></div>' },
          'a-radio-button': { template: '<button><slot /></button>' },
          'a-table': { template: '<div class="ant-table-stub" />' },
        },
      },
    })

    await flushPromises()

    const vm = wrapper.vm as any

    // 测试保存规则
    await vm.handleSaveRules()
    expect(trafficMaskerApi.updateRules).toHaveBeenCalledWith(mockRules)

    // 测试恢复默认出厂规则
    await vm.handleResetRules()
    expect(trafficMaskerApi.resetRules).toHaveBeenCalled()

    // 测试载入支付卡样例
    vm.loadSample('payment_card')
    expect(vm.inputContent).toContain('6222021234567890123')
  })
})
