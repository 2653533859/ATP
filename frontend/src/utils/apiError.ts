/**
 * 统一从前端异常对象中提取用户可读的后端错误说明。
 *
 * `http.ts` 响应拦截器会直接 reject 后端 `detail` 纯字符串，
 * 因此必须优先处理 `typeof err === 'string'`，再兼容 AxiosError / Error / 普通对象。
 */
export function extractApiError(err: unknown, fallback = '操作失败'): string {
  if (typeof err === 'string') {
    const trimmed = err.trim()
    return trimmed || fallback
  }
  if (Array.isArray(err)) {
    const msgs = err
      .map((item) => {
        if (typeof item === 'string') return item.trim()
        if (item && typeof item === 'object' && typeof (item as { msg?: unknown }).msg === 'string') {
          return ((item as { msg: string }).msg || '').trim()
        }
        return ''
      })
      .filter(Boolean)
    if (msgs.length > 0) {
      return msgs.join('; ')
    }
    return fallback
  }
  if (err && typeof err === 'object') {
    const record = err as {
      response?: { data?: { detail?: unknown; message?: unknown } }
      detail?: unknown
      message?: unknown
    }
    const responseDetail = record.response?.data?.detail
    if (typeof responseDetail === 'string' && responseDetail.trim()) {
      return responseDetail.trim()
    }
    if (Array.isArray(responseDetail) && responseDetail.length > 0) {
      const first = responseDetail[0] as { msg?: unknown; loc?: unknown }
      if (typeof first?.msg === 'string' && first.msg.trim()) {
        return first.msg.trim()
      }
    }
    const responseMessage = record.response?.data?.message
    if (typeof responseMessage === 'string' && responseMessage.trim()) {
      return responseMessage.trim()
    }
    if (typeof record.detail === 'string' && record.detail.trim()) {
      return record.detail.trim()
    }
    if (typeof record.message === 'string' && record.message.trim()) {
      return record.message.trim()
    }
  }
  return fallback
}
