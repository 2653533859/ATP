export type AndroidRecordedPoint = { x: number; y: number }

export type AndroidRecordedStepDraft = {
  action: string
  name: string
  params: Record<string, unknown>
}

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

export type AndroidRecordedAssertionMode = 'assert_text' | 'assert_element'

export type AndroidUiAnchorSummary = {
  text?: string | null
  resourceId?: string | null
  contentDesc?: string | null
  packageName?: string | null
}

function hasSameTrailingAssertion(
  steps: ReadonlyArray<{ action?: string; params?: Record<string, unknown> }>,
  action: AndroidRecordedAssertionMode,
  params: Record<string, unknown>,
) {
  const key = action === 'assert_element' ? 'resourceId' : 'text'
  const expected = String(params[key] || '').trim()
  if (!expected) return false
  for (let i = steps.length - 1; i >= 0; i -= 1) {
    const step = steps[i]
    if (!step?.action || !step.action.startsWith('assert_')) {
      break
    }
    if (step.action === action && String(step.params?.[key] || '').trim() === expected) {
      return true
    }
  }
  return false
}

/**
 * Build valid assertion step(s) from UIAutomator screen anchors while skipping duplicates.
 * Matches backend precheck rules: `assert_element` requires non-empty `resourceId`;
 * `assert_text` requires non-empty `text`.
 */
export function buildAndroidAutoAssertionSteps(
  anchors: AndroidUiAnchorSummary | null | undefined,
  existingSteps: ReadonlyArray<{ action?: string; params?: Record<string, unknown> }> = [],
): AndroidRecordedStepDraft[] {
  if (!anchors) return []
  const created: AndroidRecordedStepDraft[] = []
  const resourceId = anchors.resourceId?.trim() || ''
  if (resourceId) {
    const params = { resourceId }
    if (!hasSameTrailingAssertion(existingSteps, 'assert_element', params)) {
      created.push({
        action: 'assert_element',
        name: `断言元素 ${resourceId}`,
        params,
      })
    }
  }

  const text = anchors.text?.trim() || (!resourceId ? anchors.contentDesc?.trim() || '' : '')
  if (text) {
    const params = { text }
    if (!hasSameTrailingAssertion(existingSteps, 'assert_text', params)) {
      created.push({
        action: 'assert_text',
        name: `断言文本 ${text}`,
        params,
      })
    }
  }
  return created
}

/**
 * Build a specific assertion step from an inspected UIAutomator target.
 */
export function buildAndroidAssertionStepFromTarget(
  mode: AndroidRecordedAssertionMode,
  target: AndroidRecordedTarget | null | undefined,
): AndroidRecordedStepDraft | null {
  if (!target) return null
  if (mode === 'assert_element') {
    const resourceId = target.resourceId?.trim() || ''
    if (!resourceId) return null
    return {
      action: 'assert_element',
      name: `断言元素 ${resourceId}`,
      params: { resourceId },
    }
  }
  const text = target.text?.trim() || target.contentDesc?.trim() || ''
  if (!text) return null
  return {
    action: 'assert_text',
    name: `断言文本 ${text}`,
    params: { text },
  }
}

/**
 * Pick the most intuitive assertion step from a tapped UIAutomator target:
 * prefers readable `text`, falls back to stable `resourceId`, then `contentDesc`.
 */
export function buildAndroidBestAssertionStepFromTarget(
  target: AndroidRecordedTarget | null | undefined,
): AndroidRecordedStepDraft | null {
  if (!target) return null
  const text = target.text?.trim() || ''
  if (text) {
    return {
      action: 'assert_text',
      name: `断言文本 ${text}`,
      params: { text },
    }
  }
  const resourceId = target.resourceId?.trim() || ''
  if (resourceId) {
    return {
      action: 'assert_element',
      name: `断言元素 ${resourceId}`,
      params: { resourceId },
    }
  }
  const contentDesc = target.contentDesc?.trim() || ''
  if (contentDesc) {
    return {
      action: 'assert_text',
      name: `断言文本 ${contentDesc}`,
      params: { text: contentDesc },
    }
  }
  return null
}
