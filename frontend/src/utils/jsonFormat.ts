import { message } from 'ant-design-vue'

export function tryFormatJson(raw: string, options?: { space?: number; successMsg?: string; errorMsg?: string }): string {
  if (!raw || !raw.trim()) {
    message.info('请输入需要格式化的 JSON 内容')
    return raw
  }
  const space = options?.space ?? 2
  try {
    const parsed = JSON.parse(raw)
    const formatted = JSON.stringify(parsed, null, space)
    message.success(options?.successMsg || 'JSON 格式化成功')
    return formatted
  } catch {
    message.warning(options?.errorMsg || 'JSON 语法错误，无法格式化，请检查逗号、双引号或括号匹配')
    return raw
  }
}

export function tryCompressJson(raw: string, options?: { successMsg?: string; errorMsg?: string }): string {
  if (!raw || !raw.trim()) {
    message.info('请输入需要压缩的 JSON 内容')
    return raw
  }
  try {
    const parsed = JSON.parse(raw)
    const compressed = JSON.stringify(parsed)
    message.success(options?.successMsg || 'JSON 已压缩为单行')
    return compressed
  } catch {
    message.warning(options?.errorMsg || 'JSON 语法错误，无法压缩，请检查语法')
    return raw
  }
}
