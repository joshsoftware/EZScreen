import { Alert } from '../../components/ui/Alert'
import { Panel } from '../../components/ui/PageHeader'
import { Skeleton } from '../../components/ui/Skeleton'
import { cn } from '../../lib/cn'
import { buildTimelineSteps } from './applicationTimeline'
import { formatDateTime } from './jobFields'

function StepMarker({ state, icon }) {
  const styles = {
    done: 'bg-success-container text-on-success-container',
    current: 'bg-primary-container text-on-primary-container ring-2 ring-primary/30',
    rejected: 'bg-error-container text-on-error-container',
    skipped: 'bg-surface-container-high text-on-surface-variant/50',
    upcoming: 'bg-surface-container-high text-on-surface-variant',
  }

  return (
    <span
      className={cn(
        'mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-full',
        styles[state] ?? styles.upcoming,
      )}
    >
      <span className="material-symbols-outlined text-[18px]">{icon}</span>
    </span>
  )
}

export function ApplicationTimelinePanel({ events, source, loading, error }) {
  if (loading) {
    return (
      <Panel title="Screening progress">
        <div className="space-y-md">
          <Skeleton className="h-12 rounded-lg" />
          <Skeleton className="h-12 rounded-lg" />
          <Skeleton className="h-12 rounded-lg" />
        </div>
      </Panel>
    )
  }

  if (error) {
    return (
      <Panel title="Screening progress">
        <Alert>{error}</Alert>
      </Panel>
    )
  }

  const { steps, branches } = buildTimelineSteps(events, source)
  const activeSteps = steps.filter(
    (step) => step.state === 'done' || step.state === 'current' || step.state === 'rejected',
  )
  const laterSteps = steps.filter(
    (step) => step.state === 'upcoming' || step.state === 'skipped',
  )

  return (
    <Panel title="Screening progress">
      <ol className="space-y-0">
        {activeSteps.map((step, index) => {
          const isLast = index === activeSteps.length - 1
          const lineDone = step.state === 'done'
          return (
            <li key={step.id} className="flex gap-md">
              <div className="flex flex-col items-center">
                <StepMarker state={step.state} icon={step.icon} />
                {isLast ? null : (
                  <span
                    className={cn(
                      'w-px flex-1 min-h-[16px] my-xs',
                      lineDone ? 'bg-success/40' : 'bg-outline-variant',
                    )}
                  />
                )}
              </div>
              <div className={cn('min-w-0', isLast ? 'pb-0' : 'pb-md')}>
                <p
                  className={cn(
                    'text-body-sm font-medium',
                    step.state === 'upcoming' || step.state === 'skipped'
                      ? 'text-on-surface-variant'
                      : 'text-on-surface',
                  )}
                >
                  {step.title}
                </p>
                <p className="text-label-md text-on-surface-variant">{step.description}</p>
                {step.at ? (
                  <p className="text-label-md text-on-surface-variant mt-xs">
                    {formatDateTime(step.at)}
                    {step.rerun ? ' · Rerun' : ''}
                    {step.extraCount > 0 ? ` · ${step.extraCount} earlier` : ''}
                  </p>
                ) : null}
                {step.state === 'current' ? (
                  <p className="text-label-md text-primary mt-xs">Up next</p>
                ) : null}
              </div>
            </li>
          )
        })}
      </ol>
      {laterSteps.length > 0 ? (
        <p className="text-label-md text-on-surface-variant mt-sm pt-sm border-t border-outline-variant leading-relaxed">
          Then: {laterSteps.map((step) => step.title).join(' → ')}
        </p>
      ) : null}
      {branches.length > 0 ? (
        <div className="mt-md pt-md border-t border-outline-variant space-y-xs">
          {branches.map((branch) => (
            <p key={branch.id} className="text-label-md text-on-surface-variant">
              {branch.title}
              {branch.at ? ` · ${formatDateTime(branch.at)}` : ''}
            </p>
          ))}
        </div>
      ) : null}
    </Panel>
  )
}
