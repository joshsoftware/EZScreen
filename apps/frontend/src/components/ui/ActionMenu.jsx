import { useEffect, useId, useRef, useState } from 'react'
import { cn } from '../../lib/cn'

/**
 * Compact overflow menu for secondary page actions.
 * @param {{ label?: string, items: Array<{ id: string, label: string, icon?: string, danger?: boolean, disabled?: boolean, loading?: boolean, onSelect: () => void }> }} props
 */
export function ActionMenu({ label = 'More actions', items = [] }) {
  const [open, setOpen] = useState(false)
  const rootRef = useRef(null)
  const menuId = useId()

  useEffect(() => {
    if (!open) return undefined

    function onPointerDown(event) {
      if (rootRef.current && !rootRef.current.contains(event.target)) {
        setOpen(false)
      }
    }

    function onKeyDown(event) {
      if (event.key === 'Escape') setOpen(false)
    }

    document.addEventListener('pointerdown', onPointerDown)
    document.addEventListener('keydown', onKeyDown)
    return () => {
      document.removeEventListener('pointerdown', onPointerDown)
      document.removeEventListener('keydown', onKeyDown)
    }
  }, [open])

  const visible = items.filter(Boolean)
  if (visible.length === 0) return null

  return (
    <div ref={rootRef} className="relative">
      <button
        type="button"
        aria-label={label}
        aria-haspopup="menu"
        aria-expanded={open}
        aria-controls={menuId}
        onClick={() => setOpen((value) => !value)}
        className={cn(
          'inline-flex h-11 min-h-11 w-11 items-center justify-center rounded-xl',
          'border border-outline-variant/80 bg-surface-container-lowest text-on-surface-variant',
          'shadow-soft hover:bg-surface-container-high hover:text-on-surface',
          'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/30',
        )}
      >
        <span className="material-symbols-outlined text-[22px]" aria-hidden>
          more_vert
        </span>
      </button>
      {open ? (
        <div
          id={menuId}
          role="menu"
          className="absolute right-0 z-20 mt-xs min-w-[13.5rem] overflow-hidden rounded-xl border border-outline-variant/80 bg-surface-container-lowest py-xs shadow-lift"
        >
          {visible.map((item) => (
            <button
              key={item.id}
              type="button"
              role="menuitem"
              disabled={item.disabled || item.loading}
              onClick={() => {
                if (item.disabled || item.loading) return
                setOpen(false)
                item.onSelect()
              }}
              className={cn(
                'flex w-full items-center gap-sm px-md py-sm text-left text-body-sm whitespace-nowrap',
                'hover:bg-surface-container-high disabled:opacity-50 disabled:pointer-events-none',
                item.danger ? 'text-on-error-container' : 'text-on-surface',
              )}
            >
              {item.icon ? (
                <span className="material-symbols-outlined text-[18px]" aria-hidden>
                  {item.icon}
                </span>
              ) : null}
              {item.loading ? 'Working…' : item.label}
            </button>
          ))}
        </div>
      ) : null}
    </div>
  )
}
