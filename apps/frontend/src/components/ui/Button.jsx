import { Link } from 'react-router-dom'
import { motion, useReducedMotion } from 'framer-motion'
import { cn } from '../../lib/cn'
import { Spinner } from './Spinner'

const variants = {
  primary:
    'bg-primary text-white shadow-soft hover:bg-on-primary-fixed-variant hover:shadow-lift active:bg-on-secondary-fixed-variant focus-visible:ring-primary/40',
  secondary:
    'border border-primary/40 text-primary bg-surface-container-lowest shadow-soft hover:bg-primary-container/70 hover:border-primary focus-visible:ring-primary/30',
  ghost:
    'text-primary hover:bg-primary-container/60 focus-visible:ring-primary/20',
  danger:
    'border border-error-container text-on-error-container bg-error-container/40 hover:bg-error-container focus-visible:ring-error/30',
}

const sizes = {
  sm: 'h-10 min-h-10 px-4 text-body-sm rounded-xl gap-2',
  md: 'h-11 min-h-11 px-5 text-body-sm rounded-xl gap-2',
  lg: 'h-12 min-h-12 px-6 text-body-md font-medium rounded-xl gap-2.5',
}

const MotionLink = motion.create(Link)

export function Button({
  variant = 'primary',
  size = 'md',
  className,
  loading = false,
  disabled,
  children,
  type = 'button',
  as,
  to,
  icon,
  ...props
}) {
  const reduceMotion = useReducedMotion()
  const classes = cn(
    'inline-flex items-center justify-center font-label-md font-semibold transition-all duration-150 whitespace-nowrap',
    'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-offset-1 focus-visible:ring-offset-surface',
    'disabled:opacity-55 disabled:pointer-events-none',
    '[&_.material-symbols-outlined]:text-[20px] [&_.material-symbols-outlined]:leading-none',
    '[&_.material-symbols-outlined]:shrink-0 [&_.material-symbols-outlined]:text-current',
    sizes[size],
    variants[variant],
    className,
  )

  const content = (
    <>
      {loading ? (
        <Spinner className="h-4 w-4 shrink-0 text-current" />
      ) : icon ? (
        <span className="material-symbols-outlined text-current" aria-hidden>
          {icon}
        </span>
      ) : null}
      {children}
    </>
  )

  const motionProps = reduceMotion
    ? {}
    : {
        whileHover: { y: -1 },
        whileTap: { scale: 0.98 },
        transition: { duration: 0.15 },
      }

  if (as === 'link' || to) {
    return (
      <MotionLink to={to} className={classes} {...motionProps} {...props}>
        {content}
      </MotionLink>
    )
  }

  return (
    <motion.button
      type={type}
      className={classes}
      disabled={disabled || loading}
      {...motionProps}
      {...props}
    >
      {content}
    </motion.button>
  )
}
