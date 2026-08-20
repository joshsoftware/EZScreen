export function LogoMark({ subtitle, compact = false }) {
  return (
    <div className="flex items-center gap-sm">
      <div className="w-8 h-8 rounded-lg bg-primary shadow-soft flex items-center justify-center shrink-0">
        <span className="material-symbols-outlined text-on-primary text-[18px]">
          monitor_heart
        </span>
      </div>
      <div className="min-w-0">
        <span className="font-headline-sm text-[16px] text-primary tracking-tight">
          EZScreen
        </span>
        {subtitle && !compact ? (
          <p className="text-[10px] text-on-surface-variant tracking-wide">{subtitle}</p>
        ) : null}
      </div>
    </div>
  )
}
