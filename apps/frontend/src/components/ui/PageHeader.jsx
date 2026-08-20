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
          <h1 className="font-headline-md text-headline-md text-on-surface">{title}</h1>
        ) : (
          title
        )}
        {description ? (
          <p className="text-body-sm text-on-surface-variant mt-xs">{description}</p>
        ) : null}
      </div>
      {actions ? <div className="flex flex-wrap items-center gap-sm shrink-0">{actions}</div> : null}
    </div>
  )
}

export function Panel({ title, children, className, bodyClassName }) {
  return (
    <div
      className={cn(
        'bg-surface-container-lowest border border-outline-variant rounded-xl',
        className,
      )}
    >
      {title ? (
        <div className="px-lg pt-lg pb-0">
          <h2 className="font-headline-sm text-headline-sm text-on-surface">{title}</h2>
        </div>
      ) : null}
      <div className={cn('p-lg', bodyClassName)}>{children}</div>
    </div>
  )
}

export function StatCard({ label, value, onClick, selected = false }) {
  const className = cn(
    'bg-surface-container-lowest border rounded-xl p-lg text-left',
    selected ? 'border-secondary ring-2 ring-secondary/20' : 'border-outline-variant',
    onClick ? 'cursor-pointer hover:border-secondary transition-colors' : '',
  )
  const content = (
    <>
      <p className="font-label-md text-label-md text-on-surface-variant uppercase tracking-wider mb-xs">
        {label}
      </p>
      <p className="font-headline-md text-headline-md text-on-surface">{value}</p>
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
