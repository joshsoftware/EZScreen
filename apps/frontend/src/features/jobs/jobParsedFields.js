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

export function emptyJobSkills() {
  return { must_have: [], good_to_have: [] }
}

export function normalizeJobSkills(source) {
  const skills = source?.skills && typeof source.skills === 'object' ? source.skills : source
  const { mustHave, goodToHave } = jdSkillLists(
    skills?.must_have || skills?.good_to_have ? { skills } : source,
  )
  return {
    must_have: mustHave.map((item) => ({
      skill: item.skill,
      required_years: item.years ?? null,
    })),
    good_to_have: goodToHave.map((item) => ({
      skill: item.skill,
      required_years: item.years ?? null,
    })),
  }
}

export function skillsFromJob(job) {
  if (job?.skills && typeof job.skills === 'object') {
    return normalizeJobSkills(job.skills)
  }
  return normalizeJobSkills(job?.parsed_jd)
}

function skillKey(name) {
  return String(name || '').trim().toLowerCase()
}

function parsedSkillKeys(parsedJd) {
  if (!parsedJd) return new Set()
  const norm = normalizeJobSkills(parsedJd)
  return new Set(
    [...norm.must_have, ...norm.good_to_have]
      .map((item) => skillKey(item.skill))
      .filter(Boolean),
  )
}

function syncSkillList(currentList, newList, previousParsedKeys, newParsedKeys) {
  const result = []
  const seen = new Set()
  const newByKey = new Map(
    newList
      .map((item) => [skillKey(item.skill), item])
      .filter(([key]) => Boolean(key)),
  )

  for (const item of currentList) {
    const key = skillKey(item.skill)
    if (!key) continue
    const wasFromParse = previousParsedKeys.has(key)
    if (wasFromParse && !newParsedKeys.has(key)) continue
    const fromNew = newByKey.get(key)
    if (fromNew?.required_years != null) {
      result.push({ ...item, required_years: fromNew.required_years })
    } else {
      result.push(item)
    }
    seen.add(key)
  }

  for (const item of newList) {
    const key = skillKey(item.skill)
    if (!key || seen.has(key)) continue
    result.push({ ...item })
    seen.add(key)
  }

  return result
}

/** Same skill must not appear in both buckets; must-have wins. */
function dedupePreferMustHave(mustHave, goodToHave) {
  const mustKeys = new Set(
    mustHave.map((item) => skillKey(item.skill)).filter(Boolean),
  )
  return {
    must_have: mustHave,
    good_to_have: goodToHave.filter((item) => !mustKeys.has(skillKey(item.skill))),
  }
}

/**
 * After JD re-parse: drop parse-sourced skills no longer in the JD,
 * keep manually added skills, append newly parsed skills,
 * merge years from parse, and avoid duplicates across buckets.
 */
export function syncSkillsAfterReparse(current, previousParsedJd, newParsedJd) {
  const currentNorm = normalizeJobSkills(current)
  const newNorm = normalizeJobSkills(newParsedJd)
  const prevKeys = parsedSkillKeys(previousParsedJd)
  const newKeys = parsedSkillKeys(newParsedJd)

  return dedupePreferMustHave(
    syncSkillList(
      currentNorm.must_have,
      newNorm.must_have,
      prevKeys,
      newKeys,
    ),
    syncSkillList(
      currentNorm.good_to_have,
      newNorm.good_to_have,
      prevKeys,
      newKeys,
    ),
  )
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
