import { useAuthStore } from '@/stores/auth'
import type { TokenPair } from '@/lib/types'

export class ApiError extends Error {
  status: number
  detail: string

  constructor(status: number, detail: string) {
    super(detail)
    this.status = status
    this.detail = detail
  }
}

const BASE = '/api/v1'

let refreshPromise: Promise<boolean> | null = null

async function doRefresh(): Promise<boolean> {
  const refreshToken = useAuthStore.getState().refreshToken
  if (!refreshToken) return false
  try {
    const res = await fetch(`${BASE}/auth/refresh`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ refresh_token: refreshToken }),
    })
    if (!res.ok) {
      useAuthStore.getState().clear()
      return false
    }
    const pair = (await res.json()) as TokenPair
    useAuthStore.getState().setAuth(pair)
    return true
  } catch {
    return false
  }
}

interface ApiOptions {
  method?: 'GET' | 'POST' | 'PUT' | 'PATCH' | 'DELETE'
  body?: unknown
  params?: Record<string, unknown>
  formData?: FormData
}

function buildUrl(path: string, params?: Record<string, unknown>): string {
  let url = BASE + path
  if (params) {
    const sp = new URLSearchParams()
    for (const [key, value] of Object.entries(params)) {
      if (value !== undefined && value !== null && value !== '') sp.set(key, String(value))
    }
    const qs = sp.toString()
    if (qs) url += `?${qs}`
  }
  return url
}

export async function api<T>(path: string, opts: ApiOptions = {}): Promise<T> {
  const { method = 'GET', body, params, formData } = opts
  const url = buildUrl(path, params)

  const doFetch = () => {
    const headers: Record<string, string> = {}
    const token = useAuthStore.getState().accessToken
    if (token) headers.Authorization = `Bearer ${token}`
    if (body !== undefined) headers['Content-Type'] = 'application/json'
    return fetch(url, {
      method,
      headers,
      body: formData ?? (body !== undefined ? JSON.stringify(body) : undefined),
    })
  }

  let res = await doFetch()
  if (res.status === 401 && useAuthStore.getState().refreshToken && !path.startsWith('/auth/')) {
    refreshPromise = refreshPromise ?? doRefresh()
    const refreshed = await refreshPromise
    refreshPromise = null
    if (refreshed) res = await doFetch()
  }

  if (!res.ok) {
    let detail = res.statusText
    try {
      const data = await res.json()
      detail = typeof data.detail === 'string' ? data.detail : JSON.stringify(data.detail)
    } catch {
      /* keep statusText */
    }
    if (res.status === 401) useAuthStore.getState().clear()
    throw new ApiError(res.status, detail)
  }
  if (res.status === 204) return undefined as T
  return (await res.json()) as T
}

async function authedBlob(path: string, params?: Record<string, unknown>): Promise<Blob> {
  const token = useAuthStore.getState().accessToken
  const res = await fetch(buildUrl(path, params), {
    headers: token ? { Authorization: `Bearer ${token}` } : {},
  })
  if (!res.ok) throw new ApiError(res.status, res.statusText)
  return res.blob()
}

export async function downloadFile(
  path: string,
  filename: string,
  params?: Record<string, unknown>
): Promise<void> {
  const blob = await authedBlob(path, params)
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  a.click()
  URL.revokeObjectURL(url)
}

export async function openBlobInTab(path: string): Promise<void> {
  const blob = await authedBlob(path)
  const url = URL.createObjectURL(blob)
  window.open(url, '_blank', 'noopener')
  setTimeout(() => URL.revokeObjectURL(url), 60_000)
}
