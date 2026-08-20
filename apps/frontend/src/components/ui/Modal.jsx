import { useEffect, useRef } from 'react'
import { cn } from '../../lib/cn'

export function Modal({ open, onClose, title, children, className }) {
  const dialogRef = useRef(null)

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
      onClose?.()
    }
    el.addEventListener('close', handleClose)
    return () => el.removeEventListener('close', handleClose)
  }, [onClose])

  function handleBackdropClick(event) {
    if (event.target === dialogRef.current) {
      onClose?.()
    }
  }

  return (
    <dialog
      ref={dialogRef}
      onClick={handleBackdropClick}
      style={{ marginTop: '15vh' }}
      className={cn(
        'backdrop:bg-on-surface/40 backdrop:backdrop-blur-sm',
        'rounded-xl border border-outline-variant bg-surface-container-lowest shadow-lg',
        'p-0 max-w-2xl w-full max-h-[85vh] overflow-hidden',
        'open:animate-in open:fade-in-0 open:zoom-in-95',
        className,
      )}
    >
      <div className="flex items-center justify-between px-lg pt-lg pb-sm">
        <h2 className="font-headline-sm text-headline-sm text-on-surface">{title}</h2>
        <button
          type="button"
          onClick={() => onClose?.()}
          className="text-on-surface-variant hover:text-on-surface transition-colors p-xs rounded-DEFAULT"
        >
          <span className="material-symbols-outlined text-[20px]">close</span>
        </button>
      </div>
      <div className="px-lg pb-lg overflow-y-auto max-h-[calc(85vh-4rem)]">{children}</div>
    </dialog>
  )
}
