export const queryKeys = {
  organization: (organizationId) => ['organization', organizationId],
  job: (jobId) => ['job', jobId],
  publicJobs: (params = {}) => ['publicJobs', params],
  publicJob: (jobId, orgName) => ['publicJob', jobId, orgName],
  jobApplicants: (jobId) => ['job', jobId, 'applicants'],
  application: (applicationId) => ['application', applicationId],
  applicationTimeline: (applicationId) => ['application', applicationId, 'timeline'],
  interviewSession: (sessionId) => ['interview-session', sessionId],
  interviewAnalysis: (sessionId) => ['interview-analysis', sessionId],
}

