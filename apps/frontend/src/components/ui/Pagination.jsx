import { cn } from '../../lib/cn'
import { Button } from './Button'

/** Page numbers to show: first, last, and a window around the current page. */
function pageItems(page, pageCount) {
  const pages = new Set([1, pageCount, page - 1, page, page + 1])
  const sorted = [...pages].filter((p) => p >= 1 && p <= pageCount).sort((a, b) => a - b)
  const items = []
  sorted.forEach((p, index) => {
    if (index > 0 && p - sorted[index - 1] > 1) items.push(`gap-${p}`)
    items.push(p)
  })
  return items
}

/**
 * "Showing 21–40 of 57" with Previous / page numbers / Next.
 * Renders nothing when everything fits on one page.
 */
export function Pagination({ page, pageSize, total, onPageChange, className }) {
  const pageCount = Math.max(1, Math.ceil(total / pageSize))
  if (total <= pageSize) return null

  const current = Math.min(Math.max(page, 1), pageCount)
  const from = (current - 1) * pageSize + 1
  const to = Math.min(current * pageSize, total)

  return (
    <nav
      aria-label="Pagination"
      className={cn(
        'flex flex-wrap items-center justify-between gap-sm px-md py-sm border-t border-outline-variant',
        className,
      )}
    >
      <p className="text-body-sm text-on-surface-variant">
        Showing {from}–{to} of {total}
      </p>
      <div className="flex flex-wrap items-center gap-xs">
        <Button
          variant="ghost"
          size="sm"
          icon="chevron_left"
          disabled={current <= 1}
          onClick={() => onPageChange(current - 1)}
        >
          Previous
        </Button>
        {pageItems(current, pageCount).map((item) =>
          typeof item === 'number' ? (
            <button
              key={item}
              type="button"
              onClick={() => onPageChange(item)}
              aria-current={item === current ? 'page' : undefined}
              className={cn(
                'h-10 min-w-10 px-sm rounded-xl text-body-sm transition-colors',
                item === current
                  ? 'bg-primary text-white font-medium'
                  : 'text-on-surface hover:bg-primary-container/60',
              )}
            >
              {item}
            </button>
          ) : (
            <span key={item} className="px-xs text-on-surface-variant" aria-hidden>
              …
            </span>
          ),
        )}
        <Button
          variant="ghost"
          size="sm"
          disabled={current >= pageCount}
          onClick={() => onPageChange(current + 1)}
        >
          Next
          <span className="material-symbols-outlined text-[18px]" aria-hidden>
            chevron_right
          </span>
        </Button>
      </div>
    </nav>
  )
}
