import { cn } from '../../lib/cn'

export function PageHeader({ title, description, actions, breadcrumb, className }) {
  return (
    <div
      className={cn(
        'flex flex-wrap items-start justify-between gap-md mb-xl',
        className,
      )}
    >
      <div className="min-w-0">
        {breadcrumb ? <div className="mb-xs">{breadcrumb}</div> : null}
        {typeof title === 'string' ? (
          <h1 className="font-headline-md text-headline-md text-on-surface tracking-tight">
            {title}
          </h1>
        ) : (
          title
        )}
        {description ? (
          <p className="text-body-sm text-on-surface-variant mt-xs max-w-2xl">
            {description}
          </p>
        ) : null}
      </div>
      {actions ? (
        <div className="flex flex-wrap items-center gap-sm shrink-0">{actions}</div>
      ) : null}
    </div>
  )
}

export function Panel({ title, children, className, bodyClassName, actions }) {
  return (
    <div
      className={cn(
        'bg-surface-container-lowest/90 border border-outline-variant/80 rounded-xl shadow-soft backdrop-blur-sm',
        className,
      )}
    >
      {title || actions ? (
        <div className="px-lg pt-lg pb-0 flex items-start justify-between gap-md">
          {title ? (
            <h2 className="font-headline-sm text-headline-sm text-on-surface tracking-tight">
              {title}
            </h2>
          ) : (
            <span />
          )}
          {actions ? <div className="shrink-0">{actions}</div> : null}
        </div>
      ) : null}
      <div className={cn('p-lg', bodyClassName)}>{children}</div>
    </div>
  )
}

export function StatCard({ label, value, onClick, selected = false, hint }) {
  const className = cn(
    'bg-surface-container-lowest/90 border rounded-xl p-lg text-left shadow-soft backdrop-blur-sm transition-all',
    selected
      ? 'border-secondary ring-2 ring-secondary/20 shadow-lift'
      : 'border-outline-variant/80',
    onClick
      ? 'cursor-pointer hover:border-secondary/70 hover:shadow-lift hover:-translate-y-0.5'
      : '',
  )
  const content = (
    <>
      <p className="font-label-md text-label-md text-on-surface-variant tracking-wide mb-xs">
        {label}
      </p>
      <p className="font-headline-md text-headline-md text-on-surface tracking-tight">
        {value}
      </p>
      {hint ? (
        <p className="text-label-md text-on-surface-variant mt-xs">{hint}</p>
      ) : null}
    </>
  )
  if (onClick) {
    return (
      <button type="button" onClick={onClick} className={className}>
        {content}
      </button>
    )
  }
  return <div className={className}>{content}</div>
}
