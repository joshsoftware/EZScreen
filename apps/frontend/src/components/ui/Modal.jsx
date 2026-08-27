import { useEffect, useRef } from 'react'
import { cn } from '../../lib/cn'

export function Modal({ open, onClose, title, children, className }) {
  const dialogRef = useRef(null)
  const onCloseRef = useRef(onClose)
  onCloseRef.current = onClose

  useEffect(() => {
    const el = dialogRef.current
    if (!el) return
    if (open && !el.open) {
      el.showModal()
    } else if (!open && el.open) {
      el.close()
    }
  }, [open])

  useEffect(() => {
    const el = dialogRef.current
    if (!el) return
    function handleClose() {
      onCloseRef.current?.()
    }
    el.addEventListener('close', handleClose)
    return () => el.removeEventListener('close', handleClose)
  }, [])

  function handleBackdropClick(event) {
    if (event.target === dialogRef.current) {
      onCloseRef.current?.()
    }
  }

  return (
    <dialog
      ref={dialogRef}
      onClick={handleBackdropClick}
      className={cn(
        'fixed inset-0 z-50 m-0 h-full max-h-none w-full max-w-none border-0 bg-transparent p-0',
        'open:flex open:items-center open:justify-center open:pb-[8vh]',
        'backdrop:bg-on-surface/40 backdrop:backdrop-blur-sm',
      )}
    >
      <div
        className={cn(
          'flex max-h-[85vh] w-[calc(100%-2rem)] max-w-2xl flex-col overflow-hidden',
          'rounded-2xl border border-outline-variant/80 bg-surface-container-lowest shadow-lift',
          className,
        )}
        onClick={(event) => event.stopPropagation()}
      >
        <div className="flex shrink-0 items-center justify-between px-lg pt-lg pb-sm">
          <h2 className="min-w-0 truncate font-headline-sm text-headline-sm text-on-surface tracking-tight">
            {title}
          </h2>
          <button
            type="button"
            onClick={() => onCloseRef.current?.()}
            className="shrink-0 rounded-lg p-xs text-on-surface-variant transition-colors hover:bg-surface-container-low hover:text-on-surface"
          >
            <span className="material-symbols-outlined text-[20px]">close</span>
          </button>
        </div>
        <div className="min-h-0 flex-1 overflow-y-auto px-lg pb-lg">{children}</div>
      </div>
    </dialog>
  )
}
