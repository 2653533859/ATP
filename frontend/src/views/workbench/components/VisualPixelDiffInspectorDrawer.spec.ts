import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import VisualPixelDiffInspectorDrawer from './VisualPixelDiffInspectorDrawer.vue'
import * as visualApi from '@/api/visualRegressionA11y'

describe('VisualPixelDiffInspectorDrawer.vue (UI1.1)', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.spyOn(visualApi, 'listMaskRegions').mockResolvedValue({
      total: 1,
      masks: [
        {
          mask_id: 'mask_test_1',
          name: 'test_clock_mask',
          x: 100,
          y: 20,
          width: 80,
          height: 30,
          reason: '测试动态时间戳屏蔽',
          is_active: true,
        },
      ],
    })
    vi.spyOn(visualApi, 'compareVisualPixelDiff').mockResolvedValue({
      message: '对比完成',
      report: {
        report_id: 'diff_rpt_123',
        page_name: 'checkout_view',
        overall_verdict: 'ACCEPTABLE_DRIFT',
        average_ssim_score: 0.965,
        max_mismatch_ratio_pct: 0.85,
        total_diff_clusters_count: 2,
        viewports: [
          {
            viewport_type: 'DESKTOP',
            viewport_width: 1920,
            viewport_height: 1080,
            ssim_score: 0.965,
            mismatch_ratio_pct: 0.85,
            verdict: 'ACCEPTABLE_DRIFT',
            diff_boxes_count: 2,
            diff_boxes: [
              {
                box_id: 'box_1',
                x: 100,
                y: 200,
                width: 150,
                height: 50,
                diff_pixel_count: 120,
                severity: 'HIGH',
              },
            ],
          },
        ],
        created_at: new Date().toISOString(),
      },
    })
  })

  it('正确渲染抽屉标题、头部说明 Banner、四项 KPI 卡片及视口切换栏', async () => {
    const wrapper = mount(VisualPixelDiffInspectorDrawer, {
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
          'a-space': { template: '<div><slot /></div>' },
          'a-radio-group': { template: '<div><slot /></div>' },
          'a-radio-button': { template: '<button><slot /></button>' },
          'a-table': { template: '<div class="ant-table"><slot /></div>' },
          'a-modal': { template: '<div><slot /></div>' },
          'a-form': { template: '<form><slot /></form>' },
          'a-form-item': { template: '<div><slot /></div>' },
          'a-input': { template: '<input />' },
          'a-input-number': { template: '<input type="number" />' },
        },
      },
    })

    await flushPromises()

    expect(wrapper.text()).toContain('多模态视觉像素级对比与动态抗锯齿去噪控制台')
    expect(wrapper.text()).toContain('综合判定结论')
    expect(wrapper.text()).toContain('平均 SSIM 相似度')
    expect(wrapper.text()).toContain('像素差异比率')
    expect(wrapper.text()).toContain('差异聚类区域数')
    expect(wrapper.text()).toContain('Desktop (1920×1080)')
  })

  it('点击立即触发对比按钮能正确调用 API 并更新 SSIM 判定结论与指标', async () => {
    const wrapper = mount(VisualPixelDiffInspectorDrawer, {
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
          'a-space': { template: '<div><slot /></div>' },
          'a-radio-group': { template: '<div><slot /></div>' },
          'a-radio-button': { template: '<button><slot /></button>' },
          'a-table': { template: '<div class="ant-table"><slot /></div>' },
          'a-modal': { template: '<div><slot /></div>' },
          'a-form': { template: '<form><slot /></form>' },
          'a-form-item': { template: '<div><slot /></div>' },
          'a-input': { template: '<input />' },
          'a-input-number': { template: '<input type="number" />' },
        },
      },
    })

    await flushPromises()

    const triggerBtn = wrapper.findAll('button').find(b => b.text().includes('立即触发 SSIM 对比'))
    expect(triggerBtn).toBeDefined()
    await triggerBtn?.trigger('click')
    await flushPromises()

    expect(visualApi.compareVisualPixelDiff).toHaveBeenCalledTimes(1)
    expect(wrapper.text()).toContain('ACCEPTABLE_DRIFT')
    expect(wrapper.text()).toContain('96.5%')
  })
})
