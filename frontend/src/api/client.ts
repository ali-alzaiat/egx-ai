import { useQuery } from '@tanstack/react-query'

const API_BASE = '/api'

async function fetchApi<T>(path: string): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`)
  if (!res.ok) throw new Error(`API error: ${res.status}`)
  return res.json()
}

export function useHealthCheck() {
  return useQuery({
    queryKey: ['health'],
    queryFn: () => fetchApi<{ status: string; version: string }>('/health'),
  })
}
