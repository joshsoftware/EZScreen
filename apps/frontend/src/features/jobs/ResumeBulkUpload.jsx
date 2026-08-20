import { useMemo, useRef, useState } from 'react'
import { toast } from 'sonner'
import { Alert } from '../../components/ui/Alert'
import { Button } from '../../components/ui/Button'
import {
  enqueueBulkResumesRequest,
  getResumeUploadUrlsRequest,
} from './api'

const ALLOWED_TYPES = new Set([
  'application/pdf',
  'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
])

function normalizeContentType(file) {
  if (file.type) return file.type
  const lower = file.name.toLowerCase()
  if (lower.endsWith('.pdf')) return 'application/pdf'
  if (lower.endsWith('.docx')) {
    return 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
  }
  return ''
}

export function ResumeBulkUpload({ jobId, onQueued }) {
  const inputRef = useRef(null)
  const [files, setFiles] = useState([])
  const [error, setError] = useState(null)
  const [uploading, setUploading] = useState(false)
  const [dragActive, setDragActive] = useState(false)

  const hasFiles = files.length > 0
  const fileLabel = useMemo(() => {
    if (!hasFiles) return 'Drop PDF or DOCX files here, or browse to select.'
    return `${files.length} file${files.length === 1 ? '' : 's'} ready to upload`
  }, [files, hasFiles])

  function addFiles(selected) {
    if (!selected.length) return
    setError(null)
    setFiles((current) => {
      const existing = new Set(current.map((file) => `${file.name}-${file.size}`))
      const next = [...current]
      for (const file of selected) {
        const key = `${file.name}-${file.size}`
        if (!existing.has(key)) {
          next.push(file)
          existing.add(key)
        }
      }
      return next
    })
  }

  function onFileChange(event) {
    addFiles(Array.from(event.target.files || []))
    event.target.value = ''
  }

  function removeFile(index) {
    setFiles((current) => current.filter((_, i) => i !== index))
  }

  async function uploadToSignedUrl(uploadItem, file) {
    const contentType = normalizeContentType(file)
    const response = await fetch(uploadItem.upload_url, {
      method: 'PUT',
      headers: {
        'Content-Type': contentType,
      },
      body: file,
    })
    if (!response.ok) {
      throw new Error(`Upload failed for ${file.name} (${response.status})`)
    }
  }

  async function onSubmit() {
    if (!hasFiles || uploading) return
    setUploading(true)
    setError(null)

    const invalid = files.find((file) => !ALLOWED_TYPES.has(normalizeContentType(file)))
    if (invalid) {
      setUploading(false)
      setError(`Unsupported file type: ${invalid.name}. Use PDF or DOCX only.`)
      return
    }

    try {
      const payloadFiles = files.map((file) => ({
        file_name: file.name,
        content_type: normalizeContentType(file),
      }))

      const uploadData = await getResumeUploadUrlsRequest(jobId, payloadFiles)
      const uploadItems = Array.isArray(uploadData.uploads) ? uploadData.uploads : []

      const uploadedResumes = await Promise.all(
        uploadItems.map(async (uploadItem) => {
          const file = files.find((f) => f.name === uploadItem.file_name)
          if (!file) {
            throw new Error(`Missing local file for ${uploadItem.file_name}`)
          }
          await uploadToSignedUrl(uploadItem, file)
          return {
            s3_key: uploadItem.s3_key,
            file_name: uploadItem.file_name,
          }
        }),
      )

      if (uploadedResumes.length === 0) {
        throw new Error('No files were uploaded')
      }

      const queued = await enqueueBulkResumesRequest(jobId, uploadedResumes)
      const queuedValue = Number(queued?.queued || uploadedResumes.length)
      toast.success(`${queuedValue} resume${queuedValue === 1 ? '' : 's'} queued`)
      setFiles([])
      if (onQueued) {
        await onQueued(queuedValue)
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to upload resumes')
    } finally {
      setUploading(false)
    }
  }

  return (
    <div className="space-y-md">
      <div
        className={`rounded-xl border-2 border-dashed p-lg transition-colors ${
          dragActive
            ? 'border-secondary bg-primary-container/30'
            : 'border-outline-variant bg-surface-container-low'
        }`}
        onDragEnter={(event) => {
          event.preventDefault()
          setDragActive(true)
        }}
        onDragOver={(event) => {
          event.preventDefault()
          setDragActive(true)
        }}
        onDragLeave={(event) => {
          event.preventDefault()
          setDragActive(false)
        }}
        onDrop={(event) => {
          event.preventDefault()
          setDragActive(false)
          addFiles(Array.from(event.dataTransfer.files || []))
        }}
      >
        <div className="flex flex-col items-center text-center gap-sm">
          <span className="material-symbols-outlined text-[32px] text-secondary">upload_file</span>
          <p className="text-body-sm text-on-surface">{fileLabel}</p>
          <p className="text-label-md text-on-surface-variant">
            Supports PDF and DOCX · up to 50 files
          </p>
          <div className="flex flex-wrap gap-sm justify-center">
            <Button
              variant="secondary"
              size="sm"
              onClick={() => inputRef.current?.click()}
              disabled={uploading}
            >
              Browse files
            </Button>
            <Button
              variant="primary"
              size="sm"
              onClick={onSubmit}
              loading={uploading}
              disabled={!hasFiles}
            >
              Upload and queue
            </Button>
          </div>
          <input
            ref={inputRef}
            type="file"
            multiple
            accept=".pdf,.docx,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            onChange={onFileChange}
            className="hidden"
            disabled={uploading}
          />
        </div>
      </div>

      {hasFiles ? (
        <ul className="divide-y divide-outline-variant rounded-DEFAULT border border-outline-variant bg-surface-container-lowest">
          {files.map((file, index) => (
            <li
              key={`${file.name}-${file.size}`}
              className="flex items-center justify-between gap-sm px-md py-sm"
            >
              <div className="min-w-0">
                <p className="text-body-sm text-on-surface truncate">{file.name}</p>
                <p className="text-label-md text-on-surface-variant">
                  {(file.size / 1024).toFixed(1)} KB
                </p>
              </div>
              <Button
                variant="ghost"
                size="sm"
                onClick={() => removeFile(index)}
                disabled={uploading}
              >
                Remove
              </Button>
            </li>
          ))}
        </ul>
      ) : null}

      {error ? <Alert>{error}</Alert> : null}
    </div>
  )
}
