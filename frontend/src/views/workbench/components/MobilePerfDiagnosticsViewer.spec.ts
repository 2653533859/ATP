import { mount, flushPromises } from '@vue/test-utils'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import MobilePerfDiagnosticsViewer from './MobilePerfDiagnosticsViewer.vue'
import { mobilePerfApi } from '@/api/mobilePerf'

const mockSessionReport = {
  session_id: 'session_perf_01',
  device_serial: 'emulator-5554',
  package_name: 'com.atp.autotest.demo',
  started_at: '2026-10-16T10:00:00Z',
  ended_at: null,
  total_samples_count: 6,
  summary: {
    cpu_app_avg: 45.2,
    cpu_app_max: 78.5,
    memory_pss_max: 185.4,
    memory_growth_slope_mb_per_min: 16.8, // 模拟内存持续泄露 (> 5.0)
    fps_avg: 54.0,
    total_janks: 2,
    anomalies_count: 1,
    has_memory_leak: true,
    has_jank_drops: false,
  },
  anomalies: [
    {
      anomaly_type: 'MEMORY_LEAK_WARNING',
      severity: 'critical',
      timestamp_sec: 5.0,
      metric_name: 'memory_growth_slope_mb_per_min',
      metric_value: 16.8,
      threshold: 5.0,
      description: '检测到应用物理内存 (PSS) 呈现线性单调持续增长趋势 (斜率: 16.80 MB/min)，疑似存在内存泄露！',
    },
  ],
  samples_preview: [
    {
      timestamp_sec: 1.0,
      cpu_app_pct: 35.0,
      cpu_total_pct: 55.0,
      memory_pss_mb: 120.0,
      memory_native_heap_mb: 60.0,
      memory_dalvik_heap_mb: 40.0,
      fps: 58.0,
      jank_count: 0,
      net_tx_kbps: 12.0,
      net_rx_kbps: 45.0,
    },
    {
      timestamp_sec: 2.0,
      cpu_app_pct: 42.0,
      cpu_total_pct: 60.0,
      memory_pss_mb: 145.0,
      memory_native_heap_mb: 75.0,
      memory_dalvik_heap_mb: 42.0,
      fps: 55.0,
      jank_count: 0,
      net_tx_kbps: 15.0,
      net_rx_kbps: 50.0,
    },
  ],
}

vi.mock('@/api/mobilePerf', () => ({
  mobilePerfApi: {
    listSessions: vi.fn(),
    getSession: vi.fn(),
    startSession: vi.fn(),
    appendSamples: vi.fn(),
    stopSession: vi.fn(),
  },
}))

vi.mock('ant-design-vue', () => ({
  message: {
    success: vi.fn(),
    error: vi.fn(),
  },
}))

vi.mock('@ant-design/icons-vue', () => ({
  DashboardOutlined: { template: '<span>Dashboard</span>' },
  ReloadOutlined: { template: '<span>Reload</span>' },
  PlayCircleOutlined: { template: '<span>Play</span>' },
  StopOutlined: { template: '<span>Stop</span>' },
  PlusOutlined: { template: '<span>Plus</span>' },
  WarningOutlined: { template: '<span>Warning</span>' },
  AlertOutlined: { template: '<span>Alert</span>' },
  CheckCircleOutlined: { template: '<span>Check</span>' },
}))

vi.mock('vue-echarts', () => ({
  default: {
    name: 'VChart',
    props: ['option'],
    template: '<div class="v-chart-stub" />',
  },
}))
vi.mock('@/utils/chartTheme', () => ({
  useChartTheme: () => ({ chartTheme: 'atp-light' }),
}))

describe('MobilePerfDiagnosticsViewer.vue', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(mobilePerfApi.listSessions).mockResolvedValue({
      total: 1,
      sessions: [mockSessionReport as any],
    })
    vi.mocked(mobilePerfApi.getSession).mockResolvedValue(mockSessionReport as any)
  })

  it('renders header, diagnostic banner and KPI metrics cards', async () => {
    const wrapper = mount(MobilePerfDiagnosticsViewer, {
      global: {
        stubs: {
          'a-spin': { template: '<div><slot /></div>' },
          'a-tag': { template: '<span class="ant-tag"><slot /></span>' },
          'a-space': { template: '<div><slot /></div>' },
          'a-button': { template: '<button><slot /></button>' },
          'a-select': { template: '<select><slot /></select>' },
          'a-card': { template: '<div class="ant-card"><slot /></div>' },
          'a-tabs': { template: '<div><slot /></div>' },
          'a-tab-pane': { template: '<div><slot /></div>' },
          'a-table': {
            props: ['dataSource'],
            template: `
              <div class="ant-table-stub">
                <div v-for="item in dataSource" :key="item.description || item.timestamp_sec" class="table-row">
                  <span v-if="item.description">{{ item.description }}</span>
                </div>
              </div>
            `,
          },
          'a-modal': { template: '<div><slot /></div>' },
          'a-form': { template: '<form><slot /></form>' },
          'a-form-item': { template: '<div><slot /></div>' },
          'a-input': { template: '<input />' },
          'a-input-number': { template: '<input type="number" />' },
          'a-radio-group': { template: '<div><slot /></div>' },
          'a-radio-button': { template: '<button><slot /></button>' },
        },
      },
    })

    await flushPromises()

    // 验证标题与诊断结论
    expect(wrapper.text()).toContain('移动端原生性能剖析与深度质量诊断控制台')
    expect(wrapper.text()).toContain('发现高危性能劣化缺陷')
    expect(wrapper.text()).toContain('16.8 MB/min')

    // 验证核心 KPI 指标
    expect(wrapper.text()).toContain('45.2%')
    expect(wrapper.text()).toContain('185.4')
    expect(wrapper.text()).toContain('54')

    // 验证异常列表渲染
    expect(wrapper.text()).toContain('检测到应用物理内存 (PSS) 呈现线性单调持续增长趋势')
    expect(mobilePerfApi.listSessions).toHaveBeenCalled()
    expect(mobilePerfApi.getSession).toHaveBeenCalledWith('session_perf_01')
  })

  it('triggers session stop and generates diagnostic report', async () => {
    const completedReport = {
      ...mockSessionReport,
      ended_at: '2026-10-16T10:15:00Z',
    }
    vi.mocked(mobilePerfApi.stopSession).mockResolvedValue({
      message: '性能诊断报告已生成',
      report: completedReport as any,
    })

    const wrapper = mount(MobilePerfDiagnosticsViewer, {
      global: {
        stubs: {
          'a-spin': { template: '<div><slot /></div>' },
          'a-tag': { template: '<span class="ant-tag"><slot /></span>' },
          'a-space': { template: '<div><slot /></div>' },
          'a-button': { template: '<button><slot /></button>' },
          'a-select': { template: '<select><slot /></select>' },
          'a-card': { template: '<div class="ant-card"><slot /></div>' },
          'a-tabs': { template: '<div><slot /></div>' },
          'a-tab-pane': { template: '<div><slot /></div>' },
          'a-table': { template: '<div class="ant-table-stub" />' },
          'a-modal': { template: '<div><slot /></div>' },
          'a-form': { template: '<form><slot /></form>' },
          'a-form-item': { template: '<div><slot /></div>' },
          'a-input': { template: '<input />' },
          'a-input-number': { template: '<input type="number" />' },
          'a-radio-group': { template: '<div><slot /></div>' },
          'a-radio-button': { template: '<button><slot /></button>' },
        },
      },
    })

    await flushPromises()

    const vm = wrapper.vm as any
    await vm.handleStopSession()

    expect(mobilePerfApi.stopSession).toHaveBeenCalledWith('session_perf_01')
  })
})
