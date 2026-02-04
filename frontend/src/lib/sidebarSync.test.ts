import { describe, it, expect } from 'vitest'
import { fetchRemoteSidebarConfig, saveRemoteSidebarConfig } from './sidebarSync'

describe('sidebarSync', () => {
    it('returns null when apiBase missing', async () => {
        expect(await fetchRemoteSidebarConfig('', async () => new Response(null))).toBe(null)
    })

    it('fetches remote config', async () => {
        const fetchImpl = async () =>
            new Response(JSON.stringify({ config: { version: 1 }, updatedAtMs: 123 }), { status: 200 })
        const res = await fetchRemoteSidebarConfig('http://localhost:8000', fetchImpl)
        expect(res?.config).toEqual({ version: 1 })
        expect(res?.updatedAtMs).toBe(123)
    })

    it('returns null on non-ok responses', async () => {
        const fetchImpl = async () => new Response('no', { status: 500 })
        expect(await fetchRemoteSidebarConfig('http://localhost:8000/', fetchImpl)).toBe(null)
        expect(await saveRemoteSidebarConfig('http://localhost:8000/', { v: 1 }, null, fetchImpl)).toBe(null)
    })

    it('normalizes invalid payload fields', async () => {
        const fetchImpl = async () =>
            new Response(JSON.stringify({ config: undefined, updatedAtMs: 'x' }), { status: 200 })
        const res = await fetchRemoteSidebarConfig('http://localhost:8000', fetchImpl)
        expect(res?.config).toBe(null)
        expect(res?.updatedAtMs).toBe(null)
    })

    it('sends token when provided', async () => {
        let captured: RequestInit | undefined
        const fetchImpl = async (_input: RequestInfo | URL, init?: RequestInit) => {
            captured = init
            return new Response(JSON.stringify({ ok: true, updatedAtMs: 456 }), { status: 200 })
        }
        const res = await saveRemoteSidebarConfig('http://localhost:8000', { version: 1 }, 't', fetchImpl)
        expect(res?.ok).toBe(true)
        expect(res?.updatedAtMs).toBe(456)
        expect((captured?.headers as Record<string, string>)['x-sync-token']).toBe('t')
    })

    it('does not send token when blank', async () => {
        let captured: RequestInit | undefined
        const fetchImpl = async (_input: RequestInfo | URL, init?: RequestInit) => {
            captured = init
            return new Response(JSON.stringify({ ok: true, updatedAtMs: 1 }), { status: 200 })
        }
        await saveRemoteSidebarConfig('http://localhost:8000', { version: 1 }, '   ', fetchImpl)
        expect((captured?.headers as Record<string, string>)['x-sync-token']).toBeUndefined()
    })
})
