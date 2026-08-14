import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { createRunWebSocket } from './websocket'

class FakeWebSocket {
  static instances: FakeWebSocket[] = []

  onmessage: ((event: MessageEvent) => void) | null = null
  onclose: ((event: CloseEvent) => void) | null = null
  onerror: (() => void) | null = null
  close = vi.fn((code = 1000) => {
    this.onclose?.({ code } as CloseEvent)
  })

  constructor(public readonly url: string) {
    FakeWebSocket.instances.push(this)
  }
}

describe('createRunWebSocket', () => {
  beforeEach(() => {
    FakeWebSocket.instances = []
    vi.useFakeTimers()
    vi.stubGlobal('WebSocket', FakeWebSocket)
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('uses the HttpOnly cookie session and dispatches JSON messages', () => {
    const onMessage = vi.fn()

    createRunWebSocket(42, onMessage)
    const socket = FakeWebSocket.instances[0]

    expect(socket.url).toBe('ws://localhost:5173/ws/runs/42')

    socket.onmessage?.({
      data: JSON.stringify({ type: 'completed', run_id: 42, status: 'passed' }),
    } as MessageEvent)
    socket.onmessage?.({ data: 'not-json' } as MessageEvent)

    expect(onMessage).toHaveBeenCalledTimes(1)
    expect(onMessage).toHaveBeenCalledWith({ type: 'completed', run_id: 42, status: 'passed' })
  })

  it('reconnects non-normal closes and suppresses reconnects after manual close', async () => {
    const onClose = vi.fn()
    const connection = createRunWebSocket(7, vi.fn(), onClose)

    FakeWebSocket.instances[0].onclose?.({ code: 1006 } as CloseEvent)
    expect(FakeWebSocket.instances).toHaveLength(1)

    await vi.advanceTimersByTimeAsync(1000)
    expect(FakeWebSocket.instances).toHaveLength(2)

    connection.close()

    expect(FakeWebSocket.instances[1].close).toHaveBeenCalledWith(1000)
    expect(onClose).toHaveBeenCalledOnce()
  })

  it('adds the mobile run type to isolate Android special events', () => {
    createRunWebSocket(8, vi.fn(), undefined, 'mobile')

    expect(FakeWebSocket.instances[0].url).toBe('ws://localhost:5173/ws/runs/8?run_type=mobile')
  })
})
