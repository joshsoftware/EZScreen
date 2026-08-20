import { cn } from '../../lib/cn'

const tones = {
  error: 'text-error bg-error-container/60 border-error-container',
  success: 'text-on-success-container bg-success-container/70 border-success-container',
  info: 'text-on-primary-container bg-primary-container/70 border-primary-fixed-dim',
  warning: 'text-on-warning-container bg-warning-container/80 border-warning-container',
}

export function Alert({ tone = 'error', className, children, ...props }) {
  return (
    <div
      role="alert"
      className={cn(
        'text-body-sm border rounded-lg px-md py-sm shadow-soft',
        tones[tone],
        className,
      )}
      {...props}
    >
      {children}
    </div>
  )
}
