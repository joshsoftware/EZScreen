import { motion, useReducedMotion } from 'framer-motion'

const ease = [0.22, 1, 0.36, 1]

export function useMotionSafe() {
  const reduce = useReducedMotion()
  return !reduce
}

export function FadeIn({
  children,
  className,
  delay = 0,
  y = 12,
  duration = 0.35,
  ...props
}) {
  const animate = useMotionSafe()

  if (!animate) {
    return (
      <div className={className} {...props}>
        {children}
      </div>
    )
  }

  return (
    <motion.div
      className={className}
      initial={{ opacity: 0, y }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration, delay, ease }}
      {...props}
    >
      {children}
    </motion.div>
  )
}

export function PageTransition({ children, className }) {
  const animate = useMotionSafe()

  if (!animate) {
    return <div className={className}>{children}</div>
  }

  return (
    <motion.div
      className={className}
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -6 }}
      transition={{ duration: 0.28, ease }}
    >
      {children}
    </motion.div>
  )
}

const staggerContainer = {
  hidden: {},
  show: {
    transition: {
      staggerChildren: 0.05,
      delayChildren: 0.04,
    },
  },
}

const staggerItem = {
  hidden: { opacity: 0, y: 10 },
  show: {
    opacity: 1,
    y: 0,
    transition: { duration: 0.3, ease },
  },
}

export function Stagger({ children, className, as: Component = 'div' }) {
  const animate = useMotionSafe()
  const MotionComponent = motion[Component] ?? motion.div

  if (!animate) {
    const Tag = Component
    return <Tag className={className}>{children}</Tag>
  }

  return (
    <MotionComponent
      className={className}
      variants={staggerContainer}
      initial="hidden"
      animate="show"
    >
      {children}
    </MotionComponent>
  )
}

export function StaggerItem({ children, className, as: Component = 'div', ...rest }) {
  const animate = useMotionSafe()
  const MotionComponent = motion[Component] ?? motion.div

  if (!animate) {
    const Tag = Component
    return <Tag className={className} {...rest}>{children}</Tag>
  }

  return (
    <MotionComponent className={className} variants={staggerItem} {...rest}>
      {children}
    </MotionComponent>
  )
}

export function FadeSlide({
  children,
  className,
  from = 'left',
  delay = 0,
}) {
  const animate = useMotionSafe()
  const x = from === 'left' ? -24 : from === 'right' ? 24 : 0

  if (!animate) {
    return <div className={className}>{children}</div>
  }

  return (
    <motion.div
      className={className}
      initial={{ opacity: 0, x }}
      animate={{ opacity: 1, x: 0 }}
      transition={{ duration: 0.45, delay, ease }}
    >
      {children}
    </motion.div>
  )
}
