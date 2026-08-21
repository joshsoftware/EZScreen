import { cn } from '../../lib/cn'

const fieldClass =
  'w-full h-11 px-md border border-outline-variant/90 rounded-lg text-body-sm bg-surface-container-lowest/95 text-on-surface shadow-soft placeholder:text-on-surface-variant/65 focus:outline-none focus:ring-2 focus:ring-primary/30 focus:border-primary focus:shadow-focus transition-shadow disabled:opacity-60'

export function Label({ htmlFor, className, children }) {
  return (
    <label
      htmlFor={htmlFor}
      className={cn('block font-label-md text-label-md text-on-surface mb-xs', className)}
    >
      {children}
    </label>
  )
}

export function Input({ className, id, label, ...props }) {
  return (
    <div>
      {label ? <Label htmlFor={id}>{label}</Label> : null}
      <input id={id} className={cn(fieldClass, className)} {...props} />
    </div>
  )
}

export function Select({ className, id, label, children, ...props }) {
  return (
    <div>
      {label ? <Label htmlFor={id}>{label}</Label> : null}
      <select id={id} className={cn(fieldClass, className)} {...props}>
        {children}
      </select>
    </div>
  )
}

export function TextArea({ className, id, label, ...props }) {
  return (
    <div>
      {label ? <Label htmlFor={id}>{label}</Label> : null}
      <textarea
        id={id}
        className={cn(fieldClass, 'h-auto min-h-[96px] py-sm', className)}
        {...props}
      />
    </div>
  )
}
