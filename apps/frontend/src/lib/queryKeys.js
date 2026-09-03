export const queryKeys = {
  organization: (organizationId) => ['organization', organizationId],
  job: (jobId) => ['job', jobId],
  publicJobs: (params = {}) => ['publicJobs', params],
  publicJob: (jobId) => ['publicJob', jobId],
  jobApplicants: (jobId, params = {}) => [
    'job',
    jobId,
    'applicants',
    params.page ?? 1,
    params.limit ?? 50,
  ],
  application: (applicationId) => ['application', applicationId],
  applicationTimeline: (applicationId) => ['application', applicationId, 'timeline'],
}

