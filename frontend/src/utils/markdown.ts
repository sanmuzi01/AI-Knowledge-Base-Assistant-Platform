import DOMPurify from 'dompurify'
import { marked } from 'marked'

export function renderMarkdown(text: string, citations = false): string {
  // 脚本生成的文件链接是 [名称](attachment://ID)。DOMPurify 会删掉未知协议的 href，
  // 所以先改成页内锚点，点击时由页面拦截并带登录态下载。
  const source = (text || '').replace(/\]\(attachment:\/\/([0-9a-f]{24})\)/g, '](#attachment-$1)')
  let html = marked.parse(source, { async: false }) as string
  if (citations) {
    html = html.replace(/【来源(\d+)】/g, '<span class="cite-ref" data-cite="$1">【来源$1】</span>')
  }
  return DOMPurify.sanitize(html, { USE_PROFILES: { html: true } })
}
