/**
 * Google Drive file picker for resume upload.
 * Requires VITE_GOOGLE_CLIENT_ID + VITE_GOOGLE_API_KEY (Picker + Drive APIs enabled).
 */

const GIS_SRC = 'https://accounts.google.com/gsi/client'
const GAPI_SRC = 'https://apis.google.com/js/api.js'
const DRIVE_SCOPE = 'https://www.googleapis.com/auth/drive.readonly'

const MIME_PDF = 'application/pdf'
const MIME_DOCX =
  'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
const MIME_GOOGLE_DOC = 'application/vnd.google-apps.document'

const PICKER_MIME_TYPES = [MIME_PDF, MIME_DOCX, MIME_GOOGLE_DOC].join(',')

function getConfig() {
  const clientId = String(import.meta.env.VITE_GOOGLE_CLIENT_ID || '').trim()
  const apiKey = String(import.meta.env.VITE_GOOGLE_API_KEY || '').trim()
  return { clientId, apiKey, configured: Boolean(clientId && apiKey) }
}

export function isGoogleDriveConfigured() {
  return getConfig().configured
}

function loadScript(src) {
  return new Promise((resolve, reject) => {
    const existing = document.querySelector(`script[src="${src}"]`)
    if (existing) {
      if (existing.dataset.loaded === 'true') {
        resolve()
        return
      }
      existing.addEventListener('load', () => resolve(), { once: true })
      existing.addEventListener('error', () => reject(new Error(`Failed to load ${src}`)), {
        once: true,
      })
      return
    }
    const script = document.createElement('script')
    script.src = src
    script.async = true
    script.onload = () => {
      script.dataset.loaded = 'true'
      resolve()
    }
    script.onerror = () => reject(new Error(`Failed to load ${src}`))
    document.head.appendChild(script)
  })
}

async function ensureGoogleApis() {
  await Promise.all([loadScript(GIS_SRC), loadScript(GAPI_SRC)])
  const gapi = window.gapi
  if (!gapi) throw new Error('Google API failed to load')
  await new Promise((resolve) => {
    gapi.load('client:picker', () => resolve())
  })
}

function requestAccessToken(clientId) {
  return new Promise((resolve, reject) => {
    const google = window.google
    if (!google?.accounts?.oauth2) {
      reject(new Error('Google Identity Services failed to load'))
      return
    }

    const client = google.accounts.oauth2.initTokenClient({
      client_id: clientId,
      scope: DRIVE_SCOPE,
      callback: (response) => {
        if (response?.error) {
          reject(new Error(response.error_description || response.error))
          return
        }
        if (!response?.access_token) {
          reject(new Error('Google sign-in did not return an access token'))
          return
        }
        resolve(response.access_token)
      },
      error_callback: (err) => {
        reject(new Error(err?.message || 'Google sign-in was cancelled'))
      },
    })

    client.requestAccessToken({ prompt: '' })
  })
}

function openPicker({ apiKey, accessToken }) {
  return new Promise((resolve, reject) => {
    const google = window.google
    if (!google?.picker) {
      reject(new Error('Google Picker failed to load'))
      return
    }

    const view = new google.picker.DocsView(google.picker.ViewId.DOCS)
      .setMimeTypes(PICKER_MIME_TYPES)
      .setIncludeFolders(true)
      .setSelectFolderEnabled(false)

    const picker = new google.picker.PickerBuilder()
      .addView(view)
      .enableFeature(google.picker.Feature.MULTISELECT_ENABLED)
      .setOAuthToken(accessToken)
      .setDeveloperKey(apiKey)
      .setTitle('Select resumes from Drive')
      .setCallback((data) => {
        if (data.action === google.picker.Action.CANCEL) {
          resolve([])
          return
        }
        if (data.action === google.picker.Action.PICKED) {
          const docs = Array.isArray(data.docs) ? data.docs : []
          resolve(docs)
        }
      })
      .build()

    // Sit above app modals (z-50) and stay viewport-centered.
    // Default Picker CSS uses absolute top/left and often clips under the
    // browser chrome when the page has a fixed overlay + body scroll lock.
    const styleId = 'ezscreen-google-picker-z'
    let style = document.getElementById(styleId)
    if (!style) {
      style = document.createElement('style')
      style.id = styleId
      document.head.appendChild(style)
    }
    style.textContent = `
      .picker-dialog-bg {
        position: fixed !important;
        inset: 0 !important;
        z-index: 100000 !important;
      }
      .picker-dialog {
        position: fixed !important;
        top: 50% !important;
        left: 50% !important;
        transform: translate(-50%, -50%) !important;
        margin: 0 !important;
        max-height: min(720px, calc(100vh - 48px)) !important;
        z-index: 100001 !important;
      }
    `

    picker.setVisible(true)
  })
}

function ensureExtension(name, mimeType) {
  const lower = name.toLowerCase()
  if (mimeType === MIME_PDF && !lower.endsWith('.pdf')) return `${name}.pdf`
  if (mimeType === MIME_DOCX && !lower.endsWith('.docx')) return `${name}.docx`
  return name
}

async function downloadDriveFile(doc, accessToken) {
  const mimeType = doc.mimeType || ''
  const id = doc.id
  let url
  let outMime
  let fileName = doc.name || 'resume'

  if (mimeType === MIME_GOOGLE_DOC) {
    outMime = MIME_PDF
    fileName = ensureExtension(fileName.replace(/\.gdoc$/i, ''), MIME_PDF)
    url = `https://www.googleapis.com/drive/v3/files/${encodeURIComponent(id)}/export?mimeType=${encodeURIComponent(MIME_PDF)}`
  } else if (mimeType === MIME_PDF || mimeType === MIME_DOCX) {
    outMime = mimeType
    fileName = ensureExtension(fileName, mimeType)
    url = `https://www.googleapis.com/drive/v3/files/${encodeURIComponent(id)}?alt=media`
  } else {
    throw new Error(`Unsupported Drive file type: ${doc.name || id}`)
  }

  const response = await fetch(url, {
    headers: { Authorization: `Bearer ${accessToken}` },
  })
  if (!response.ok) {
    throw new Error(`Failed to download ${fileName} from Drive (${response.status})`)
  }
  const blob = await response.blob()
  return new File([blob], fileName, { type: outMime })
}

/**
 * Opens Google account + Drive picker, returns File[] (PDF/DOCX).
 * Empty array if the user cancels.
 */
export async function pickResumesFromGoogleDrive() {
  const { clientId, apiKey, configured } = getConfig()
  if (!configured) {
    throw new Error(
      'Google Drive is not configured. Set VITE_GOOGLE_CLIENT_ID and VITE_GOOGLE_API_KEY in the frontend .env.',
    )
  }

  await ensureGoogleApis()
  const accessToken = await requestAccessToken(clientId)
  const docs = await openPicker({ apiKey, accessToken })
  if (!docs.length) return []

  const files = await Promise.all(docs.map((doc) => downloadDriveFile(doc, accessToken)))
  return files
}
