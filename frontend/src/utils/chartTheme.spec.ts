import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { registerTheme } from 'echarts/core'

vi.mock('echarts/core', () => ({
  registerTheme: vi.fn(),
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
