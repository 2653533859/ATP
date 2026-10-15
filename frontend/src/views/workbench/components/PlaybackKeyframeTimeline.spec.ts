import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import PlaybackKeyframeTimeline from './PlaybackKeyframeTimeline.vue'

const mockTimelineReport = {
  report_id: 'rpt_pb_test_881',
  session_id: 'pb_sess_sample_01',
  platform: 'android',
  generated_at: '2026-10-16T10:00:00Z',
  video_summary: {
    video_url: 'http://minio:9000/videos/run_01.mp4',
    duration_seconds: 30.0,
    fps: 30.0,
    total_frames: 900,
  },
  execution_summary: {
    total_steps: 3,
    passed_steps: 1,
    failed_steps: 1,
    healed_steps: 1,
    success_rate: 66.67,
    overall_status: 'failed',
  },
  timeline: [
    {
      step_no: 1,
      action: 'click',
      params: { resource_id: 'btn_search' },
      status: 'passed',
      duration_ms: 150.0,
      video_start_sec: 0.0,
      video_end_sec: 0.15,
      keyframe_frame: 0,
      is_keyframe: false,
      highlight_type: 'normal',
      highlight_color: '#52c41a',
      error_message: null,
      screenshot_url: null,
      healing_details: null,
    },
    {
      step_no: 2,
      action: 'input_text',
      params: { text: '智能手表' },
      status: 'healed',
      duration_ms: 450.0,
      video_start_sec: 0.25,
      video_end_sec: 0.70,
      keyframe_frame: 7,
      is_keyframe: true,
      highlight_type: 'self_healed',
      highlight_color: '#faad14',
      error_message: null,
      screenshot_url: null,
      healing_details: '组件定位由无障碍树模糊评分自愈补偿',
    },
    {
      step_no: 3,
      action: 'assert_text',
      params: { expected_text: '热卖爆款' },
      status: 'failed',
      duration_ms: 200.0,
      video_start_sec: 0.80,
      video_end_sec: 1.00,
      keyframe_frame: 24,
      is_keyframe: true,
      highlight_type: 'failure',
      highlight_color: '#f5222d',
      error_message: '断言失败: 未能在屏幕找到期望文本 "热卖爆款"',
      screenshot_url: null,
      healing_details: null,
    },
  ],
  seek_markers: [
    {
      step_no: 2,
      timestamp_sec: 0.25,
      frame: 7,
      type: 'self_healed',
      color: '#faad14',
      error_message: null,
    },
    {
      step_no: 3,
      timestamp_sec: 0.80,
      frame: 24,
      type: 'failure',
      color: '#f5222d',
      error_message: '断言失败: 未能在屏幕找到期望文本 "热卖爆款"',
    },
  ],
}

const mockCompileRaw = vi.fn().mockResolvedValue(mockTimelineReport)

vi.mock('@/api/devicePlayback', () => ({
  devicePlaybackApi: {
    compileRawTimelineReport: (data: unknown) => mockCompileRaw(data),
    compileSessionTimelineReport: vi.fn(),
    initSession: vi.fn(),
    executeStep: vi.fn(),
    teardownSession: vi.fn(),
    getSession: vi.fn(),
    hybridLocate: vi.fn(),
  },
}))

const globalStubs = {
  'a-drawer': { template: '<div class="ant-drawer"><slot name="title" /><slot /></div>' },
  'a-card': { template: '<div class="ant-card"><h4>{{ $attrs.title }}</h4><slot /></div>' },
  'a-button': { template: '<button class="ant-btn"><slot /></button>' },
  'a-tag': { template: '<span class="ant-tag"><slot /></span>' },
  'a-alert': { template: '<div class="ant-alert">{{ $attrs.message }}</div>' },
  'a-table': {
    props: ['dataSource'],
    template: `
      <div class="ant-table">
        <slot />
        <div v-for="item in dataSource" :key="item.step_no" class="table-row">
          <span>步骤 #{{ item.step_no }}</span>
          <span>{{ item.action }}</span>
          <span>{{ item.video_start_sec }}s ~ {{ item.video_end_sec }}s</span>
          <span>帧 #{{ item.keyframe_frame }}</span>
          <span>{{ item.highlight_type }}</span>
        </div>
      </div>
    `,
  },
}

describe('PlaybackKeyframeTimeline.vue', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders drawer header, timeline tracks, and initial state', () => {
    const wrapper = mount(PlaybackKeyframeTimeline, {
      props: {
        open: true,
        sessionId: 'pb_sess_sample_01',
        platform: 'android',
      },
      global: {
        stubs: globalStubs,
      },
    })

    expect(wrapper.text()).toContain('MP4 录屏毫秒级时间线对齐与异常高亮播放器')
    expect(wrapper.text()).toContain('音画逐帧同步对齐与关键现场标记')
    expect(wrapper.text()).toContain('生成时间线报告')
    expect(wrapper.text()).toContain('当前跳转位点: 0.00 秒')
  })

  it('compiles report and renders seek markers on timeline track', async () => {
    const wrapper = mount(PlaybackKeyframeTimeline, {
      props: {
        open: true,
        sessionId: 'pb_sess_sample_01',
        platform: 'android',
      },
      global: {
        stubs: globalStubs,
      },
    })

    const compileBtn = wrapper.findAll('button').find((b) => b.text().includes('生成时间线报告'))
    expect(compileBtn).toBeDefined()
    await compileBtn!.trigger('click')
    await flushPromises()

    expect(mockCompileRaw).toHaveBeenCalled()
    expect(wrapper.text()).toContain('30 秒')
    expect(wrapper.text()).toContain('900 帧')
    expect(wrapper.text()).toContain('66.67%')
    expect(wrapper.text()).toContain('存在异常/失败')

    // Verify seek markers rendered
    const markers = wrapper.findAll('.seek-marker-pin')
    expect(markers.length).toBe(2)

    // Click marker
    await markers[0].trigger('click')
    expect(wrapper.text()).toContain('当前跳转位点: 0.25 秒')
    expect(wrapper.text()).toContain('帧 #7')
  })
})
