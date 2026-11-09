/**
 * useVisiblePolling.ts - 页面可见期间按固定间隔执行任务
 *
 * - 仅在 document.visibilityState === 'visible' 时计时，页面隐藏时清掉定时器；
 *   重新可见时立即执行一次再恢复计时，避免切回标签页后看到旧数据。
 * - 上一次任务未结束时跳过本轮，不叠加请求。
 * - 在组件 setup 中调用时，所属作用域销毁（组件卸载）会自动 stop。
 */
import { getCurrentScope, onScopeDispose } from 'vue'

export function useVisiblePolling(task: () => unknown, intervalMs: number) {
  let timer: ReturnType<typeof setInterval> | null = null
  let inFlight = false
  let active = false

  const isVisible = () => typeof document === 'undefined' || document.visibilityState === 'visible'

  async function tick() {
    if (!active || inFlight || !isVisible()) return
    inFlight = true
    try {
      await task()
    } catch {
      // 轮询失败静默处理，下一轮再试
    } finally {
      inFlight = false
    }
  }

  function startTimer() {
    if (timer === null) timer = setInterval(() => { void tick() }, intervalMs)
  }

  function stopTimer() {
    if (timer !== null) {
      clearInterval(timer)
      timer = null
    }
  }

  function onVisibilityChange() {
    if (!active) return
    if (isVisible()) {
      void tick()
      startTimer()
    } else {
      stopTimer()
    }
  }

  function start() {
    if (active) return
    active = true
    if (typeof document !== 'undefined') document.addEventListener('visibilitychange', onVisibilityChange)
    if (isVisible()) startTimer()
  }

  function stop() {
    active = false
    if (typeof document !== 'undefined') document.removeEventListener('visibilitychange', onVisibilityChange)
    stopTimer()
  }

  if (getCurrentScope()) onScopeDispose(stop)

  return { start, stop }
}
