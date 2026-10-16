import { mount, flushPromises } from '@vue/test-utils'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import WebVitalsDiagnosticsView from './WebVitalsDiagnosticsView.vue'
import { webVitalsApi } from '@/api/webVitals'

const mockReport = {
  audit_id: 'audit_wv_abc123',
  target_url: 'https://app.atp.io/dashboard',
  browser_type: 'chromium',
  device_emulation: 'desktop',
  overall_performance_score: 92.5,
  overall_rating: 'good',
  core_vitals: {
    LCP: {
      name: 'Largest Contentful Paint (最大内容绘制)',
      value: 2150.0,
      unit: 'ms',
      rating: 'good',
      good_threshold: 2500.0,
      poor_threshold: 4000.0,
      description: '页面视口内最大文本块或图像绘制完成的时间',
    },
    INP: {
      name: 'Interaction to Next Paint (交互到下次绘制延迟)',
      value: 110.0,
      unit: 'ms',
      rating: 'good',
      good_threshold: 200.0,
      poor_threshold: 500.0,
      description: '衡量用户在页面交互操作后渲染下次绘制的整体延迟',
    },
    CLS: {
      name: 'Cumulative Layout Shift (累积布局偏移)',
      value: 0.04,
      unit: 'score',
      rating: 'good',
      good_threshold: 0.1,
      poor_threshold: 0.25,
      description: '页面生命周期内所有意外布局抖动的累积分数',
    },
  },
  supplementary_vitals: {
    FCP: {
      name: 'First Contentful Paint (首次内容绘制)',
      value: 1250.0,
      unit: 'ms',
      rating: 'good',
      good_threshold: 1800.0,
      poor_threshold: 3000.0,
      description: '浏览器首次渲染任何文本、图像的时间点',
    },
    TTFB: {
      name: 'Time to First Byte (首字节响应时间)',
      value: 310.0,
      unit: 'ms',
      rating: 'good',
      good_threshold: 800.0,
      poor_threshold: 1800.0,
      description: '浏览器发出请求到接收到首字节数据的等待网络时延',
    },
    TBT: {
      name: 'Total Blocking Time (总阻塞时间)',
      value: 120.0,
      unit: 'ms',
      rating: 'good',
      good_threshold: 200.0,
      poor_threshold: 600.0,
      description: '所有超过 50ms 的长任务阻塞时间累加总和',
    },
  },
  blocking_resources: [
    {
      url: 'https://cdn.example.com/assets/vendor-heavy.js',
      resource_type: 'script',
      duration_ms: 380.0,
      transfer_size_kb: 450.0,
      impact: 'high',
      suggestion: '建议使用 defer/async 异步加载或路由级懒加载代码分割',
    },
  ],
  optimization_recommendations: [
    '启用静态资源 Brotli / Gzip 深度压缩，减小网络传输负载',
    '为首屏关键 LCP 图像配置 preload 预加载标签',
  ],
  evaluated_at: '2026-10-16T10:00:00Z',
}

vi.mock('@/api/webVitals', () => ({
  webVitalsApi: {
    listReports: vi.fn(),
    getReport: vi.fn(),
    diagnose: vi.fn(),
  },
}))

vi.mock('ant-design-vue', () => ({
  message: {
    success: vi.fn(),
    error: vi.fn(),
  },
}))

vi.mock('@ant-design/icons-vue', () => ({
  GlobalOutlined: { template: '<span>Global</span>' },
  ReloadOutlined: { template: '<span>Reload</span>' },
  ThunderboltOutlined: { template: '<span>Thunderbolt</span>' },
}))

vi.mock('@/utils/chartTheme', () => ({
  useChartTheme: () => ({ chartTheme: 'atp-light' }),
}))

vi.mock('vue-echarts', () => ({
  default: {
    name: 'VChart',
    props: ['option'],
    template: '<div class="v-chart-radar-stub" />',
  },
}))

describe('WebVitalsDiagnosticsView.vue', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(webVitalsApi.listReports).mockResolvedValue({
      total: 1,
      reports: [mockReport as any],
    })
    vi.mocked(webVitalsApi.getReport).mockResolvedValue(mockReport as any)
  })

  it('renders page hero, diagnosis form, and overall performance score', async () => {
    const wrapper = mount(WebVitalsDiagnosticsView, {
      global: {
        stubs: {
          'a-spin': { template: '<div><slot /></div>' },
          'a-tag': { template: '<span class="ant-tag"><slot /></span>' },
          'a-space': { template: '<div><slot /></div>' },
          'a-button': { template: '<button><slot /></button>' },
          'a-card': { template: '<div class="ant-card"><slot /></div>' },
          'a-form': { template: '<form><slot /></form>' },
          'a-form-item': { template: '<div><slot /></div>' },
          'a-input': { template: '<input />' },
          'a-select': { template: '<select><slot /></select>' },
          'a-select-option': { template: '<option><slot /></option>' },
          'a-table': {
            props: ['dataSource'],
            template: `
              <div class="ant-table-stub">
                <div v-for="item in dataSource" :key="item.url" class="table-row">
                  <span class="url-col">{{ item.url }}</span>
                  <span class="type-col">{{ item.resource_type }}</span>
                  <span class="suggestion-col">{{ item.suggestion }}</span>
                </div>
              </div>
            `,
          },
        },
      },
    })

    await flushPromises()

    // 验证页面标题与总得分
    expect(wrapper.text()).toContain('Web 性能 Core Web Vitals 自动化深度诊断中心')
    expect(wrapper.text()).toContain('92.5')
    expect(wrapper.text()).toContain('综合得分')
    expect(wrapper.text()).toContain('优秀良好')

    // 验证核心体验指标
    expect(wrapper.text()).toContain('LCP')
    expect(wrapper.text()).toContain('2150')
    expect(wrapper.text()).toContain('INP')
    expect(wrapper.text()).toContain('110')
    expect(wrapper.text()).toContain('CLS')
    expect(wrapper.text()).toContain('0.04')

    // 验证辅助指标
    expect(wrapper.text()).toContain('FCP')
    expect(wrapper.text()).toContain('1250')
    expect(wrapper.text()).toContain('TTFB')
    expect(wrapper.text()).toContain('310')
    expect(wrapper.text()).toContain('TBT')
    expect(wrapper.text()).toContain('120')

    // 验证阻断资源与建议
    expect(wrapper.text()).toContain('vendor-heavy.js')
    expect(wrapper.text()).toContain('建议使用 defer/async 异步加载')
    expect(wrapper.text()).toContain('启用静态资源 Brotli / Gzip 深度压缩')

    expect(webVitalsApi.listReports).toHaveBeenCalled()
  })

  it('triggers diagnosis and renders updated report', async () => {
    vi.mocked(webVitalsApi.diagnose).mockResolvedValue({
      message: 'Web Vitals 性能诊断完成',
      report: mockReport as any,
    })

    const wrapper = mount(WebVitalsDiagnosticsView, {
      global: {
        stubs: {
          'a-spin': { template: '<div><slot /></div>' },
          'a-tag': { template: '<span class="ant-tag"><slot /></span>' },
          'a-space': { template: '<div><slot /></div>' },
          'a-button': { template: '<button><slot /></button>' },
          'a-card': { template: '<div class="ant-card"><slot /></div>' },
          'a-form': { template: '<form><slot /></form>' },
          'a-form-item': { template: '<div><slot /></div>' },
          'a-input': { template: '<input />' },
          'a-select': { template: '<select><slot /></select>' },
          'a-select-option': { template: '<option><slot /></option>' },
          'a-table': { template: '<div class="ant-table-stub" />' },
        },
      },
    })

    await flushPromises()

    const vm = wrapper.vm as any
    await vm.handleRunDiagnose()

    expect(webVitalsApi.diagnose).toHaveBeenCalledWith(expect.objectContaining({
      target_url: expect.any(String),
      browser_type: 'chromium',
    }))
  })
})
