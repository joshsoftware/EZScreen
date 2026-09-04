import { useState } from 'react'
import {
  usePublicUploadUrlsMutation,
  useSubmitCandidateApplicationMutation,
} from '../usePublicJobs'

export function CandidateApplyModal({ job, onClose }) {
  const [formData, setFormData] = useState({
    firstName: '',
    lastName: '',
    email: '',
    phone: '',
  })
  const [selectedFile, setSelectedFile] = useState(null)
  const [dragActive, setDragActive] = useState(false)
  const [step, setStep] = useState('idle') // 'idle' | 'uploading' | 'submitting' | 'success'
  const [errorMessage, setErrorMessage] = useState('')
  const [submittedApplication, setSubmittedApplication] = useState(null)

  const uploadUrlsMutation = usePublicUploadUrlsMutation()
  const submitApplicationMutation = useSubmitCandidateApplicationMutation()

  const handleInputChange = (e) => {
    const { name, value } = e.target
    setFormData((prev) => ({ ...prev, [name]: value }))
  }

  const validateAndSetFile = (file) => {
    setErrorMessage('')
    if (!file) return

    const allowedTypes = [
      'application/pdf',
      'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    ]
    const ext = file.name.split('.').pop()?.toLowerCase()
    const isValidType =
      allowedTypes.includes(file.type) || ['pdf', 'docx'].includes(ext)

    if (!isValidType) {
      setErrorMessage('Please upload a valid PDF or DOCX resume document.')
      return
    }
    if (file.size > 10 * 1024 * 1024) {
      setErrorMessage('File size exceeds 10MB limit. Please select a smaller file.')
      return
    }
    setSelectedFile(file)
  }

  const handleFileChange = (e) => {
    const file = e.target.files?.[0]
    validateAndSetFile(file)
  }

  const handleDrag = (e) => {
    e.preventDefault()
    e.stopPropagation()
    if (e.type === 'dragenter' || e.type === 'dragover') {
      setDragActive(true)
    } else if (e.type === 'dragleave') {
      setDragActive(false)
    }
  }

  const handleDrop = (e) => {
    e.preventDefault()
    e.stopPropagation()
    setDragActive(false)
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      validateAndSetFile(e.dataTransfer.files[0])
    }
  }

  const handleSubmit = async (e) => {
    e.preventDefault()
    setErrorMessage('')

    if (!formData.firstName.trim() || !formData.lastName.trim()) {
      setErrorMessage('Please provide your full name.')
      return
    }
    if (!formData.email.trim() || !formData.email.includes('@')) {
      setErrorMessage('Please enter a valid email address.')
      return
    }
    if (!selectedFile) {
      setErrorMessage('Please attach your resume document.')
      return
    }

    try {
      setStep('uploading')

      const ext = selectedFile.name.split('.').pop()?.toLowerCase()
      const contentType =
        selectedFile.type ||
        (ext === 'docx'
          ? 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
          : 'application/pdf')

      // 1. Request presigned upload URL
      const uploadRes = await uploadUrlsMutation.mutateAsync({
        jobId: job.id,
        files: [{ file_name: selectedFile.name, content_type: contentType }],
      })

      const uploadItem = uploadRes?.uploads?.[0]
      if (!uploadItem?.upload_url || !uploadItem?.s3_key) {
        throw new Error('Failed to obtain pre-signed upload URL for resume.')
      }

      // 2. Upload resume directly to object storage via PUT
      const uploadResult = await fetch(uploadItem.upload_url, {
        method: 'PUT',
        headers: { 'Content-Type': contentType },
        body: selectedFile,
      })

      if (!uploadResult.ok) {
        throw new Error(`Failed to upload resume to storage (${uploadResult.status})`)
      }

      setStep('submitting')

      // 3. Register application
      const res = await submitApplicationMutation.mutateAsync({
        jobId: job.id,
        payload: {
          first_name: formData.firstName.trim(),
          last_name: formData.lastName.trim(),
          email: formData.email.trim(),
          phone: formData.phone.trim() || null,
          s3_key: uploadItem.s3_key,
        },
      })

      setSubmittedApplication(res)
      setStep('success')
    } catch (err) {
      setStep('idle')
      setErrorMessage(err?.message || 'Failed to submit application. Please try again.')
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-inverse-surface/40 backdrop-blur-md p-margin-mobile overflow-y-auto">
      <div className="w-full max-w-xl rounded-3xl border border-outline-variant/80 bg-surface-container-lowest p-lg md:p-xl shadow-2xl transition-all my-auto">
        {/* Modal Header */}
        <div className="flex items-center justify-between border-b border-outline-variant/60 pb-md mb-lg">
          <div>
            <span className="text-label-md font-semibold text-primary uppercase tracking-wider">
              Candidate Application
            </span>
            <h3 className="text-headline-sm font-bold text-on-surface">
              {job.title}
            </h3>
          </div>
          <button
            type="button"
            onClick={onClose}
            disabled={step === 'uploading' || step === 'submitting'}
            className="rounded-full p-xs text-on-surface-variant hover:bg-surface-container-high transition-colors disabled:opacity-50"
          >
            <span className="material-symbols-outlined text-[24px]">close</span>
          </button>
        </div>

        {/* Success View */}
        {step === 'success' ? (
          <div className="py-lg text-center space-y-md">
            <div className="mx-auto w-16 h-16 rounded-full bg-emerald-500/10 border border-emerald-500/30 text-emerald-600 flex items-center justify-center">
              <span className="material-symbols-outlined text-[36px]">check_circle</span>
            </div>
            <h4 className="text-headline-md font-bold text-on-surface">
              Application Submitted!
            </h4>
            <p className="text-body-md text-on-surface-variant max-w-md mx-auto">
              Thank you, <strong>{formData.firstName}</strong>. Your application for{' '}
              <strong>{job.title}</strong> at <strong>{job.organization_name || 'EZScreen Partner'}</strong> has been successfully received.
            </p>
            {submittedApplication?.id && (
              <div className="inline-block rounded-xl bg-surface-container-low border border-outline-variant/60 px-md py-xs text-body-xs font-mono text-on-surface-variant">
                Application Ref: {submittedApplication.id}
              </div>
            )}
            <div className="pt-md">
              <button
                type="button"
                onClick={onClose}
                className="w-full rounded-xl bg-primary px-lg py-sm text-body-md font-semibold text-on-primary shadow-soft hover:bg-primary/90 transition-colors"
              >
                Done
              </button>
            </div>
          </div>
        ) : (
          /* Form View */
          <form onSubmit={handleSubmit} className="space-y-md">
            {errorMessage && (
              <div className="rounded-xl border border-error/40 bg-error-container/30 p-sm text-body-sm font-medium text-error flex items-start gap-xs">
                <span className="material-symbols-outlined text-[20px] shrink-0 mt-[2px]">error</span>
                <span>{errorMessage}</span>
              </div>
            )}

            {/* Personal Details */}
            <div className="grid gap-md sm:grid-cols-2">
              <div>
                <label className="block text-body-xs font-semibold text-on-surface-variant mb-xs">
                  First Name <span className="text-error">*</span>
                </label>
                <input
                  type="text"
                  name="firstName"
                  value={formData.firstName}
                  onChange={handleInputChange}
                  placeholder="e.g. John"
                  disabled={step !== 'idle'}
                  className="w-full rounded-xl border border-outline-variant bg-surface px-md py-xs text-body-sm text-on-surface focus:border-primary focus:outline-none transition-colors"
                  required
                />
              </div>

              <div>
                <label className="block text-body-xs font-semibold text-on-surface-variant mb-xs">
                  Last Name <span className="text-error">*</span>
                </label>
                <input
                  type="text"
                  name="lastName"
                  value={formData.lastName}
                  onChange={handleInputChange}
                  placeholder="e.g. Doe"
                  disabled={step !== 'idle'}
                  className="w-full rounded-xl border border-outline-variant bg-surface px-md py-xs text-body-sm text-on-surface focus:border-primary focus:outline-none transition-colors"
                  required
                />
              </div>
            </div>

            <div>
              <label className="block text-body-xs font-semibold text-on-surface-variant mb-xs">
                Email Address <span className="text-error">*</span>
              </label>
              <input
                type="email"
                name="email"
                value={formData.email}
                onChange={handleInputChange}
                placeholder="john.doe@example.com"
                disabled={step !== 'idle'}
                className="w-full rounded-xl border border-outline-variant bg-surface px-md py-xs text-body-sm text-on-surface focus:border-primary focus:outline-none transition-colors"
                required
              />
            </div>

            <div>
              <label className="block text-body-xs font-semibold text-on-surface-variant mb-xs">
                Phone Number <span className="text-on-surface-variant/60 font-normal">(Optional)</span>
              </label>
              <input
                type="tel"
                name="phone"
                value={formData.phone}
                onChange={handleInputChange}
                placeholder="+1 (555) 000-0000"
                disabled={step !== 'idle'}
                className="w-full rounded-xl border border-outline-variant bg-surface px-md py-xs text-body-sm text-on-surface focus:border-primary focus:outline-none transition-colors"
              />
            </div>

            {/* Resume File Upload Dropzone */}
            <div>
              <label className="block text-body-xs font-semibold text-on-surface-variant mb-xs">
                Resume Document <span className="text-error">*</span>
              </label>
              <div
                onDragEnter={handleDrag}
                onDragLeave={handleDrag}
                onDragOver={handleDrag}
                onDrop={handleDrop}
                className={`relative rounded-2xl border-2 border-dashed p-lg text-center transition-all ${
                  dragActive
                    ? 'border-primary bg-primary-container/20'
                    : selectedFile
                    ? 'border-emerald-500/50 bg-emerald-500/5'
                    : 'border-outline-variant/80 bg-surface-container-low hover:border-primary/50'
                }`}
              >
                <input
                  type="file"
                  accept=".pdf,.docx,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                  onChange={handleFileChange}
                  disabled={step !== 'idle'}
                  className="absolute inset-0 cursor-pointer opacity-0"
                />

                {selectedFile ? (
                  <div className="flex items-center justify-between gap-sm text-left">
                    <div className="flex items-center gap-sm overflow-hidden">
                      <div className="w-10 h-10 rounded-xl bg-primary-container text-on-primary-container flex items-center justify-center shrink-0">
                        <span className="material-symbols-outlined text-[22px]">description</span>
                      </div>
                      <div className="truncate">
                        <p className="text-body-sm font-semibold text-on-surface truncate">
                          {selectedFile.name}
                        </p>
                        <p className="text-label-md text-on-surface-variant">
                          {(selectedFile.size / (1024 * 1024)).toFixed(2)} MB
                        </p>
                      </div>
                    </div>
                    {step === 'idle' && (
                      <button
                        type="button"
                        onClick={(e) => {
                          e.stopPropagation()
                          setSelectedFile(null)
                        }}
                        className="rounded-lg p-xs text-on-surface-variant hover:bg-error-container/20 hover:text-error transition-colors shrink-0"
                      >
                        <span className="material-symbols-outlined text-[20px]">delete</span>
                      </button>
                    )}
                  </div>
                ) : (
                  <div className="space-y-xs">
                    <div className="mx-auto w-10 h-10 rounded-full bg-surface-container-high text-primary flex items-center justify-center">
                      <span className="material-symbols-outlined text-[24px]">cloud_upload</span>
                    </div>
                    <p className="text-body-sm font-medium text-on-surface">
                      Drag & drop your resume or <span className="text-primary underline">browse</span>
                    </p>
                    <p className="text-label-md text-on-surface-variant">
                      Supports PDF or DOCX format (Max 10MB)
                    </p>
                  </div>
                )}
              </div>
            </div>

            {/* Modal Actions */}
            <div className="flex items-center justify-end gap-sm pt-md border-t border-outline-variant/60">
              <button
                type="button"
                onClick={onClose}
                disabled={step !== 'idle'}
                className="rounded-xl bg-surface-container-high px-lg py-sm text-body-sm font-medium text-on-surface hover:bg-outline-variant transition-colors disabled:opacity-50"
              >
                Cancel
              </button>
              <button
                type="submit"
                disabled={step !== 'idle' || !selectedFile}
                className="inline-flex items-center gap-xs rounded-xl bg-primary px-xl py-sm text-body-sm font-semibold text-on-primary shadow-soft hover:bg-primary/90 transition-colors disabled:opacity-50"
              >
                {step === 'uploading' && (
                  <>
                    <span className="w-4 h-4 rounded-full border-2 border-on-primary border-t-transparent animate-spin" />
                    <span>Uploading Resume...</span>
                  </>
                )}
                {step === 'submitting' && (
                  <>
                    <span className="w-4 h-4 rounded-full border-2 border-on-primary border-t-transparent animate-spin" />
                    <span>Submitting Application...</span>
                  </>
                )}
                {step === 'idle' && <span>Submit Application</span>}
              </button>
            </div>
          </form>
        )}
      </div>
    </div>
  )
}
