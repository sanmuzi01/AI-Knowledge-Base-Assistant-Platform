import DOMPurify from 'dompurify'
import { marked } from 'marked'

export function renderMarkdown(text: string, citations = false): string {
  let html = marked.parse(text || '', { async: false }) as string
  if (citations) {
    html = html.replace(/【来源(\d+)】/g, '<span class="cite-ref" data-cite="$1">【来源$1】</span>')
  }
  return DOMPurify.sanitize(html, { USE_PROFILES: { html: true } })
}
