import { mount } from '@vue/test-utils'
import { defineComponent, h, onMounted } from 'vue'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { useVisiblePolling } from './useVisiblePolling'

let visibility: DocumentVisibilityState = 'visible'

function setVisibility(state: DocumentVisibilityState) {
  visibility = state
  document.dispatchEvent(new Event('visibilitychange'))
}

function mountPoller(task: () => unknown, intervalMs = 15000) {
  return mount(
    defineComponent({
      setup() {
        const polling = useVisiblePolling(task, intervalMs)
        onMounted(polling.start)
        return () => h('div')
      },
    }),
  )
}

beforeEach(() => {
  vi.useFakeTimers()
  visibility = 'visible'
  Object.defineProperty(document, 'visibilityState', { configurable: true, get: () => visibility })
})

afterEach(() => {
  vi.clearAllTimers()
  vi.useRealTimers()
  delete (document as unknown as Record<string, unknown>).visibilityState
})

describe('useVisiblePolling', () => {
  it('runs the task on every interval while the page is visible', async () => {
    const task = vi.fn().mockResolvedValue(undefined)
    mountPoller(task)

    expect(task).not.toHaveBeenCalled()
    await vi.advanceTimersByTimeAsync(15000)
    expect(task).toHaveBeenCalledTimes(1)
    await vi.advanceTimersByTimeAsync(30000)
    expect(task).toHaveBeenCalledTimes(3)
  })

  it('pauses while hidden and refreshes immediately when visible again', async () => {
    const task = vi.fn().mockResolvedValue(undefined)
    mountPoller(task)

    setVisibility('hidden')
    await vi.advanceTimersByTimeAsync(60000)
    expect(task).not.toHaveBeenCalled()
    expect(vi.getTimerCount()).toBe(0)

    setVisibility('visible')
    await vi.advanceTimersByTimeAsync(0)
    expect(task).toHaveBeenCalledTimes(1)
    await vi.advanceTimersByTimeAsync(15000)
    expect(task).toHaveBeenCalledTimes(2)
  })

  it('does not start a timer when mounted in a hidden page', async () => {
    visibility = 'hidden'
    const task = vi.fn().mockResolvedValue(undefined)
    mountPoller(task)

    await vi.advanceTimersByTimeAsync(60000)
    expect(task).not.toHaveBeenCalled()
    expect(vi.getTimerCount()).toBe(0)
  })

  it('skips ticks while the previous run is still pending', async () => {
    let resolveRun!: () => void
    const task = vi.fn(() => new Promise<void>((resolve) => { resolveRun = resolve }))
    mountPoller(task)

    await vi.advanceTimersByTimeAsync(45000)
    expect(task).toHaveBeenCalledTimes(1)

    resolveRun()
    await vi.advanceTimersByTimeAsync(15000)
    expect(task).toHaveBeenCalledTimes(2)
  })

  it('keeps polling after a failed run', async () => {
    const task = vi.fn().mockRejectedValueOnce(new Error('network')).mockResolvedValue(undefined)
    mountPoller(task)

    await vi.advanceTimersByTimeAsync(30000)
    expect(task).toHaveBeenCalledTimes(2)
  })

  it('stops the timer and the visibility listener on unmount', async () => {
    const task = vi.fn().mockResolvedValue(undefined)
    const wrapper = mountPoller(task)
    wrapper.unmount()

    expect(vi.getTimerCount()).toBe(0)
    setVisibility('hidden')
    setVisibility('visible')
    await vi.advanceTimersByTimeAsync(60000)
    expect(task).not.toHaveBeenCalled()
  })
})
