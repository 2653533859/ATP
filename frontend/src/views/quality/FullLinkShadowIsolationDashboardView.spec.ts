import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import FullLinkShadowIsolationDashboardView from './FullLinkShadowIsolationDashboardView.vue'
import * as stressApi from '@/api/fullLinkStressTesting'

describe('FullLinkShadowIsolationDashboardView.vue (UI1.3)', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.spyOn(stressApi, 'listMqRules').mockResolvedValue({
      total: 3,
      rules: [
        {
          rule_id: 'rule_01',
          production_topic: 'order_paid_events',
          shadow_topic: '__shadow_order_paid_events__',
          dead_letter_queue: '__shadow_order_dlq__',
          bypass_action: 'REDIRECT_SHADOW_CONSUMER',
          is_active: true,
        },
        {
          rule_id: 'rule_02',
          production_topic: 'user_sms_notification',
          shadow_topic: '__shadow_user_sms_notification__',
          dead_letter_queue: '__shadow_sms_dlq__',
          bypass_action: 'DROP_SILENTLY',
          is_active: true,
        },
        {
          rule_id: 'rule_03',
          production_topic: 'payment_recharge_callback',
          shadow_topic: '__shadow_payment_recharge_callback__',
          dead_letter_queue: '__shadow_recharge_dlq__',
          bypass_action: 'MOCK_DISPATCH',
          is_active: true,
        },
      ],
    })
  })

  it('正确渲染全链路影子隔离大盘 Header、4 项 KPI 卡片与规则表格', async () => {
    const wrapper = mount(FullLinkShadowIsolationDashboardView, {
      global: {
        stubs: {
          'a-row': { template: '<div><slot /></div>' },
          'a-col': { template: '<div><slot /></div>' },
          'a-card': { template: '<div><slot /></div>' },
          'a-table': { template: '<div class="ant-table"><slot /></div>' },
          'a-tag': { template: '<span class="ant-tag"><slot /></span>' },
          'a-button': { template: '<button><slot /></button>' },
          'a-space': { template: '<div><slot /></div>' },
          'a-input-search': { template: '<input />' },
          'a-modal': { template: '<div><slot /></div>' },
          'a-form': { template: '<form><slot /></form>' },
          'a-form-item': { template: '<div><slot /></div>' },
          'a-input': { template: '<input />' },
          'a-select': { template: '<select><slot /></select>' },
          'a-select-option': { template: '<option><slot /></option>' },
          ShadowTrafficTaintPropagatorDrawer: { template: '<div class="taint-drawer-stub" />' },
          ShadowDatabaseIsolationDrawer: { template: '<div class="db-drawer-stub" />' },
        },
      },
    })

    await flushPromises()

    expect(wrapper.text()).toContain('全链路影子数据与 MQ 消息分流隔离全景大盘')
    expect(wrapper.text()).toContain('全链路影子隔离达标率')
    expect(wrapper.text()).toContain('100.0%')
    expect(wrapper.text()).toContain('已映射影子库表')
    expect(wrapper.text()).toContain('生效中的 MQ 影子规则')
    expect(wrapper.text()).toContain('高危外部旁路拦截数')
    expect(stressApi.listMqRules).toHaveBeenCalledTimes(1)
  })

  it('点击刷新规则按钮触发 listMqRules API', async () => {
    const wrapper = mount(FullLinkShadowIsolationDashboardView, {
      global: {
        stubs: {
          'a-row': { template: '<div><slot /></div>' },
          'a-col': { template: '<div><slot /></div>' },
          'a-card': { template: '<div><slot /></div>' },
          'a-table': { template: '<div class="ant-table"><slot /></div>' },
          'a-tag': { template: '<span class="ant-tag"><slot /></span>' },
          'a-button': {
            props: ['loading'],
            emits: ['click'],
            template: '<button @click="$emit(\'click\')"><slot /></button>',
          },
          'a-space': { template: '<div><slot /></div>' },
          'a-input-search': { template: '<input />' },
          'a-modal': { template: '<div><slot /></div>' },
          'a-form': { template: '<form><slot /></form>' },
          'a-form-item': { template: '<div><slot /></div>' },
          'a-input': { template: '<input />' },
          'a-select': { template: '<select><slot /></select>' },
          'a-select-option': { template: '<option><slot /></option>' },
          ShadowTrafficTaintPropagatorDrawer: { template: '<div class="taint-drawer-stub" />' },
          ShadowDatabaseIsolationDrawer: { template: '<div class="db-drawer-stub" />' },
        },
      },
    })

    await flushPromises()

    const refreshBtn = wrapper.findAll('button').find((b) => b.text().includes('刷新规则'))
    expect(refreshBtn).toBeDefined()
    await refreshBtn?.trigger('click')
    await flushPromises()

    expect(stressApi.listMqRules).toHaveBeenCalledTimes(2)
  })
})
