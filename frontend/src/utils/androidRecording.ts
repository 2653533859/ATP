export type AndroidRecordedPoint = { x: number; y: number }

export type AndroidRecordedScreen = { width: number; height: number }

export type AndroidRecordedTarget = {
  text?: string | null
  resourceId?: string | null
  contentDesc?: string | null
  className?: string | null
  bounds?: { left: number; top: number; right: number; bottom: number } | null
}

/**
 * Keep semantic selectors and the original point together.
 *
 * Selectors make a recorded step resilient to small layout changes; the point
 * remains an explicit last-resort fallback when UIAutomator cannot find the
 * same node during replay.
 */
export function buildAndroidRecordedClickParams(
  point: AndroidRecordedPoint,
  target: AndroidRecordedTarget | null,
) {
  const params: Record<string, unknown> = {
    text: target?.text?.trim() || '',
    resourceId: target?.resourceId?.trim() || '',
    contentDesc: target?.contentDesc?.trim() || '',
    x: point.x,
    y: point.y,
  }

  if (target?.className?.trim()) {
    params.className = target.className.trim()
  }
  if (target?.bounds) {
    params.bounds = target.bounds
  }

  return params
}

/**
 * Preserve the screenshot coordinate space for recorded swipes. The worker
 * can use it to scale the gesture when the replay device has another size.
 */
export function buildAndroidRecordedSwipeParams(
  start: AndroidRecordedPoint,
  end: AndroidRecordedPoint,
  screen: AndroidRecordedScreen,
  duration = 300,
) {
  return {
    direction: undefined,
    x1: start.x,
    y1: start.y,
    x2: end.x,
    y2: end.y,
    duration,
    screenWidth: screen.width,
    screenHeight: screen.height,
  }
}
