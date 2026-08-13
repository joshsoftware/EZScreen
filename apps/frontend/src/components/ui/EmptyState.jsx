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
      <span className="material-symbols-outlined text-[36px] text-on-surface-variant mb-md">
        {icon}
      </span>
      <p className="font-headline-sm text-headline-sm text-on-surface mb-xs">{title}</p>
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
