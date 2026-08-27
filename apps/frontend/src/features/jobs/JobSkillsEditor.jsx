import { useState } from 'react'
import { Alert } from '../../components/ui/Alert'
import { Button } from '../../components/ui/Button'
import { Input } from '../../components/ui/Input'

function parseYears(raw) {
  if (raw === '' || raw == null) return null
  const parsed = Number(raw)
  if (!Number.isFinite(parsed) || parsed < 0) return null
  return Math.min(50, parsed)
}

function SkillRow({ item, onSkillChange, onYearsChange, onRemove }) {
  return (
    <div className="flex items-start gap-sm py-sm border-b border-outline-variant last:border-b-0">
      <div className="flex-1 min-w-0">
        <Input
          aria-label="Skill name"
          className="h-10"
          value={item.skill}
          onChange={(event) => onSkillChange(event.target.value)}
          placeholder="Skill name"
        />
      </div>
      <div className="w-24 shrink-0">
        <Input
          aria-label={`${item.skill || 'Skill'} years`}
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
      <Button
        type="button"
        variant="ghost"
        size="sm"
        icon="delete"
        className="shrink-0 px-2 text-on-surface-variant hover:text-error"
        aria-label={`Remove ${item.skill || 'skill'}`}
        onClick={onRemove}
      />
    </div>
  )
}

function AddSkillRow({ onAdd }) {
  const [name, setName] = useState('')
  const [years, setYears] = useState('')

  function submit() {
    const trimmed = name.trim()
    if (!trimmed) return
    onAdd({
      skill: trimmed,
      required_years: parseYears(years),
    })
    setName('')
    setYears('')
  }

  return (
    <div className="flex items-start gap-sm pt-sm mt-sm border-t border-dashed border-outline-variant">
      <div className="flex-1 min-w-0">
        <Input
          aria-label="New skill name"
          className="h-10"
          value={name}
          onChange={(event) => setName(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === 'Enter') {
              event.preventDefault()
              submit()
            }
          }}
          placeholder="Add a skill"
        />
      </div>
      <div className="w-24 shrink-0">
        <Input
          aria-label="New skill years"
          type="number"
          min={0}
          max={50}
          step={0.5}
          className="h-10"
          value={years}
          onChange={(event) => setYears(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === 'Enter') {
              event.preventDefault()
              submit()
            }
          }}
          placeholder="Years"
        />
      </div>
      <Button
        type="button"
        variant="secondary"
        size="sm"
        icon="add"
        className="shrink-0"
        disabled={!name.trim()}
        onClick={submit}
      >
        Add
      </Button>
    </div>
  )
}

function normalizeSkillList(items) {
  return (Array.isArray(items) ? items : [])
    .map((item) => ({
      skill: typeof item?.skill === 'string' ? item.skill.trim() : '',
      required_years:
        item?.required_years == null || item?.required_years === ''
          ? null
          : Number(item.required_years),
    }))
    .filter((item) => item.skill)
    .map((item) => ({
      skill: item.skill,
      required_years:
        Number.isFinite(item.required_years) && item.required_years >= 0
          ? Math.min(50, item.required_years)
          : null,
    }))
}

function SkillGroup({ title, items, onChange }) {
  function updateAt(index, patch) {
    onChange(items.map((item, i) => (i === index ? { ...item, ...patch } : item)))
  }

  function removeAt(index) {
    onChange(items.filter((_, i) => i !== index))
  }

  function addSkill(skill) {
    onChange([...items, skill])
  }

  return (
    <div>
      <p className="font-label-md text-label-md text-on-surface mb-sm">{title}</p>
      {items.length === 0 ? (
        <p className="text-body-sm text-on-surface-variant">No skills yet. Add one below.</p>
      ) : (
        <div>
          {items.map((item, index) => (
            <SkillRow
              key={index}
              item={item}
              onSkillChange={(value) => updateAt(index, { skill: value })}
              onYearsChange={(raw) => {
                if (raw === '') {
                  updateAt(index, { required_years: null })
                  return
                }
                const parsed = Number(raw)
                if (!Number.isFinite(parsed) || parsed < 0) return
                updateAt(index, { required_years: Math.min(50, parsed) })
              }}
              onRemove={() => removeAt(index)}
            />
          ))}
        </div>
      )}
      <AddSkillRow onAdd={addSkill} />
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
  function handleSubmit() {
    const next = {
      must_have: normalizeSkillList(skills.must_have),
      good_to_have: normalizeSkillList(skills.good_to_have),
    }
    onChange(next)
    void onSubmit(next)
  }

  return (
    <div className="space-y-lg">
      <p className="text-body-sm text-on-surface-variant">
        Review skills parsed from the description. Edit names, set expected years, remove skills you
        do not need, or add new ones.
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
        <Button onClick={handleSubmit} loading={submitting}>
          {submitting ? 'Saving…' : submitLabel}
        </Button>
      </div>
    </div>
  )
}
