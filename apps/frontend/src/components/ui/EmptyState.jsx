import { cn } from '../../lib/cn'
import { Button } from './Button'

export function EmptyState({
  icon = 'inbox',
  title,
  description,
  actionLabel,
  actionTo,
  className,
}) {
  return (
    <div
      className={cn(
        'flex flex-col items-center justify-center text-center py-2xl px-lg',
        className,
      )}
    >
      <div className="mb-md flex h-14 w-14 items-center justify-center rounded-2xl bg-primary-container/70 text-on-primary-container shadow-soft">
        <span className="material-symbols-outlined text-[28px]">{icon}</span>
      </div>
      <p className="font-headline-sm text-headline-sm text-on-surface mb-xs tracking-tight">
        {title}
      </p>
      {description ? (
        <p className="text-body-sm text-on-surface-variant max-w-sm mb-lg">{description}</p>
      ) : null}
      {actionLabel && actionTo ? (
        <Button to={actionTo} size="md">
          {actionLabel}
        </Button>
      ) : null}
    </div>
  )
}
