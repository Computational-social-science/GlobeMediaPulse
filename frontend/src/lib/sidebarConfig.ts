export type SidebarItemId = 'status' | 'gde' | 'autoheal'
export type SidebarGroup = { id: string; title: string; items: SidebarItemId[]; collapsed?: boolean }
export type SidebarConfig = { version: number; groups: SidebarGroup[] }
export type SidebarMovePayload = {
    itemId?: SidebarItemId
    fromGroupId?: string
    toGroupId?: string
    toIndex?: number
}

type StorageLike = {
    getItem: (key: string) => string | null
    setItem: (key: string, value: string) => void
    removeItem: (key: string) => void
}

const sidebarItemIds: SidebarItemId[] = ['status', 'gde', 'autoheal']
export const SIDEBAR_STORAGE_KEY = 'sidebarConfig'

export function getDefaultSidebarConfig(): SidebarConfig {
    return {
        version: 1,
        groups: [
            {
                id: 'core',
                title: 'Core',
                items: [...sidebarItemIds],
                collapsed: false
            }
        ]
    }
}

export function normalizeSidebarConfig(raw: unknown): SidebarConfig {
    if (!raw || typeof raw !== 'object') return getDefaultSidebarConfig()
    const rawRecord = raw as { groups?: unknown }
    const groups = Array.isArray(rawRecord.groups) ? rawRecord.groups : []
    const seen = new Set<SidebarItemId>()
    const normalizedGroups = groups.map((group, index) => {
        const candidate = group as {
            id?: unknown
            title?: unknown
            collapsed?: unknown
            items?: unknown
        }
        const id = typeof candidate.id === 'string' && candidate.id ? candidate.id : `group-${index + 1}`
        const title =
            typeof candidate.title === 'string' && candidate.title.trim()
                ? candidate.title.trim()
                : `Group ${index + 1}`
        const collapsed = Boolean(candidate.collapsed)
        const items = Array.isArray(candidate.items)
            ? candidate.items.filter((item): item is SidebarItemId => {
                  if (typeof item !== 'string') return false
                  const asItem = item as SidebarItemId
                  if (!sidebarItemIds.includes(asItem)) return false
                  if (seen.has(asItem)) return false
                  seen.add(asItem)
                  return true
              })
            : []
        return { id, title, collapsed, items }
    })
    if (!normalizedGroups.length) {
        normalizedGroups.push({
            id: 'core',
            title: 'Core',
            items: [],
            collapsed: false
        })
    }
    const missing = sidebarItemIds.filter((item) => !seen.has(item))
    if (missing.length) {
        normalizedGroups[0] = {
            ...normalizedGroups[0],
            items: [...normalizedGroups[0].items, ...missing]
        }
    }
    return {
        version: 1,
        groups: normalizedGroups
    }
}

export function moveSidebarItem(config: unknown, payload?: SidebarMovePayload): SidebarConfig {
    const next = normalizeSidebarConfig(config)
    const itemId = payload?.itemId
    if (!itemId || !sidebarItemIds.includes(itemId)) return next
    const sourceGroupIndex = next.groups.findIndex((group) => group.id === payload?.fromGroupId)
    const targetGroupIndex = next.groups.findIndex((group) => group.id === payload?.toGroupId)
    if (sourceGroupIndex < 0 || targetGroupIndex < 0) return next
    const sourceGroup = next.groups[sourceGroupIndex]
    const targetGroup = next.groups[targetGroupIndex]
    const fromIndex = sourceGroup.items.indexOf(itemId)
    if (fromIndex < 0) return next
    let insertIndex = typeof payload?.toIndex === 'number' ? payload.toIndex : targetGroup.items.length
    if (sourceGroupIndex === targetGroupIndex && insertIndex > fromIndex) {
        insertIndex -= 1
    }
    const [removed] = sourceGroup.items.splice(fromIndex, 1)
    const clampedIndex = Math.max(0, Math.min(insertIndex, targetGroup.items.length))
    targetGroup.items.splice(clampedIndex, 0, removed)
    const groups = next.groups.map((group, index) => {
        if (index === sourceGroupIndex || index === targetGroupIndex) {
            return { ...group, items: [...group.items] }
        }
        return group
    })
    return { ...next, groups }
}

export function addSidebarGroup(config: unknown, title = ''): { config: SidebarConfig; groupId: string } {
    const next = normalizeSidebarConfig(config)
    let counter = 1
    let id = `group-${counter}`
    while (next.groups.some((group) => group.id === id)) {
        counter += 1
        id = `group-${counter}`
    }
    const trimmedTitle = title.trim()
    const groupTitle = trimmedTitle || `Group ${next.groups.length + 1}`
    const groups = [
        ...next.groups,
        {
            id,
            title: groupTitle,
            items: [],
            collapsed: false
        }
    ]
    return { config: { ...next, groups }, groupId: id }
}

export function setSidebarGroupCollapsed(config: unknown, groupId: string, collapsed: boolean): SidebarConfig {
    const next = normalizeSidebarConfig(config)
    const groups = next.groups.map((group) =>
        group.id === groupId ? { ...group, collapsed: Boolean(collapsed) } : group
    )
    return { ...next, groups }
}

export function tidySidebarConfig(config: unknown): SidebarConfig {
    const next = normalizeSidebarConfig(config)
    const normalizedGroups = next.groups.map((group, index) => {
        const title = group.title.trim() || `Group ${index + 1}`
        return { ...group, title, items: [...group.items] }
    })
    const filteredGroups = normalizedGroups.filter((group, index) => group.items.length > 0 || index === 0)
    return { ...next, groups: filteredGroups }
}

export function loadSidebarConfig(storage?: StorageLike | null): SidebarConfig | null {
    if (!storage) return null
    try {
        const raw = storage.getItem(SIDEBAR_STORAGE_KEY)
        if (!raw) return null
        const parsed = JSON.parse(raw)
        return tidySidebarConfig(normalizeSidebarConfig(parsed))
    } catch {
        return null
    }
}

export function saveSidebarConfig(storage: StorageLike | null | undefined, config: unknown): boolean {
    if (!storage) return false
    try {
        storage.setItem(SIDEBAR_STORAGE_KEY, JSON.stringify(tidySidebarConfig(config)))
        return true
    } catch {
        return false
    }
}

export function clearSidebarConfig(storage?: StorageLike | null): boolean {
    if (!storage) return false
    try {
        storage.removeItem(SIDEBAR_STORAGE_KEY)
        return true
    } catch {
        return false
    }
}
