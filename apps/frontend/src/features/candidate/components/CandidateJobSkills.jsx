export function CandidateJobSkills({ skills }) {
  const skillsData = skills || {}
  const mustHave = skillsData.must_have || []
  const goodToHave = skillsData.good_to_have || []

  if (mustHave.length === 0 && goodToHave.length === 0) return null

  return (
    <div className="rounded-2xl border border-outline-variant/70 bg-surface-container-lowest p-lg md:p-xl shadow-soft">
      <h2 className="text-headline-sm font-semibold text-on-surface mb-md">
        Required Skills
      </h2>

      {mustHave.length > 0 && (
        <div className="mb-lg">
          <h3 className="text-body-sm font-semibold text-on-surface mb-sm">Must Have:</h3>
          <div className="flex flex-wrap gap-xs">
            {mustHave.map((item, idx) => {
              const name = typeof item === 'string' ? item : item.skill
              const yrs = typeof item === 'object' ? item.required_years : null
              return (
                <div
                  key={idx}
                  className="inline-flex items-center gap-xs rounded-xl bg-primary-container/70 border border-primary/20 px-md py-xs text-body-sm font-medium text-on-primary-container"
                >
                  <span>{name}</span>
                  {yrs ? (
                    <span className="rounded-full bg-primary/20 px-xs py-[2px] text-label-md">
                      {yrs}+ yrs
                    </span>
                  ) : null}
                </div>
              )
            })}
          </div>
        </div>
      )}

      {goodToHave.length > 0 && (
        <div>
          <h3 className="text-body-sm font-semibold text-on-surface mb-sm">Good to Have:</h3>
          <div className="flex flex-wrap gap-xs">
            {goodToHave.map((item, idx) => {
              const name = typeof item === 'string' ? item : item.skill
              return (
                <span
                  key={idx}
                  className="rounded-xl bg-surface-container-low border border-outline-variant/60 px-md py-xs text-body-sm font-medium text-on-surface"
                >
                  {name}
                </span>
              )
            })}
          </div>
        </div>
      )}
    </div>
  )
}
