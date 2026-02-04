export type RemoteSidebarConfigResponse = {
    config: unknown | null
    updatedAtMs: number | null
}

export type RemoteSidebarConfigWriteResponse = {
    ok: boolean
    updatedAtMs: number | null
}

type FetchLike = (input: RequestInfo | URL, init?: RequestInit) => Promise<Response>

export async function fetchRemoteSidebarConfig(
    apiBase: string,
    fetchImpl: FetchLike = fetch,
    signal?: AbortSignal
): Promise<RemoteSidebarConfigResponse | null> {
    const base = (apiBase || '').replace(/\/+$/, '')
    if (!base) return null
    const res = await fetchImpl(`${base}/api/system/ui/sidebar-config`, { method: 'GET', signal })
    if (!res.ok) return null
    const data = (await res.json()) as RemoteSidebarConfigResponse
    return {
        config: data?.config ?? null,
        updatedAtMs: typeof data?.updatedAtMs === 'number' ? data.updatedAtMs : null
    }
}

export async function saveRemoteSidebarConfig(
    apiBase: string,
    config: unknown,
    token: string | null,
    fetchImpl: FetchLike = fetch,
    signal?: AbortSignal
): Promise<RemoteSidebarConfigWriteResponse | null> {
    const base = (apiBase || '').replace(/\/+$/, '')
    if (!base) return null
    const headers: Record<string, string> = { 'content-type': 'application/json' }
    if (token && token.trim()) headers['x-sync-token'] = token.trim()
    const res = await fetchImpl(`${base}/api/system/ui/sidebar-config`, {
        method: 'PUT',
        headers,
        body: JSON.stringify({ config }),
        signal
    })
    if (!res.ok) return null
    const data = (await res.json()) as RemoteSidebarConfigWriteResponse
    return {
        ok: Boolean(data?.ok),
        updatedAtMs: typeof data?.updatedAtMs === 'number' ? data.updatedAtMs : null
    }
}

