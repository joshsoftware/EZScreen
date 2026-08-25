export const TIMELINE_LADDER = Object.freeze([
  {
    id: 'intake',
    eventTypes: ['scored', 'applied'],
    icon: 'how_to_reg',
    titleForSource(source) {
      return source === 'candidate' ? 'Applied' : 'Scored'
    },
    descriptionForSource(source) {
      return source === 'candidate'
        ? 'Candidate submitted this application'
        : 'Added from HR bulk screening'
    },
  },
  {
    id: 'resume_parsed',
    eventTypes: ['resume_parsed'],
    icon: 'description',
    title: 'Resume parsed',
    description: 'Structured resume data is ready',
  },
  {
    id: 'job_fit',
    eventTypes: ['job_fit'],
    icon: 'analytics',
    title: 'Job fit',
    description: 'Match score and analysis computed',
  },
  {
    id: 'under_hr_review',
    eventTypes: ['under_hr_review'],
    icon: 'rate_review',
    title: 'HR review',
    description: 'Waiting for a screening decision',
  },
  {
    id: 'screening_scheduled',
    eventTypes: ['screening_scheduled'],
    icon: 'event',
    title: 'Screening scheduled',
    description: 'AI screening slot is booked',
  },
  {
    id: 'invite_sent',
    eventTypes: ['invite_sent'],
    icon: 'mail',
    title: 'Invite sent',
    description: 'Candidate received the screening invite',
  },
  {
    id: 'screening_in_progress',
    eventTypes: ['screening_in_progress'],
    icon: 'videocam',
    title: 'Screening in progress',
    description: 'Candidate is in the AI interview',
  },
  {
    id: 'screening_completed',
    eventTypes: ['screening_completed'],
    icon: 'task_alt',
    title: 'Screening completed',
    description: 'Interview session finished',
  },
  {
    id: 'analysis_ready',
    eventTypes: ['analysis_ready'],
    icon: 'psychology',
    title: 'Analysis ready',
    description: 'Screening insights are available',
  },
  {
    id: 'decision',
    eventTypes: ['shortlisted_for_l1', 'rejected'],
    icon: 'flag',
    title: 'Decision',
    description: 'Shortlist or reject after review',
  },
])

const BRANCH_LABELS = {
  screening_rescheduled: 'Rescheduled',
  screening_no_show: 'No-show',
  screening_cancelled: 'Cancelled',
  screening_failed: 'Screening failed',
}

function eventsForStep(events, step) {
  const types = new Set(step.eventTypes)
  return events.filter((event) => types.has(event.event_type))
}

function lastMatching(matching) {
  return matching.length > 0 ? matching[matching.length - 1] : undefined
}

function stepTitle(step, source, matchingEvents) {
  const last = lastMatching(matchingEvents)
  if (step.id === 'intake') return step.titleForSource(source)
  if (step.id === 'decision' && last?.event_type === 'rejected') return 'Rejected'
  if (step.id === 'decision' && last?.event_type === 'shortlisted_for_l1') {
    return 'Shortlisted for L1'
  }
  return step.title
}

export function buildTimelineSteps(events, source) {
  const list = Array.isArray(events) ? events : []
  const rejectedAt = list.findIndex((event) => event.event_type === 'rejected')
  const terminal = rejectedAt >= 0 || list.some((e) => e.event_type === 'shortlisted_for_l1')

  let foundCurrent = false
  const steps = TIMELINE_LADDER.map((step) => {
    const matching = eventsForStep(list, step)
    const done = matching.length > 0
    const last = lastMatching(matching)
    let state = 'upcoming'
    if (done) {
      state = last?.event_type === 'rejected' ? 'rejected' : 'done'
    } else if (terminal) {
      state = 'skipped'
    } else if (!foundCurrent) {
      state = 'current'
      foundCurrent = true
    }

    return {
      id: step.id,
      icon: step.icon,
      title: stepTitle(step, source, matching),
      description:
        step.id === 'intake' ? step.descriptionForSource(source) : step.description,
      state,
      at: last?.created_at ?? null,
      extraCount: Math.max(matching.length - 1, 0),
      rerun: Boolean(last?.metadata?.rerun),
    }
  })

  const branches = list
    .filter((event) => BRANCH_LABELS[event.event_type])
    .map((event) => ({
      id: event.id,
      title: BRANCH_LABELS[event.event_type],
      at: event.created_at,
    }))

  return { steps, branches }
}
