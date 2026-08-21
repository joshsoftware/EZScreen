import { cn } from '../../lib/cn'

function sanitizeHtml(html) {
  return html
    .replace(/<script[\s\S]*?>[\s\S]*?<\/script>/gi, '')
    .replace(/<style[\s\S]*?>[\s\S]*?<\/style>/gi, '')
    .replace(/\son\w+="[^"]*"/gi, '')
    .replace(/\son\w+='[^']*'/gi, '')
    .replace(/javascript:/gi, '')
}

export function HtmlContent({ html, className, empty = '—' }) {
  if (!html || !html.replace(/<[^>]*>/g, '').replace(/&nbsp;/g, ' ').trim()) {
    return <p className={cn('text-body-sm text-on-surface-variant', className)}>{empty}</p>
  }

  return (
    <div
      className={cn('rich-text text-body-sm text-on-surface', className)}
      dangerouslySetInnerHTML={{ __html: sanitizeHtml(html) }}
    />
  )
}
