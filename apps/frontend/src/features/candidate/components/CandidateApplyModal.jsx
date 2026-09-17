import { useState } from 'react'
import { useParams } from 'react-router-dom'
import {
  usePublicUploadUrlsMutation,
  useSubmitCandidateApplicationMutation,
} from '../usePublicJobs'
import { ORG_URL_SLUG } from '../constants'
import { Alert } from '../../../components/ui/Alert'
import { Button } from '../../../components/ui/Button'
import { Input } from '../../../components/ui/Input'
import { Modal } from '../../../components/ui/Modal'
import { cn } from '../../../lib/cn'

export function CandidateApplyModal({ job, onClose, open = true }) {
  const { org = ORG_URL_SLUG } = useParams()
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

  const busy = step === 'uploading' || step === 'submitting'

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
    validateAndSetFile(e.target.files?.[0])
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
    if (e.dataTransfer.files?.[0]) {
      validateAndSetFile(e.dataTransfer.files[0])
    }
  }

  const handleClose = () => {
    if (busy) return
    onClose?.()
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

      const uploadRes = await uploadUrlsMutation.mutateAsync({
        jobId: job.id,
        files: [{ file_name: selectedFile.name, content_type: contentType }],
      })

      const uploadItem = uploadRes?.uploads?.[0]
      if (!uploadItem?.upload_url || !uploadItem?.s3_key) {
        throw new Error('Failed to obtain pre-signed upload URL for resume.')
      }

      const uploadResult = await fetch(uploadItem.upload_url, {
        method: 'PUT',
        headers: { 'Content-Type': contentType },
        body: selectedFile,
      })

      if (!uploadResult.ok) {
        throw new Error(`Failed to upload resume to storage (${uploadResult.status})`)
      }

      setStep('submitting')

      const res = await submitApplicationMutation.mutateAsync({
        jobId: job.id,
        orgName: org,
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
    <Modal
      open={open}
      onClose={handleClose}
      title={step === 'success' ? 'Application submitted' : `Apply · ${job.title || 'Role'}`}
    >
      {step === 'success' ? (
        <div className="space-y-md">
          <Alert tone="success">
            Thank you, {formData.firstName}. Your application for {job.title} has been received.
          </Alert>
          {submittedApplication?.id ? (
            <p className="text-label-md text-on-surface-variant font-mono">
              Application ref · {submittedApplication.id}
            </p>
          ) : null}
          <div className="flex justify-end">
            <Button type="button" onClick={handleClose}>
              Done
            </Button>
          </div>
        </div>
      ) : (
        <form onSubmit={handleSubmit} className="space-y-md">
          {errorMessage ? <Alert>{errorMessage}</Alert> : null}

          <div className="grid gap-md sm:grid-cols-2">
            <Input
              id="apply-first-name"
              label="First name"
              name="firstName"
              value={formData.firstName}
              onChange={handleInputChange}
              placeholder="First name"
              disabled={busy}
              required
            />
            <Input
              id="apply-last-name"
              label="Last name"
              name="lastName"
              value={formData.lastName}
              onChange={handleInputChange}
              placeholder="Last name"
              disabled={busy}
              required
            />
          </div>

          <Input
            id="apply-email"
            label="Email"
            type="email"
            name="email"
            value={formData.email}
            onChange={handleInputChange}
            placeholder="you@example.com"
            disabled={busy}
            required
          />

          <Input
            id="apply-phone"
            label="Phone (optional)"
            type="tel"
            name="phone"
            value={formData.phone}
            onChange={handleInputChange}
            placeholder="+91 …"
            disabled={busy}
          />

          <div>
            <p className="font-label-md text-label-md text-on-surface mb-xs">
              Resume <span className="text-error">*</span>
            </p>
            <div
              onDragEnter={handleDrag}
              onDragLeave={handleDrag}
              onDragOver={handleDrag}
              onDrop={handleDrop}
              className={cn(
                'relative rounded-xl border border-dashed p-md text-center transition-colors',
                dragActive
                  ? 'border-primary bg-primary-container/20'
                  : selectedFile
                    ? 'border-success-container bg-success-container/15'
                    : 'border-outline-variant/80 bg-surface-container-low/40',
              )}
            >
              <input
                type="file"
                accept=".pdf,.docx,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                onChange={handleFileChange}
                disabled={busy}
                className="absolute inset-0 cursor-pointer opacity-0"
              />
              {selectedFile ? (
                <div className="flex items-center justify-between gap-sm text-left">
                  <div className="min-w-0">
                    <p className="text-body-sm font-medium text-on-surface truncate">
                      {selectedFile.name}
                    </p>
                    <p className="text-label-md text-on-surface-variant">
                      {(selectedFile.size / (1024 * 1024)).toFixed(2)} MB
                    </p>
                  </div>
                  {!busy ? (
                    <Button
                      type="button"
                      variant="ghost"
                      size="sm"
                      icon="delete"
                      onClick={(e) => {
                        e.stopPropagation()
                        setSelectedFile(null)
                      }}
                    >
                      Remove
                    </Button>
                  ) : null}
                </div>
              ) : (
                <div className="space-y-xs py-sm">
                  <p className="text-body-sm text-on-surface">
                    Drop PDF/DOCX or browse
                  </p>
                  <p className="text-label-md text-on-surface-variant">Max 10MB</p>
                </div>
              )}
            </div>
          </div>

          <div className="flex flex-wrap justify-end gap-sm pt-sm border-t border-outline-variant/60">
            <Button type="button" variant="secondary" disabled={busy} onClick={handleClose}>
              Cancel
            </Button>
            <Button
              type="submit"
              icon="send"
              loading={busy}
              disabled={busy || !selectedFile}
            >
              {step === 'uploading'
                ? 'Uploading…'
                : step === 'submitting'
                  ? 'Submitting…'
                  : 'Submit application'}
            </Button>
          </div>
        </form>
      )}
    </Modal>
  )
}
