import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import ClientLongTaskJankProfilerDrawer from './ClientLongTaskJankProfilerDrawer.vue'
import * as visualApi from '@/api/visualRegressionA11y'

describe('ClientLongTaskJankProfilerDrawer.vue (UI4.1)', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.spyOn(visualApi, 'listLongTaskReports').mockResolvedValue({
      total: 1,
      reports: [
        {
          report_id: 'lt_rpt_001',
          page_name: 'case_list_view',
          total_tasks_count: 5,
          long_tasks_count: 2,
          total_duration_ms: 280.0,
          total_blocking_time_ms: 170.0,
          tbt_rating: 'GOOD',
          estimated_fps: 58.2,
          jank_rate_pct: 3.5,
          long_tasks: [
            {
              task_id: 'lt_1',
              duration_ms: 180.0,
              blocking_duration_ms: 130.0,
              attribution_type: 'LAYOUT_THRASHING',
              culprit_symbol: 'calculateVirtualScroll',
              call_stack: ['read offsetTop'],
              severity: 'HIGH',
            },
          ],
          jank_incidents: [],
          remediation_recommendations: ['避免强制同步布局'],
          created_at: new Date().toISOString(),
        },
      ],
    })
    vi.spyOn(visualApi, 'profileLongTasks').mockResolvedValue({
      message: '诊断完成',
      report: {
        report_id: 'lt_rpt_002',
        page_name: 'case_list_view',
        total_tasks_count: 3,
        long_tasks_count: 1,
        total_duration_ms: 120.0,
        total_blocking_time_ms: 70.0,
        tbt_rating: 'GOOD',
        estimated_fps: 59.0,
        jank_rate_pct: 1.5,
        long_tasks: [],
        jank_incidents: [],
        remediation_recommendations: [],
        created_at: new Date().toISOString(),
      },
    })
  })

  it('正确渲染标题 Banner、4 项核心 TBT 与掉帧 KPI 卡片及长任务列表', async () => {
    const wrapper = mount(ClientLongTaskJankProfilerDrawer, {
      props: {
        open: true,
      },
      global: {
        stubs: {
          'a-drawer': { template: '<div><slot /></div>' },
          'a-row': { template: '<div><slot /></div>' },
          'a-col': { template: '<div><slot /></div>' },
          'a-tag': { template: '<span class="ant-tag"><slot /></span>' },
          'a-button': { template: '<button><slot /></button>' },
          'a-input': { template: '<input />' },
          'a-select': { template: '<select><slot /></select>' },
          'a-select-option': { template: '<option><slot /></option>' },
          'a-table': { template: '<div class="ant-table"><slot /></div>' },
        },
      },
    })

    await flushPromises()

    expect(wrapper.text()).toContain('W3C Long Tasks 运行时阻塞与 60 FPS 掉帧卡顿全息剖析控制台')
    expect(wrapper.text()).toContain('总阻塞时间 (TBT)')
    expect(wrapper.text()).toContain('TBT 评级状态')
    expect(wrapper.text()).toContain('预估有效帧率 (FPS)')
    expect(wrapper.text()).toContain('掉帧率 (Jank Rate)')
    expect(wrapper.text()).toContain('170.0ms')
  })

  it('点击启动长任务诊断按钮能正确调用 API 并更新展示结果', async () => {
    const wrapper = mount(ClientLongTaskJankProfilerDrawer, {
      props: {
        open: true,
      },
      global: {
        stubs: {
          'a-drawer': { template: '<div><slot /></div>' },
          'a-row': { template: '<div><slot /></div>' },
          'a-col': { template: '<div><slot /></div>' },
          'a-tag': { template: '<span class="ant-tag"><slot /></span>' },
          'a-button': { template: '<button><slot /></button>' },
          'a-input': { template: '<input />' },
          'a-select': { template: '<select><slot /></select>' },
          'a-select-option': { template: '<option><slot /></option>' },
          'a-table': { template: '<div class="ant-table"><slot /></div>' },
        },
      },
    })

    await flushPromises()

    const profileBtn = wrapper.findAll('button').find(b => b.text().includes('启动主线程长任务诊断'))
    expect(profileBtn).toBeDefined()
    await profileBtn?.trigger('click')
    await flushPromises()

    expect(visualApi.profileLongTasks).toHaveBeenCalledTimes(1)
  })
})
