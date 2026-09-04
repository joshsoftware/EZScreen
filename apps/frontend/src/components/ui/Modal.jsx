import { useEffect } from 'react'
import { createPortal } from 'react-dom'
import { cn } from '../../lib/cn'

export function Modal({ open, onClose, title, children, className }) {
  useEffect(() => {
    if (!open) return undefined
    const previous = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    return () => {
      document.body.style.overflow = previous
    }
  }, [open])

  useEffect(() => {
    if (!open) return undefined
    function onKeyDown(event) {
      if (event.key === 'Escape') onClose?.()
    }
    window.addEventListener('keydown', onKeyDown)
    return () => window.removeEventListener('keydown', onKeyDown)
  }, [open, onClose])

  if (!open || typeof document === 'undefined') return null

  return createPortal(
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-on-surface/40 p-md pb-[8vh] backdrop-blur-sm"
      role="presentation"
      onMouseDown={(event) => {
        if (event.target === event.currentTarget) onClose?.()
      }}
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-label={typeof title === 'string' ? title : undefined}
        className={cn(
          'flex max-h-[85vh] w-full max-w-2xl flex-col overflow-hidden',
          'rounded-2xl border border-outline-variant/80 bg-surface-container-lowest shadow-lift',
          className,
        )}
        onMouseDown={(event) => event.stopPropagation()}
      >
        <div className="flex shrink-0 items-center justify-between px-lg pt-lg pb-sm">
          <h2 className="min-w-0 truncate font-headline-sm text-headline-sm text-on-surface tracking-tight">
            {title}
          </h2>
          <button
            type="button"
            onClick={() => onClose?.()}
            className="shrink-0 rounded-lg p-xs text-on-surface-variant transition-colors hover:bg-surface-container-low hover:text-on-surface"
          >
            <span className="material-symbols-outlined text-[20px]">close</span>
          </button>
        </div>
        <div className="min-h-0 flex-1 overflow-y-auto px-lg pb-lg">{children}</div>
      </div>
    </div>,
    document.body,
  )
}
