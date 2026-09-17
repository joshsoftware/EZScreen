import { Button } from '../../../components/ui/Button'
import { Panel } from '../../../components/ui/PageHeader'
import {
  formatExperience,
  formatJobType,
  formatWorkType,
} from '../../jobs/jobFields'

function SummaryRow({ label, value }) {
  return (
    <div className="flex items-baseline justify-between gap-sm border-b border-outline-variant/50 py-sm last:border-b-0">
      <span className="text-label-md text-on-surface-variant">{label}</span>
      <span className="text-body-sm font-medium text-on-surface text-right">{value}</span>
    </div>
  )
}

export function CandidateJobSummarySidebar({ job, onApply }) {
  return (
    <div className="lg:sticky lg:top-20 self-start">
      <Panel title="Job summary">
        <div className="space-y-xs">
          <SummaryRow label="Company" value={job.organization_name || '—'} />
          <SummaryRow label="Location" value={job.location || 'Flexible'} />
          <SummaryRow label="Work mode" value={formatWorkType(job.work_type)} />
          <SummaryRow label="Job type" value={formatJobType(job.job_type)} />
          <SummaryRow
            label="Experience"
            value={formatExperience(job.experience_min, job.experience_max)}
          />
          <SummaryRow
            label="Posted"
            value={
              job.published_at
                ? new Date(job.published_at).toLocaleDateString()
                : 'Recently'
            }
          />
        </div>
        <div className="pt-md">
          <Button type="button" className="w-full" icon="send" onClick={onApply}>
            Apply for this role
          </Button>
        </div>
      </Panel>
    </div>
  )
}
