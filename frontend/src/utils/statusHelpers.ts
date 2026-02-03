export function getStatusColor(status?: string): string {
    const value = String(status || '').toLowerCase();
    if (!value || value === 'unknown') return 'status-text-neutral';
    if (value === 'ok' || value === 'running' || value === 'active' || value === 'online') return 'status-text-ok';
    if (value === 'disabled' || value === 'idle') return 'status-text-neutral';
    if (value === 'restarting' || value === 'starting' || value === 'warning' || value === 'degraded' || value === 'waiting')
        return 'status-text-warn';
    if (value === 'stalled' || value === 'stopped' || value === 'error' || value === 'failed' || value === 'offline')
        return 'status-text-error';
    return 'status-text-neutral';
}

export function getThreadStatusColor(status?: string): string {
    return getStatusColor(status);
}

export function getSystemIconClass(status?: string): string {
    if (status === 'ONLINE') return 'status-text-ok';
    if (status === 'DEGRADED') return 'status-text-warn';
    if (status === 'OFFLINE') return 'status-text-error';
    return 'status-text-neutral';
}

export function getSystemDotClass(status?: string): string {
    if (status === 'ONLINE') return 'status-dot-ok';
    if (status === 'DEGRADED') return 'status-dot-warn';
    if (status === 'OFFLINE') return 'status-dot-error';
    return 'status-dot-neutral';
}

export function getSystemSlotClass(systemStatus: string): string {
    if (systemStatus === 'ONLINE') return 'status-bg-ok';
    if (systemStatus === 'DEGRADED') return 'status-bg-warn';
    if (systemStatus === 'OFFLINE') return 'status-bg-error';
    return 'sidebar-panel-sub sidebar-text-muted';
}

export function getSecondarySlotClass(): string {
     return 'sidebar-panel-sub sidebar-text-muted';
}

export function getSystemTitleClass(systemStatus: string): string {
    if (systemStatus === 'ONLINE') return 'status-text-ok';
    if (systemStatus === 'DEGRADED') return 'status-text-warn';
    if (systemStatus === 'OFFLINE') return 'status-text-error';
    return 'sidebar-text-muted';
}
