import DOMPurify from 'dompurify'
import { marked } from 'marked'

marked.use({
  breaks: true,
  gfm: true,
})

/**
 * 将 Markdown 文本渲染为可安全用于 v-html 的 HTML。
 *
 * LLM 输出与被测系统的响应文本都可能携带任意 HTML（存储型 XSS 载体），
 * marked 本身不做任何转义，必须经 DOMPurify 净化后再渲染。
 */
export function renderMarkdown(content?: string | null): string {
  if (!content) return ''
  try {
    return DOMPurify.sanitize(marked.parse(content, { async: false }) as string)
  } catch {
    return DOMPurify.sanitize(String(content))
  }
}
