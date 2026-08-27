import { useEffect, useState } from 'react'
import { toast } from 'sonner'
import { Button } from '../../components/ui/Button'
import { Modal } from '../../components/ui/Modal'
import { ApiError } from '../../lib/api/client'
import { fetchApplicationResumeFile } from './api'

function triggerBlobDownload(blob, fileName) {
  const objectUrl = URL.createObjectURL(blob)
  const anchor = document.createElement('a')
  anchor.href = objectUrl
  anchor.download = fileName || 'resume.pdf'
  anchor.rel = 'noopener'
  document.body.appendChild(anchor)
  anchor.click()
  anchor.remove()
  URL.revokeObjectURL(objectUrl)
}

export function ResumePreviewButton({
  applicationId,
  hasResume,
  fileName,
  variant = 'secondary',
  size = 'md',
}) {
  const [loading, setLoading] = useState(false)
  const [preview, setPreview] = useState(null)

  useEffect(() => {
    return () => {
      if (preview?.url) {
        URL.revokeObjectURL(preview.url)
      }
    }
  }, [preview])

  function closePreview() {
    setPreview((current) => {
      if (current?.url) {
        URL.revokeObjectURL(current.url)
      }
      return null
    })
  }

  async function onPreview() {
    if (!hasResume || loading) return
    setLoading(true)
    try {
      const { blob, fileName: remoteName, contentType } = await fetchApplicationResumeFile(
        applicationId,
        'inline',
      )
      const resolvedName = remoteName || fileName || 'Resume'
      const isPdf =
        contentType === 'application/pdf' ||
        resolvedName.toLowerCase().endsWith('.pdf') ||
        blob.type === 'application/pdf'

      if (!isPdf) {
        toast.message('Preview is available for PDF resumes. Downloading instead.')
        triggerBlobDownload(blob, resolvedName)
        return
      }

      const url = URL.createObjectURL(blob)
      setPreview({
        url,
        fileName: resolvedName,
      })
    } catch (err) {
      toast.error(
        err instanceof ApiError || err instanceof Error
          ? err.message
          : 'Failed to open resume',
      )
    } finally {
      setLoading(false)
    }
  }

  if (!hasResume) return null

  return (
    <>
      <Button
        variant={variant}
        size={size}
        icon="visibility"
        loading={loading}
        onClick={onPreview}
      >
        Preview resume
      </Button>

      <Modal
        open={Boolean(preview)}
        onClose={closePreview}
        title={preview?.fileName || 'Resume'}
        className="max-w-5xl w-[min(96vw,56rem)]"
      >
        {preview ? (
          <iframe
            title={preview.fileName}
            src={preview.url}
            className="w-full h-[70vh] rounded-xl border border-outline-variant bg-surface"
          />
        ) : null}
      </Modal>
    </>
  )
}
