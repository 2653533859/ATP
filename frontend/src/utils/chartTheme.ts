import { computed } from 'vue'
import { registerTheme } from 'echarts/core'
import { useThemeStore } from '@/stores/theme'

export const ATP_CHART_LIGHT = 'atp-light'
export const ATP_CHART_DARK = 'atp-dark'

// 调色板：与设计系统 Indigo 强调色协调，浅/深各一套
const LIGHT_PALETTE = ['#4f46e5', '#16a34a', '#d97706', '#dc2626', '#0891b2', '#7c3aed', '#db2777', '#0d9488']
const DARK_PALETTE = ['#818cf8', '#22c55e', '#f59e0b', '#f87171', '#22d3ee', '#a78bfa', '#f472b6', '#2dd4bf']

interface ThemeColors {
  palette: string[]
  axis: string
  label: string
  split: string
  legend: string
  tooltipBg: string
  tooltipBorder: string
  tooltipText: string
}

function buildTheme(c: ThemeColors) {
  const axisCommon = {
    axisLine: { lineStyle: { color: c.axis } },
    axisTick: { lineStyle: { color: c.axis } },
    axisLabel: { color: c.label },
    splitLine: { lineStyle: { color: c.split } },
  }
  return {
    color: c.palette,
    backgroundColor: 'transparent',
    textStyle: { color: c.label },
    title: { textStyle: { color: c.legend } },
    categoryAxis: axisCommon,
    valueAxis: axisCommon,
    logAxis: axisCommon,
    timeAxis: axisCommon,
    legend: { textStyle: { color: c.legend } },
    tooltip: {
      backgroundColor: c.tooltipBg,
      borderColor: c.tooltipBorder,
      textStyle: { color: c.tooltipText },
    },
  }
}

let registered = false

/** 注册 atp-light / atp-dark 两套 echarts 主题（幂等）。全量 echarts 与 echarts/core 共享注册表。 */
export function ensureChartThemes() {
  if (registered) return
  registerTheme(
    ATP_CHART_LIGHT,
    buildTheme({
      palette: LIGHT_PALETTE,
      axis: '#e2e8f0',
      label: '#64748b',
      split: '#f1f5f9',
      legend: '#64748b',
      tooltipBg: '#ffffff',
      tooltipBorder: '#e2e8f0',
      tooltipText: '#0f172a',
    }),
  )
  registerTheme(
    ATP_CHART_DARK,
    buildTheme({
      palette: DARK_PALETTE,
      axis: '#334155',
      label: '#94a3b8',
      split: '#1e293b',
      legend: '#94a3b8',
      tooltipBg: '#1e293b',
      tooltipBorder: '#334155',
      tooltipText: '#f1f5f9',
    }),
  )
  registered = true
}

ensureChartThemes()

/** 返回随全局主题切换的 echarts 主题名，供 v-chart :theme 或 echarts.init 使用。 */
export function useChartTheme() {
  const themeStore = useThemeStore()
  const chartTheme = computed(() => (themeStore.mode === 'dark' ? ATP_CHART_DARK : ATP_CHART_LIGHT))
  return { chartTheme }
}
