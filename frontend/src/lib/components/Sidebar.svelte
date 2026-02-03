<script lang="ts">
    import {
        serviceStatus,
        systemStatus,
        backendThreadStatus,
        isConnected,
        soundEnabled,
        mapCommand,
        mediaProfileStats,
    } from '@stores';
    import {
        getStatusColor,
        getSystemIconClass,
        getSystemDotClass,
        getSystemSlotClass,
        getSecondarySlotClass,
        getSystemTitleClass
    } from '@/utils/statusHelpers.js';

    // State Props
    export let sidebarCollapsed = true;
    export let expandedPanel: 'health' | 'autoheal' | 'gde' | null = 'gde';
    export let activeView: 'health' | 'autoheal' | 'gde' = 'gde';
    export let statusPanelExpanded = true;
    
    // Data Props
    export let totalSources = 0;
    export let healthUpdatedAt = 0;
    export let uiNow = Date.now();
    export let apiOk = false;
    export let apiLatencyMs: number | null = null;
    export let isSystemCritical = false;
    export let isOffline = false;
    
    // Callbacks
    export let onExpand: () => void;
    export let onCollapse: () => void;
    export let onTogglePanel: (view: 'health' | 'autoheal' | 'gde') => void;
    export let onToggleStatusPanel: () => void;
    export let onOpenDiagnostic: () => void;
    export let onHover: (hover: boolean) => void;
    export let onScroll: () => void;
    export let onActivity: () => void;

    let toolsExpanded = false;

    $: statusSummary = `${$systemStatus} | ${formatBigNumber(totalSources)} SRC | WS ${$isConnected ? '✓' : '×'} | API ${apiOk ? '✓' : '×'}${
            apiOk && apiLatencyMs != null ? ` ${apiLatencyMs}ms` : ''
        } | HEALTH ${formatAgeSeconds(healthUpdatedAt, uiNow)}`;

    $: disabledClass = isOffline ? 'opacity-50 pointer-events-none grayscale' : '';

    function formatBigNumber(num: number) {
        if (num >= 1000000) {
            return (num / 1000000).toFixed(3) + 'M';
        }
        return num.toLocaleString();
    }

    function formatPercent(value: number | null | undefined) {
        if (value == null || Number.isNaN(value)) return '—';
        return `${(value * 100).toFixed(2)}%`;
    }

    function formatAgeSeconds(fromEpochMs: number, nowEpochMs: number) {
        if (!fromEpochMs) return '—';
        const sec = Math.max(0, Math.floor((nowEpochMs - fromEpochMs) / 1000));
        if (sec < 60) return `${sec}s`;
        const min = Math.floor(sec / 60);
        if (min < 60) return `${min}m`;
        const hr = Math.floor(min / 60);
        return `${hr}h`;
    }

    function emitMapCommandWithActivity(type: string) {
        mapCommand.update((current: { nonce?: number; type?: string | null }) => ({
            nonce: (Number(current?.nonce) || 0) + 1,
            type,
        }));
        onActivity();
    }

    function toggleSoundWithActivity() {
        soundEnabled.update(v => !v);
        onActivity();
    }
</script>

<aside
    class="absolute inset-y-0 left-0 z-[200] min-h-0 sidebar-shell sidebar-theme shadow-[inset_0_1px_0_rgba(255,255,255,0.06)] overflow-hidden"
    style="width: {sidebarCollapsed ? '56px' : '320px'};"
    on:mouseenter={() => onHover(true)}
    on:mouseleave={() => onHover(false)}
>
    <div class="h-full min-h-0 flex flex-col">
        <div class="h-12 px-2 flex items-center sidebar-top">
            <div class="flex items-center gap-2 min-w-0 flex-1">
                {#if sidebarCollapsed}
                    <button
                        class="w-9 h-9 rounded flex items-center justify-center sidebar-hoverable sidebar-icon-muted"
                        on:click={onExpand}
                        title="Expand Sidebar"
                    >
                        <span class="material-icons-round text-[18px]">chevron_right</span>
                    </button>
                {:else}
                    <button
                        class="w-9 h-9 rounded flex items-center justify-center sidebar-hoverable sidebar-icon-muted"
                        on:click={onCollapse}
                        title="Collapse Sidebar"
                    >
                        <span class="material-icons-round text-[18px]">chevron_left</span>
                    </button>
                {/if}
                {#if !sidebarCollapsed}
                    <div class="min-w-0">
                        <div class="flex items-center gap-2 min-w-0">
                            <span class="w-6 h-6 rounded sidebar-panel-sub border sidebar-border flex items-center justify-center sidebar-text shrink-0">
                                <span class="material-icons-round text-[16px]">public</span>
                            </span>
                            <div class="text-xs font-semibold tracking-wide truncate sidebar-text">Globe Media Pulse</div>
                        </div>
                    </div>
                {/if}
            </div>
        </div>

        <nav class="flex-1 min-h-0 overflow-y-auto px-1 py-2 flex flex-col gap-1" on:scroll={onScroll}>
            {#if !sidebarCollapsed}
                <button
                    type="button"
                    class="mx-1 mt-1 px-2 py-1 rounded sidebar-panel border sidebar-border text-[10px] font-mono font-semibold tracking-widest sidebar-text-muted flex items-center gap-1.5"
                    on:click={onToggleStatusPanel}
                >
                    <span class="material-icons-round text-[14px] {getSystemTitleClass($systemStatus)}">monitor_heart</span><span class={getSystemTitleClass($systemStatus)}>Status</span>
                    <span class="ml-auto material-icons-round text-[16px] sidebar-icon-dim">{statusPanelExpanded ? 'expand_less' : 'expand_more'}</span>
                </button>
            {/if}
            {#if sidebarCollapsed}
                <button
                    type="button"
                    class="rounded flex items-center gap-2 px-2 sidebar-panel border sidebar-border min-w-0 overflow-hidden h-10 justify-center"
                    title={statusSummary}
                    on:click={onExpand}
                >
                    <span class="w-2 h-2 rounded-full {getSystemDotClass($systemStatus)}"></span>
                    <span class="material-icons-round text-[18px] {getSystemIconClass($systemStatus)}">monitor_heart</span>
                </button>
            {:else if statusPanelExpanded}
                <div class="mx-1 mb-1 space-y-1">
                    {#if isSystemCritical}
                        <button
                            type="button"
                            class={`flex items-center gap-2 px-2 py-1 rounded border sidebar-panel-soft ${getSystemSlotClass($systemStatus)}`}
                            on:click={onOpenDiagnostic}
                        >
                            <span class="material-icons-round text-[14px] {getSystemIconClass($systemStatus)}">healing</span>
                            <span class="text-[10px] font-mono tracking-widest flex-1">DIAGNOSTICS</span>
                            <span class="text-[10px] font-mono tracking-widest">{isOffline ? 'Health' : 'Autoheal'}</span>
                        </button>
                    {/if}
                    <div class={`flex items-center justify-between px-2 py-1 rounded border sidebar-panel-soft ${getSystemSlotClass($systemStatus)}`}>
                        <span class="text-[10px] font-mono tracking-widest">SYSTEM</span>
                        <span class="text-[10px] font-mono tracking-widest">{$systemStatus}</span>
                    </div>
                    <div class={`flex items-center justify-between px-2 py-1 rounded border sidebar-panel-soft ${getSecondarySlotClass()}`}>
                        <span class="text-[10px] font-mono tracking-widest">SRC</span>
                        <span class="text-[10px] font-mono tracking-widest">{formatBigNumber(totalSources)}</span>
                    </div>
                    <div class={`flex items-center justify-between px-2 py-1 rounded border sidebar-panel-soft ${getSecondarySlotClass()}`}>
                        <span class="text-[10px] font-mono tracking-widest">WS</span>
                        <span class="text-[10px] font-mono tracking-widest">{$isConnected ? '✓' : '×'}</span>
                    </div>
                    <div class={`flex items-center justify-between px-2 py-1 rounded border sidebar-panel-soft ${getSecondarySlotClass()}`}>
                        <span class="text-[10px] font-mono tracking-widest">API</span>
                        <span class="text-[10px] font-mono tracking-widest">{apiOk ? '✓' : '×'}{apiOk && apiLatencyMs != null ? ` ${apiLatencyMs}ms` : ''}</span>
                    </div>
                    <div class={`flex items-center justify-between px-2 py-1 rounded border sidebar-panel-soft ${getSecondarySlotClass()}`}>
                        <span class="text-[10px] font-mono tracking-widest">HEALTH</span>
                        <span class="text-[10px] font-mono tracking-widest">{formatAgeSeconds(healthUpdatedAt, uiNow)}</span>
                    </div>
                    <div class={`flex items-center justify-between px-2 py-1 rounded border sidebar-panel-soft ${getSecondarySlotClass()}`}>
                        <span class="text-[10px] font-mono tracking-widest">PROFILE</span>
                        <span class="text-[10px] font-mono tracking-widest">
                            {$mediaProfileStats.total
                                ? `${formatPercent($mediaProfileStats.rate)} ${$mediaProfileStats.hit}/${$mediaProfileStats.total}`
                                : '—'}
                        </span>
                    </div>
                </div>
            {/if}

            {#if !sidebarCollapsed}
                <div class="h-px sidebar-divider mx-1 my-2"></div>
            {/if}

            <!-- GDE Panel -->
            <button
                class="relative h-10 rounded flex items-center gap-2 px-2 sidebar-hoverable border sidebar-border {activeView === 'gde' ? 'sidebar-active' : 'bg-transparent'}"
                class:justify-center={sidebarCollapsed}
                on:click={() => onTogglePanel('gde')}
                title="Geographic Diversity Entropy"
            >
                {#if activeView === 'gde'}
                    <span class="absolute left-0 top-1.5 bottom-1.5 w-[2px] rounded-full sidebar-indicator"></span>
                {/if}
                {#if sidebarCollapsed && activeView === 'gde'}
                    <span class="absolute bottom-1 left-1/2 -translate-x-1/2 w-1.5 h-1.5 rounded-full sidebar-indicator"></span>
                {/if}
                <span class="material-icons-round text-[18px] {activeView === 'gde' ? 'sidebar-text' : 'sidebar-text-muted'}">diversity_3</span>
                {#if !sidebarCollapsed}
                    <span class="text-[11px] font-mono tracking-widest sidebar-text truncate">Geographic Diversity Entropy</span>
                    <span class="ml-auto text-[10px] font-mono sidebar-text-quiet flex items-center gap-1">
                        <span class="material-icons-round text-[16px] sidebar-icon-dim">{expandedPanel === 'gde' ? 'expand_less' : 'expand_more'}</span>
                    </span>
                {/if}
            </button>

            {#if !sidebarCollapsed && expandedPanel === 'gde'}
                <div class="mx-1 mb-1 rounded sidebar-panel-soft border sidebar-border overflow-hidden">
                    <div class="h-9 px-2 flex items-center gap-2 border-b sidebar-border">
                        <span class="material-icons-round text-[18px] sidebar-icon-muted">diversity_3</span>
                        <div class="text-xs font-semibold sidebar-text">Geographic Diversity Entropy</div>
                    </div>
                    <div class="p-3 text-[11px] sidebar-text-dim space-y-2">
                        <slot name="gde-content"></slot>
                    </div>
                </div>
            {/if}

            <!-- Health Panel -->
            <button
                class="relative h-10 rounded flex items-center gap-2 px-2 sidebar-hoverable border sidebar-border {activeView === 'health' ? 'sidebar-active' : 'bg-transparent'}"
                class:justify-center={sidebarCollapsed}
                on:click={() => onTogglePanel('health')}
                title="Health"
            >
                {#if activeView === 'health'}
                    <span class="absolute left-0 top-1.5 bottom-1.5 w-[2px] rounded-full sidebar-indicator"></span>
                {/if}
                {#if sidebarCollapsed && activeView === 'health'}
                    <span class="absolute bottom-1 left-1/2 -translate-x-1/2 w-1.5 h-1.5 rounded-full sidebar-indicator"></span>
                {/if}
                <span class="material-icons-round text-[18px] {activeView === 'health' ? 'sidebar-text' : 'sidebar-text-muted'}">health_and_safety</span>
                {#if !sidebarCollapsed}
                    <span class="text-[11px] font-mono tracking-widest sidebar-text">Health</span>
                    <span class="ml-auto text-[10px] font-mono sidebar-text-quiet flex items-center gap-1">
                        <span class="material-icons-round text-[16px] sidebar-icon-dim">{expandedPanel === 'health' ? 'expand_less' : 'expand_more'}</span>
                    </span>
                {/if}
            </button>

            {#if !sidebarCollapsed && expandedPanel === 'health'}
                <div class="mx-1 mb-1 rounded sidebar-panel-soft border sidebar-border overflow-hidden">
                    <div class="h-9 px-2 flex items-center gap-2 border-b sidebar-border">
                            <span class="material-icons-round text-[18px] sidebar-icon-muted">health_and_safety</span>
                            <div class="text-xs font-semibold sidebar-text">System Health</div>
                            <div class="ml-auto">
                                <slot name="health-header-actions"></slot>
                            </div>
                        </div>
                    <div class="p-3 text-[11px] sidebar-text-dim space-y-2">
                        <slot name="health-content"></slot>
                    </div>
                </div>
            {/if}

            <!-- Autoheal Panel -->
            <button
                class="relative h-10 rounded flex items-center gap-2 px-2 sidebar-hoverable border sidebar-border {activeView === 'autoheal' ? 'sidebar-active' : 'bg-transparent'}"
                class:justify-center={sidebarCollapsed}
                on:click={() => onTogglePanel('autoheal')}
                title="Autoheal"
            >
                {#if activeView === 'autoheal'}
                    <span class="absolute left-0 top-1.5 bottom-1.5 w-[2px] rounded-full sidebar-indicator"></span>
                {/if}
                {#if sidebarCollapsed && activeView === 'autoheal'}
                    <span class="absolute bottom-1 left-1/2 -translate-x-1/2 w-1.5 h-1.5 rounded-full sidebar-indicator"></span>
                {/if}
                <span class="material-icons-round text-[18px] {activeView === 'autoheal' ? 'sidebar-text' : 'sidebar-text-muted'}">build</span>
                {#if !sidebarCollapsed}
                    <span class="text-[11px] font-mono tracking-widest sidebar-text">Autoheal</span>
                    <span class="ml-auto text-[10px] font-mono sidebar-text-quiet flex items-center gap-1">
                        <span class="material-icons-round text-[16px] sidebar-icon-dim">{expandedPanel === 'autoheal' ? 'expand_less' : 'expand_more'}</span>
                    </span>
                {/if}
            </button>

            {#if !sidebarCollapsed && expandedPanel === 'autoheal'}
                <div class="mx-1 mb-1 rounded sidebar-panel-soft border sidebar-border overflow-hidden">
                    <div class="h-9 px-2 flex items-center gap-2 border-b sidebar-border">
                        <span class="material-icons-round text-[18px] sidebar-icon-muted">build</span>
                        <div class="text-xs font-semibold sidebar-text">Autoheal Controls</div>
                    </div>
                    <div class="p-3 text-[11px] sidebar-text-dim space-y-2">
                        <slot name="autoheal-content"></slot>
                    </div>
                </div>
            {/if}

            <!-- Tools Section -->
            {#if !sidebarCollapsed}
                <div class="h-px sidebar-divider mx-1 my-2"></div>
                <button
                    type="button"
                    class="mx-1 px-2 py-1 rounded sidebar-panel border sidebar-border text-[10px] font-mono font-semibold tracking-widest sidebar-text-muted flex items-center gap-1.5"
                    on:click={() => { toolsExpanded = !toolsExpanded; onActivity(); }}
                >
                    <span class="material-icons-round text-[14px] sidebar-icon-muted">handyman</span><span>Tools</span>
                    <span class="ml-auto flex items-center gap-1.5">
                        <span class="px-1.5 py-0.5 rounded sidebar-panel-sub border sidebar-border text-[9px] font-mono tracking-widest sidebar-text-quiet">System</span>
                        {#if isSystemCritical}
                            <span class={`px-1.5 py-0.5 rounded border sidebar-panel-sub text-[10px] font-mono tracking-widest ${getSystemSlotClass($systemStatus)}`}>{$systemStatus}</span>
                        {/if}
                        <span class="material-icons-round text-[16px] sidebar-icon-dim">{toolsExpanded ? 'expand_less' : 'expand_more'}</span>
                    </span>
                </button>
            {:else}
                <div class="h-px sidebar-divider my-1 mx-1"></div>
            {/if}

            {#if toolsExpanded || sidebarCollapsed}
                {#if toolsExpanded && !sidebarCollapsed}
                    <div class="h-px sidebar-divider mx-1 my-2"></div>
                {/if}
                
                <!-- Only show expanded tools if sidebar is expanded AND tools is expanded -->
                <!-- OR if sidebar is collapsed (show icons) -->
                <!-- Wait, if sidebar is collapsed, we don't see the Tools toggle button. -->
                <!-- The original code showed icons when toolsExpanded was true, BUT toolsExpanded could only be toggled when sidebar was expanded. -->
                <!-- Actually, in original code: if sidebarCollapsed, it shows icons? No. -->
                <!-- Original: {#if toolsExpanded} ... buttons ... {/if} -->
                <!-- And toolsExpanded toggle button is only visible if !sidebarCollapsed. -->
                <!-- So if sidebar is collapsed, tools are hidden unless they were expanded before? -->
                <!-- But if sidebarCollapsed, toolsExpanded might be true but we might want to hide them or show icons? -->
                <!-- The original code: the buttons are inside `{#if toolsExpanded}`. -->
                <!-- If sidebarCollapsed, the toggle button is hidden. So you can't toggle it. -->
                <!-- But if it was already expanded, it stays expanded? -->
                <!-- Let's assume tools are only for expanded sidebar or if we want quick actions. -->
                <!-- Actually, the icons are nice. Let's make them always visible if we want? -->
                <!-- No, stick to original behavior for now to avoid visual clutter. -->
                
                {#if toolsExpanded}
                    <button
                        class="h-10 rounded flex items-center gap-2 px-2 sidebar-hoverable border sidebar-border sidebar-text-muted {disabledClass}"
                        class:justify-center={sidebarCollapsed}
                        on:click={() => emitMapCommandWithActivity('export_png_1200')}
                        title="Export PNG (1200 DPI)"
                    >
                        <span class="material-icons-round text-[18px]">image</span>
                        {#if !sidebarCollapsed}
                            <span class="text-[11px] font-mono tracking-widest">Export PNG</span>
                            <span class="ml-auto text-[10px] font-mono sidebar-text-quiet">1200 DPI</span>
                        {/if}
                    </button>

                    <button
                        class="h-10 rounded flex items-center gap-2 px-2 sidebar-hoverable border sidebar-border sidebar-text-muted {disabledClass}"
                        class:justify-center={sidebarCollapsed}
                        on:click={() => emitMapCommandWithActivity('export_svg_1200')}
                        title="Export SVG"
                    >
                        <span class="material-icons-round text-[18px]">schema</span>
                        {#if !sidebarCollapsed}
                            <span class="text-[11px] font-mono tracking-widest">Export SVG</span>
                            <span class="ml-auto text-[10px] font-mono sidebar-text-quiet">Vector</span>
                        {/if}
                    </button>

                    <button
                        class="h-10 rounded flex items-center gap-2 px-2 sidebar-hoverable border sidebar-border sidebar-text-muted {disabledClass}"
                        class:justify-center={sidebarCollapsed}
                        on:click={() => emitMapCommandWithActivity('reset_view')}
                        title="Reset View"
                    >
                        <span class="material-icons-round text-[18px]">my_location</span>
                        {#if !sidebarCollapsed}
                            <span class="text-[11px] font-mono tracking-widest">Reset View</span>
                        {/if}
                    </button>

                    <button
                        class="h-10 rounded flex items-center gap-2 px-2 sidebar-hoverable border sidebar-border sidebar-text-muted"
                        class:justify-center={sidebarCollapsed}
                        on:click={toggleSoundWithActivity}
                        title={$soundEnabled ? 'Sound: On' : 'Sound: Off'}
                        aria-pressed={$soundEnabled}
                    >
                        <span class="material-icons-round text-[18px]">{$soundEnabled ? 'volume_up' : 'volume_off'}</span>
                        {#if !sidebarCollapsed}
                            <span class="text-[11px] font-mono tracking-widest">Sound</span>
                            <span class="ml-auto text-[10px] font-mono sidebar-text-quiet">{$soundEnabled ? 'On' : 'Off'}</span>
                        {/if}
                    </button>
                {/if}
            {/if}
        </nav>
    </div>
</aside>
