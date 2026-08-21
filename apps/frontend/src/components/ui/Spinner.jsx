import { cn } from '../../lib/cn'

export function Spinner({ className }) {
  return (
    <span
      className={cn(
        'inline-block h-5 w-5 rounded-full border-2 border-current border-r-transparent animate-spin',
        className,
      )}
      aria-hidden
    />
  )
}
