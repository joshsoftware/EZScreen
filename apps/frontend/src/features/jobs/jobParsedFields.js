function normalizeString(value) {
  if (typeof value === 'string') {
    const trimmed = value.trim()
    return trimmed || null
  }
  if (value && typeof value === 'object' && typeof value.skill === 'string') {
    const trimmed = value.skill.trim()
    return trimmed || null
  }
  return null
}

function normalizeSkillItem(value) {
  if (typeof value === 'string') {
    const trimmed = value.trim()
    return trimmed ? { skill: trimmed } : null
  }
  if (value && typeof value === 'object' && typeof value.skill === 'string') {
    const trimmed = value.skill.trim()
    return trimmed ? { skill: trimmed, years: value.required_years ?? null } : null
  }
  return null
}

export function jdSkillLists(parsedJd) {
  const skills = parsedJd?.skills
  const mustHaveRaw = Array.isArray(skills?.must_have)
    ? skills.must_have
    : []
  const goodToHaveRaw = Array.isArray(skills?.good_to_have)
    ? skills.good_to_have
    : []

  return {
    mustHave: mustHaveRaw.map(normalizeSkillItem).filter(Boolean),
    goodToHave: goodToHaveRaw.map(normalizeSkillItem).filter(Boolean),
  }
}

export function jdStringList(parsedJd, key) {
  const items = parsedJd?.[key]
  return Array.isArray(items) ? items.map(normalizeString).filter(Boolean) : []
}

export function jdExperienceRange(parsedJd) {
  const exp = parsedJd?.experience_required
  if (!exp || typeof exp !== 'object') return null
  const min = exp.min_years
  const max = exp.max_years
  if (min == null && max == null) return null
  if (min != null && max != null) return `${min}–${max} years`
  if (min != null) return `${min}+ years`
  return `Up to ${max} years`
}

export function jdStatCards(parsedJd) {
  if (!parsedJd || typeof parsedJd !== 'object') return []
  const { mustHave, goodToHave } = jdSkillLists(parsedJd)
  const qualifications = jdStringList(parsedJd, 'qualifications')
  const responsibilities = jdStringList(parsedJd, 'responsibilities')

  return [
    { label: 'Must-have skills', value: String(mustHave.length) },
    { label: 'Nice-to-have', value: String(goodToHave.length) },
    { label: 'Qualifications', value: String(qualifications.length) },
    { label: 'Responsibilities', value: String(responsibilities.length) },
  ]
}

export function jdHasContent(parsedJd) {
  if (!parsedJd || typeof parsedJd !== 'object') return false
  const { mustHave, goodToHave } = jdSkillLists(parsedJd)
  return Boolean(
    parsedJd.title ||
      parsedJd.company ||
      parsedJd.location ||
      parsedJd.employment_type ||
      parsedJd.company_description ||
      mustHave.length ||
      goodToHave.length ||
      jdStringList(parsedJd, 'qualifications').length ||
      jdStringList(parsedJd, 'responsibilities').length ||
      jdExperienceRange(parsedJd),
  )
}
