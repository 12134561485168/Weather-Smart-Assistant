// 轻量 Markdown 渲染：先转义 HTML 再仅注入白名单标签，保证安全。
// 支持：标题(#…######)、粗体(**)、斜体(*)、行内代码(`)、无序列表(-/*)、有序列表(1.)、链接。
export function escapeHtml(s) {
  return s
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;')
}

export function inlineMd(s) {
  return escapeHtml(s)
    .replace(/`([^`]+)`/g, '<code>$1</code>')
    .replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>')
    .replace(/(^|[^*])\*([^*\n]+)\*/g, '$1<em>$2</em>')
    .replace(/\[([^\]]+)\]\((https?:[^)\s]+)\)/g, '<a href="$2" target="_blank" rel="noopener">$1</a>')
}

export function renderMarkdown(text) {
  if (!text) return ''
  let html = ''
  let listTag = null // 'ul' | 'ol' | null，用于连续列表合并
  const closeList = () => {
    if (listTag) {
      html += `</${listTag}>`
      listTag = null
    }
  }
  for (const raw of String(text).split(/\r?\n/)) {
    const line = raw.trim()
    if (!line) {
      closeList()
      continue
    }
    // 标题：h1/h2 缩一到两级，保持气泡内层级不过大
    const h = /^(#{1,6})\s+(.*)$/.exec(line)
    if (h) {
      closeList()
      const lv = Math.min(h[1].length + 2, 6)
      html += `<h${lv}>${inlineMd(h[2])}</h${lv}>`
      continue
    }
    // 无序列表
    const ul = /^[-*]\s+(.*)$/.exec(line)
    if (ul) {
      if (listTag !== 'ul') {
        closeList()
        html += '<ul>'
        listTag = 'ul'
      }
      html += `<li>${inlineMd(ul[1])}</li>`
      continue
    }
    // 有序列表
    const ol = /^\d+[.、)]\s+(.*)$/.exec(line)
    if (ol) {
      if (listTag !== 'ol') {
        closeList()
        html += '<ol>'
        listTag = 'ol'
      }
      html += `<li>${inlineMd(ol[1])}</li>`
      continue
    }
    closeList()
    html += `<p>${inlineMd(line)}</p>`
  }
  closeList()
  return html
}