import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { registerTheme } from 'echarts/core'

vi.mock('echarts/core', () => ({
  registerTheme: vi.fn(),
  use: vi.fn(),
}))

// 本文件验证的是主题注册与随 store 切换的行为，不验证 echarts 模块装配（`use`
// 本身已被 mock，传给它的是什么并不参与断言）。但 chartTheme.ts 会 import 这三个
// echarts 子入口，不 mock 就得让 Vite 真去转换整棵 echarts 子图 —— 每个测试用例
// 里的 `await import('@/utils/chartTheme')` 都要等这份工作，空载约几百毫秒，机器
// 有负载时实测涨到 16.2s，直接撞穿 vitest 默认的 5000ms 超时。
// 这里换掉的是无关的重量级依赖，不是把超时调大。
vi.mock('echarts/charts', () => ({
  BarChart: {},
  LineChart: {},
  PieChart: {},
}))
vi.mock('echarts/components', () => ({
  GridComponent: {},
  LegendComponent: {},
  TitleComponent: {},
  TooltipComponent: {},
}))
vi.mock('echarts/renderers', () => ({
  CanvasRenderer: {},
}))

describe('chart theme utilities', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
    vi.resetModules()
  })

  it('registers light and dark chart themes once', async () => {
    const chartTheme = await import('@/utils/chartTheme')

    expect(registerTheme).toHaveBeenCalledTimes(2)
    expect(registerTheme).toHaveBeenNthCalledWith(
      1,
      chartTheme.ATP_CHART_LIGHT,
      expect.objectContaining({ backgroundColor: 'transparent' }),
    )
    expect(registerTheme).toHaveBeenNthCalledWith(
      2,
      chartTheme.ATP_CHART_DARK,
      expect.objectContaining({ backgroundColor: 'transparent' }),
    )

    chartTheme.ensureChartThemes()
    expect(registerTheme).toHaveBeenCalledTimes(2)
  })

  it('returns a computed chart theme that follows the global theme store', async () => {
    const chartTheme = await import('@/utils/chartTheme')
    const { useThemeStore } = await import('@/stores/theme')
    const themeStore = useThemeStore()
    const { chartTheme: currentChartTheme } = chartTheme.useChartTheme()

    expect(currentChartTheme.value).toBe(chartTheme.ATP_CHART_LIGHT)

    themeStore.setMode('dark')
    expect(currentChartTheme.value).toBe(chartTheme.ATP_CHART_DARK)

    themeStore.setMode('light')
    expect(currentChartTheme.value).toBe(chartTheme.ATP_CHART_LIGHT)
  })
})
