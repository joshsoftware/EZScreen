const STORAGE_PREFIX = 'resume-queue:'

export function resumeQueueStorageKey(jobId) {
  return `${STORAGE_PREFIX}${jobId}`
}

function parseStoredWatch(raw, timeoutMs = 120000) {
  const parsed = JSON.parse(raw)
  const targetScreened = Number(parsed?.targetScreened)
  const startedAt = Number(parsed?.startedAt)
  const batchId =
    typeof parsed?.batchId === 'string' && parsed.batchId.trim()
      ? parsed.batchId.trim()
      : null
  if (!Number.isFinite(targetScreened) || !Number.isFinite(startedAt)) {
    return null
  }
  if (Date.now() - startedAt >= timeoutMs) {
    return null
  }
  return { targetScreened, startedAt, batchId }
}

/** Read queue watch without mutating sessionStorage (safe during render). */
export function peekResumeQueueWatch(jobId, timeoutMs = 120000) {
  if (!jobId) return null
  try {
    const raw = sessionStorage.getItem(resumeQueueStorageKey(jobId))
    if (!raw) return null
    return parseStoredWatch(raw, timeoutMs)
  } catch {
    return null
  }
}

/** @returns {{ targetScreened: number, startedAt: number, batchId?: string|null } | null} */
export function loadResumeQueueWatch(jobId, screenedCount = null, timeoutMs = 120000) {
  if (!jobId) return null
  try {
    const raw = sessionStorage.getItem(resumeQueueStorageKey(jobId))
    if (!raw) return null

    const watch = parseStoredWatch(raw, timeoutMs)
    if (!watch) {
      sessionStorage.removeItem(resumeQueueStorageKey(jobId))
      return null
    }

    if (screenedCount != null && watch.targetScreened <= screenedCount) {
      sessionStorage.removeItem(resumeQueueStorageKey(jobId))
      return null
    }

    return watch
  } catch {
    sessionStorage.removeItem(resumeQueueStorageKey(jobId))
    return null
  }
}

export function saveResumeQueueWatch(jobId, watch) {
  if (!jobId || !watch) return
  try {
    sessionStorage.setItem(
      resumeQueueStorageKey(jobId),
      JSON.stringify({
        targetScreened: watch.targetScreened,
        startedAt: watch.startedAt,
        batchId: watch.batchId || null,
      }),
    )
  } catch {
    // Private browsing or quota exceeded — in-memory watch still works.
  }
}

export function clearResumeQueueWatch(jobId) {
  if (!jobId) return
  try {
    sessionStorage.removeItem(resumeQueueStorageKey(jobId))
  } catch {
    // ignore
  }
}
