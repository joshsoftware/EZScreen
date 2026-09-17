import { Badge } from '../../../components/ui/Badge'
import { Panel } from '../../../components/ui/PageHeader'

export function CandidateJobSkills({ skills }) {
  const skillsData = skills || {}
  const mustHave = skillsData.must_have || []
  const goodToHave = skillsData.good_to_have || []

  if (mustHave.length === 0 && goodToHave.length === 0) return null

  return (
    <Panel title="Required skills">
      <div className="space-y-md">
        {mustHave.length > 0 ? (
          <div className="space-y-sm">
            <p className="font-label-md text-label-md text-on-surface tracking-wide">
              Must-have
            </p>
            <div className="flex flex-wrap gap-xs">
              {mustHave.map((item, idx) => {
                const name = typeof item === 'string' ? item : item.skill
                const yrs = typeof item === 'object' ? item.required_years : null
                return (
                  <Badge key={`${name}-${idx}`} tone="info">
                    {name}
                    {yrs != null ? ` · ${yrs}+ yrs` : ''}
                  </Badge>
                )
              })}
            </div>
          </div>
        ) : null}

        {goodToHave.length > 0 ? (
          <div className="space-y-sm">
            <p className="font-label-md text-label-md text-on-surface tracking-wide">
              Good to have
            </p>
            <div className="flex flex-wrap gap-xs">
              {goodToHave.map((item, idx) => {
                const name = typeof item === 'string' ? item : item.skill
                return (
                  <Badge key={`${name}-${idx}`} tone="neutral">
                    {name}
                  </Badge>
                )
              })}
            </div>
          </div>
        ) : null}
      </div>
    </Panel>
  )
}
