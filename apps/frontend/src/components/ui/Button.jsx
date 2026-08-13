import { Link } from 'react-router-dom'
import { motion, useReducedMotion } from 'framer-motion'
import { cn } from '../../lib/cn'
import { Spinner } from './Spinner'

const variants = {
  primary:
    'bg-primary text-on-primary hover:bg-on-primary-fixed-variant active:bg-on-secondary-fixed-variant focus-visible:ring-primary/40',
  secondary:
    'border border-outline-variant text-on-surface bg-surface-container-lowest hover:bg-surface-container-low focus-visible:ring-primary/30',
  ghost:
    'text-on-surface-variant hover:text-primary hover:bg-surface-container-low focus-visible:ring-primary/20',
  danger:
    'border border-error-container text-on-error-container bg-error-container/40 hover:bg-error-container focus-visible:ring-error/30',
}

const sizes = {
  sm: 'h-9 px-md text-label-md',
  md: 'h-10 px-md text-label-md',
  lg: 'h-12 px-lg text-label-md',
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
  ...props
}) {
  const reduceMotion = useReducedMotion()
  const classes = cn(
    'inline-flex items-center justify-center gap-xs rounded-DEFAULT font-label-md transition-colors',
    'focus-visible:outline-none focus-visible:ring-2 disabled:opacity-60 disabled:pointer-events-none',
    variants[variant],
    sizes[size],
    className,
  )

  const content = (
    <>
      {loading ? <Spinner className="h-4 w-4" /> : null}
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
