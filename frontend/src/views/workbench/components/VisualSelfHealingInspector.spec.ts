import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import VisualSelfHealingInspector from './VisualSelfHealingInspector.vue'

const mockLocateResponse = {
  success: true,
  matched_strategy: 'visual_ocr',
  confidence_score: 0.95,
  healed: true,
  click_coordinates: [140, 245],
  target_element: {
    text: '确认支付',
    bounds: [40, 220, 240, 270],
  },
  healing_details: 'DOM 目标未直接命中，通过视觉截图 OCR 定位并在中心点 (140, 245) 触发自愈补偿',
}

const mockHybridLocate = vi.fn().mockResolvedValue(mockLocateResponse)

vi.mock('@/api/devicePlayback', () => ({
  devicePlaybackApi: {
    hybridLocate: (data: unknown) => mockHybridLocate(data),
    initSession: vi.fn(),
    executeStep: vi.fn(),
    teardownSession: vi.fn(),
    getSession: vi.fn(),
  },
}))

const globalStubs = {
  'a-drawer': { template: '<div class="ant-drawer"><slot name="title" /><slot /></div>' },
  'a-card': { template: '<div class="ant-card"><h4>{{ $attrs.title }}</h4><slot /></div>' },
  'a-button': { template: '<button class="ant-btn"><slot /></button>' },
  'a-tag': { template: '<span class="ant-tag"><slot /></span>' },
  'a-alert': { template: '<div class="ant-alert">{{ $attrs.message }}</div>' },
  'a-timeline': { template: '<div class="ant-timeline"><slot /></div>' },
  'a-timeline-item': { template: '<div class="ant-timeline-item"><slot /></div>' },
}

describe('VisualSelfHealingInspector.vue', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders drawer header, tier descriptions, and initial state', () => {
    const wrapper = mount(VisualSelfHealingInspector, {
      props: {
        open: true,
      },
      global: {
        stubs: globalStubs,
      },
    })

    expect(wrapper.text()).toContain('视觉/DOM 混合自愈与 OCR 物理边界比对器')
    expect(wrapper.text()).toContain('三层级混合定位与动态自愈决策引擎')
    expect(wrapper.text()).toContain('执行自愈定位比对')
    expect(wrapper.text()).toContain('Tier 1: 绝对精确 DOM / ID 匹配')
    expect(wrapper.text()).toContain('Tier 2: 无障碍树启发模糊加权')
    expect(wrapper.text()).toContain('Tier 3: 视觉截图 OCR 物理边界自愈')
  })

  it('triggers hybrid locate diagnosis and renders derived coordinates', async () => {
    const wrapper = mount(VisualSelfHealingInspector, {
      props: {
        open: true,
      },
      global: {
        stubs: globalStubs,
      },
    })

    const locateBtn = wrapper.findAll('button').find((b) => b.text().includes('执行自愈定位比对'))
    expect(locateBtn).toBeDefined()
    await locateBtn!.trigger('click')
    await flushPromises()

    expect(mockHybridLocate).toHaveBeenCalled()
    expect(wrapper.emitted('healed')).toBeTruthy()
    expect(wrapper.text()).toContain('Tier 3 视觉 OCR 自愈')
    expect(wrapper.text()).toContain('已触发自愈补偿')
    expect(wrapper.text()).toContain('95%')
    expect(wrapper.text()).toContain('X: 140, Y: 245')
    expect(wrapper.text()).toContain('OCR 成功捕获文字中心坐标并自愈!')
  })
})
