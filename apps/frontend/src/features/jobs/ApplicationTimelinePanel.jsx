import { Button } from '../../components/ui/Button'
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

function StepDetails({ step }) {
  const when = step.scheduledAt || step.at
  return (
    <>
      {when ? (
        <p className="text-label-md text-on-surface-variant mt-xs">
          {formatDateTime(when)}
          {step.durationMinutes ? ` · ${step.durationMinutes} min` : ''}
          {step.rerun ? ' · Rerun' : ''}
          {step.extraCount > 0 ? ` · ${step.extraCount} earlier` : ''}
        </p>
      ) : step.rerun || step.extraCount > 0 ? (
        <p className="text-label-md text-on-surface-variant mt-xs">
          {[step.rerun ? 'Rerun' : null, step.extraCount > 0 ? `${step.extraCount} earlier` : null]
            .filter(Boolean)
            .join(' · ')}
        </p>
      ) : null}
      {step.gmeetLink ? (
        <a
          href={step.gmeetLink}
          target="_blank"
          rel="noopener noreferrer"
          className="inline-flex items-center gap-xs text-label-md text-primary hover:underline mt-xs break-all"
        >
          <span className="material-symbols-outlined text-[16px]">videocam</span>
          Join Meet
        </a>
      ) : null}
      {Array.isArray(step.attendees) && step.attendees.length > 0 ? (
        <p className="text-label-md text-on-surface-variant mt-xs break-all">
          Guests · {step.attendees.join(', ')}
        </p>
      ) : null}
    </>
  )
}

export function ApplicationTimelinePanel({
  events,
  source,
  loading,
  error,
  scheduleAction = null,
  rescheduleAction = null,
}) {
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
          const showScheduleCta =
            step.state === 'current' &&
            step.actionId === 'screening_scheduled' &&
            scheduleAction?.visible
          const showRescheduleCta =
            step.actionId === 'screening_scheduled' &&
            step.state === 'done' &&
            rescheduleAction?.visible

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
              <div className={cn('min-w-0 flex-1', isLast ? 'pb-0' : 'pb-md')}>
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
                <StepDetails step={step} />
                {step.state === 'current' ? (
                  <p className="text-label-md text-primary mt-xs">Up next</p>
                ) : null}
                {showScheduleCta ? (
                  <div className="mt-sm">
                    <Button
                      size="sm"
                      icon="event"
                      className="whitespace-nowrap"
                      disabled={scheduleAction.disabled}
                      onClick={scheduleAction.onClick}
                    >
                      Schedule screening
                    </Button>
                  </div>
                ) : null}
                {showRescheduleCta ? (
                  <div className="mt-sm">
                    <Button
                      size="sm"
                      variant="secondary"
                      icon="event_repeat"
                      className="whitespace-nowrap"
                      disabled={rescheduleAction.disabled}
                      onClick={rescheduleAction.onClick}
                    >
                      Reschedule
                    </Button>
                  </div>
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
