import { Alert } from '../../components/ui/Alert'
import { Button } from '../../components/ui/Button'
import { Input } from '../../components/ui/Input'

function SkillYearsRow({ item, onYearsChange }) {
  return (
    <div className="flex items-center gap-md py-sm border-b border-outline-variant last:border-b-0">
      <p className="text-body-sm text-on-surface flex-1 min-w-0">{item.skill}</p>
      <div className="w-28 shrink-0">
        <Input
          aria-label={`${item.skill} years`}
          type="number"
          min={0}
          max={50}
          step={0.5}
          className="h-10"
          value={item.required_years ?? ''}
          onChange={(event) => onYearsChange(event.target.value)}
          placeholder="Years"
        />
      </div>
    </div>
  )
}

function SkillGroup({ title, items, onChange }) {
  function updateYears(index, raw) {
    const next = items.map((item, i) => {
      if (i !== index) return item
      if (raw === '') return { ...item, required_years: null }
      const parsed = Number(raw)
      if (!Number.isFinite(parsed) || parsed < 0) return item
      return { ...item, required_years: Math.min(50, parsed) }
    })
    onChange(next)
  }

  return (
    <div>
      <p className="font-label-md text-label-md text-on-surface mb-sm">{title}</p>
      {items.length === 0 ? (
        <p className="text-body-sm text-on-surface-variant">None extracted from the description.</p>
      ) : (
        <div>
          {items.map((item, index) => (
            <SkillYearsRow
              key={`${item.skill}-${index}`}
              item={item}
              onYearsChange={(value) => updateYears(index, value)}
            />
          ))}
        </div>
      )}
    </div>
  )
}

export function JobSkillsEditor({
  skills,
  onChange,
  onBack,
  onSubmit,
  submitting = false,
  error = null,
  submitLabel = 'Save skills',
}) {
  return (
    <div className="space-y-lg">
      <p className="text-body-sm text-on-surface-variant">
        Review the skills parsed from the description and set the expected years of experience for
        each one.
      </p>
      <SkillGroup
        title={`Must-have (${skills.must_have.length})`}
        items={skills.must_have}
        onChange={(must_have) => onChange({ ...skills, must_have })}
      />
      <SkillGroup
        title={`Nice-to-have (${skills.good_to_have.length})`}
        items={skills.good_to_have}
        onChange={(good_to_have) => onChange({ ...skills, good_to_have })}
      />
      {error ? <Alert>{error}</Alert> : null}
      <div className="flex gap-sm pt-sm">
        {onBack ? (
          <Button variant="secondary" onClick={onBack} disabled={submitting}>
            Back
          </Button>
        ) : null}
        <Button onClick={() => void onSubmit()} loading={submitting}>
          {submitting ? 'Saving…' : submitLabel}
        </Button>
      </div>
    </div>
  )
}
