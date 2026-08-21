import { cn } from '../../lib/cn'

const tones = {
  success: 'bg-success-container text-on-success-container',
  danger: 'bg-error-container text-on-error-container',
  warning: 'bg-warning-container text-on-warning-container',
  neutral: 'bg-surface-container-high text-on-surface-variant',
  info: 'bg-primary-container text-on-primary-container',
}

export function Badge({ tone = 'neutral', className, children }) {
  return (
    <span
      className={cn(
        'inline-flex items-center text-label-md px-sm py-xs rounded-full font-medium ring-1 ring-inset ring-black/5',
        tones[tone],
        className,
      )}
    >
      {children}
    </span>
  )
}
