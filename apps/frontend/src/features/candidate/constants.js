export const ORG_NAME = 'Josh Software'

/** Spaces in org name become lowercase hyphens for URL paths (e.g. "Josh Software" → "josh-software"). */
export function orgNameToUrlSlug(name = ORG_NAME) {
  return name.trim().replace(/\s+/g, '-').toLowerCase()
}

export const ORG_URL_SLUG = orgNameToUrlSlug(ORG_NAME)

export const JOB_TYPES = [
  { label: 'All Job Types', value: '' },
  { label: 'Full Time', value: 'full_time' },
  { label: 'Part Time', value: 'part_time' },
]

export const WORK_TYPES = [
  { label: 'All Work Modes', value: '' },
  { label: 'Remote', value: 'remote' },
  { label: 'Hybrid', value: 'hybrid' },
  { label: 'Onsite', value: 'onsite' },
]
