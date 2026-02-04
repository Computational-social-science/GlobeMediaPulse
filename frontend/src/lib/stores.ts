import { writable } from 'svelte/store'
import {
    SIDEBAR_STORAGE_KEY,
    getDefaultSidebarConfig,
    normalizeSidebarConfig,
    moveSidebarItem,
    addSidebarGroup,
    setSidebarGroupCollapsed,
    tidySidebarConfig,
    loadSidebarConfig,
    saveSidebarConfig,
    clearSidebarConfig
} from './sidebarConfig'
export type { SidebarItemId, SidebarGroup, SidebarConfig, SidebarMovePayload } from './sidebarConfig'
export {
    SIDEBAR_STORAGE_KEY,
    getDefaultSidebarConfig,
    normalizeSidebarConfig,
    moveSidebarItem,
    addSidebarGroup,
    setSidebarGroupCollapsed,
    tidySidebarConfig,
    loadSidebarConfig,
    saveSidebarConfig,
    clearSidebarConfig
}

type MapState = { selectedCountry: string | null; zoom: number; center: [number, number] }
type MapCommand = { nonce: number; type: string }
type MediaProfileStats = { total: number; hit: number; rate: number }
type HealthServices = { postgres: string; redis: string }
type HealthThreads = { crawler: string; analyzer: string; cleanup: string }
type HealthStatus = {
    updatedAt: number
    apiOk: boolean
    apiLatencyMs: number | null
    services: HealthServices
    threads: HealthThreads
}
type StatusStore = { health: HealthStatus }
type FloatingWindowState = {
    visible: boolean
    minimized: boolean
    maximized: boolean
    position: { x: number; y: number }
}
export type NewsEvent = {
    [key: string]: unknown
    country_code?: string
    country?: string
    countryCode?: string
    country_name?: string
    headline?: string
    title?: string
    has_error?: boolean
    error_details?: { word?: string; suggestion?: string } | null
    errors?: Array<{ word?: string; suggestion?: string }>
    timestamp?: number
    id?: string | number
    coordinates?: unknown
    lng?: number
    lat?: number
    source_domain?: string
    source_domain_norm?: string
    source_name?: string
    logo_url?: string
    tier?: string
}
export type SystemLog = {
    sub_type?: string
    data?: { result?: string; domain?: string; method?: string }
}

export const newsFeed = writable<unknown[]>([])
export const mapMode = writable('vector')
export const soundEnabled = writable(true)
export const audioEnabled = soundEnabled
export const audioVolume = writable(0.5)
export const heatmapEnabled = writable(true)

export const mapState = writable<MapState>({
    selectedCountry: null,
    zoom: 2.5,
    center: [20, 0]
})

export const mapIdleTimeout = writable(0)
export const mapCommand = writable<MapCommand>({ nonce: 0, type: '' })
export const mediaProfileStats = writable<MediaProfileStats>({ total: 0, hit: 0, rate: 0 })

export const isConnected = writable(false)
export const systemStatus = writable('OFFLINE')
export const statusStore = writable<StatusStore>({
    health: {
        updatedAt: 0,
        apiOk: false,
        apiLatencyMs: null,
        services: {
            postgres: 'unknown',
            redis: 'unknown'
        },
        threads: {
            crawler: 'unknown',
            analyzer: 'unknown',
            cleanup: 'unknown'
        }
    }
})
export const newsEvents = writable<NewsEvent | null>(null)
export const systemLogs = writable<SystemLog[]>([])

export const countrySourceFilter = writable('all')

export const countryStats = writable<Record<string, unknown>>({})
export const timelineData = writable<unknown[]>([])

export const windowState = writable<Record<string, FloatingWindowState>>({
    systemMonitor: { visible: true, minimized: false, maximized: false, position: { x: 100, y: 100 } },
    brain: { visible: false, minimized: false, maximized: false, position: { x: 680, y: 120 } }
})

export const mediaSources = writable<unknown[]>([])

export const serviceStatus = writable<HealthServices>({
    postgres: 'unknown',
    redis: 'unknown'
})
export const backendThreadStatus = writable<HealthThreads>({
    crawler: 'unknown',
    analyzer: 'unknown',
    cleanup: 'unknown'
})

export const floatingWindowStack = writable<string[]>(['__init__'])
export const floatingWindowPinned = writable<Map<string, boolean>>(new Map([['__init__', false]]))
export const floatingWindowActive = writable('')
export const floatingWindowDock = writable<string[]>(['__init__'])

export function bringFloatingWindowToFront(windowKey = ''): void {
    floatingWindowStack.update((stack) => {
        const next = stack.filter((key) => key !== '__init__' && key !== windowKey)
        next.push(windowKey)
        return next
    })
    floatingWindowActive.set(windowKey)
}

export function removeFloatingWindow(windowKey = ''): void {
    floatingWindowStack.update((stack) => stack.filter((key) => key !== '__init__' && key !== windowKey))
    floatingWindowDock.update((dock) => dock.filter((key) => key !== '__init__' && key !== windowKey))
    floatingWindowPinned.update((pinned) => {
        const next = new Map(pinned)
        next.delete('__init__')
        next.delete(windowKey)
        return next
    })
    floatingWindowActive.update((active) => (active === windowKey ? '' : active))
}

export function setFloatingWindowPinned(windowKey = '', pinned = false): void {
    floatingWindowPinned.update((current) => {
        const next = new Map(current)
        next.delete('__init__')
        if (pinned) {
            next.set(windowKey, true)
        } else {
            next.delete(windowKey)
        }
        return next
    })
    if (pinned) bringFloatingWindowToFront(windowKey)
}

export function setFloatingWindowMinimized(windowKey = '', minimized = false): void {
    floatingWindowDock.update((dock) => {
        const next = dock.filter((key) => key !== '__init__' && key !== windowKey)
        if (minimized) next.push(windowKey)
        return next
    })
    if (!minimized) bringFloatingWindowToFront(windowKey)
}

export const sidebarConfig = writable(getDefaultSidebarConfig())
