export type AndroidRecordedPoint = { x: number; y: number }

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
