<script lang="ts">
    import { onDestroy } from 'svelte';
    import {
        systemStatus,
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
    export let expandedPanel: 'autoheal' | 'gde' | null = 'gde';
    export let activeView: 'autoheal' | 'gde' | null = null;
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
    export let onTogglePanel: (view: 'autoheal' | 'gde') => void;
    export let onToggleStatusPanel: () => void;
    export let onHover: (hover: boolean) => void;
    export let onScroll: () => void;
    export let onActivity: () => void;

    type SidebarItemId = 'status' | 'gde' | 'autoheal';
    type SidebarGroup = { id: string; title: string; items: SidebarItemId[]; collapsed?: boolean };
    type SidebarConfig = { version: number; groups: SidebarGroup[] };

    export let sidebarConfig: SidebarConfig;
    export let onMoveSidebarItem: (payload: {
        itemId: SidebarItemId;
        fromGroupId: string;
        toGroupId: string;
        toIndex: number;
    }) => void;
    export let onCreateSidebarGroup: (payload: { itemId: SidebarItemId; fromGroupId: string; title?: string }) => void;
    export let onToggleSidebarGroup: (groupId: string) => void;
    export let onResetSidebarConfig: () => void;
    export let onTidySidebarConfig: () => void;

    let toolsExpanded = false;
    let dragItemId: SidebarItemId | null = null;
    let dragFromGroupId: string | null = null;
    let dragFromIndex: number | null = null;
    let dropTarget: { groupId: string; index: number; allowed: boolean } | null = null;
    let pointerPending = false;
    let pointerDragging = false;
    let pointerId: number | null = null;
    let pointerStartX = 0;
    let pointerStartY = 0;
    let pointerLastX = 0;
    let pointerLastY = 0;
    let pointerGhostLabel = '';
    let pointerGhostX = 0;
    let pointerGhostY = 0;
    let pointerRaf: number | null = null;
    let suppressClickUntil = 0;

    const itemMeta: Record<SidebarItemId, { title: string; label: string; icon: string }> = {
        status: { title: 'Status', label: 'Status', icon: 'monitor_heart' },
        gde: { title: 'Geographic Diversity Entropy', label: 'Geographic Diversity Entropy', icon: 'diversity_3' },
        autoheal: { title: 'Autoheal', label: 'Autoheal', icon: 'build' }
    };

    $: statusSummary = `${$systemStatus} | ${formatBigNumber(totalSources)} SRC | WS ${$isConnected ? '✓' : '×'} | API ${apiOk ? '✓' : '×'}${
            apiOk && apiLatencyMs != null ? ` ${apiLatencyMs}ms` : ''
        } | STATUS AGE ${formatAgeSeconds(healthUpdatedAt, uiNow)}`;

    $: disabledClass = isOffline ? 'opacity-50 grayscale sidebar-disabled' : '';
    $: flattenedItems = sidebarConfig?.groups?.flatMap(group => group.items) ?? [];

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

    function handleItemClick(itemId: SidebarItemId) {
        if (Date.now() < suppressClickUntil) return;
        if (itemId === 'status') {
            onToggleStatusPanel();
        } else {
            onTogglePanel(itemId);
        }
        onActivity();
    }

    function handleDragStart(
        event: DragEvent,
        itemId: SidebarItemId,
        groupId: string,
        index: number
    ) {
        dragItemId = itemId;
        dragFromGroupId = groupId;
        dragFromIndex = index;
        dropTarget = null;
        event.dataTransfer?.setData('text/plain', itemId);
        if (event.dataTransfer) event.dataTransfer.effectAllowed = 'move';
    }

    function handleDragEnd() {
        stopPointerDrag();
        dragItemId = null;
        dragFromGroupId = null;
        dragFromIndex = null;
        dropTarget = null;
    }

    function isDropAllowed(groupId: string, index: number) {
        if (!dragItemId || !dragFromGroupId || dragFromIndex == null) return false;
        if (groupId === dragFromGroupId) {
            const group = sidebarConfig.groups.find(item => item.id === groupId);
            const lastIndex = group ? group.items.length : 0;
            if (index === dragFromIndex) return false;
            if (index === lastIndex && dragFromIndex === lastIndex - 1) return false;
        }
        return true;
    }

    function handleDragOver(event: DragEvent, groupId: string, index: number) {
        const allowed = isDropAllowed(groupId, index);
        dropTarget = { groupId, index, allowed };
        if (allowed) {
            event.preventDefault();
            if (event.dataTransfer) event.dataTransfer.dropEffect = 'move';
        } else if (event.dataTransfer) {
            event.dataTransfer.dropEffect = 'none';
        }
    }

    function handleDragLeave() {
        dropTarget = null;
    }

    function handleDrop(event: DragEvent, groupId: string, index: number) {
        if (!dragItemId || !dragFromGroupId) return;
        if (!isDropAllowed(groupId, index)) return;
        event.preventDefault();
        onMoveSidebarItem({
            itemId: dragItemId,
            fromGroupId: dragFromGroupId,
            toGroupId: groupId,
            toIndex: index
        });
        handleDragEnd();
        onActivity();
    }

    function handleDropNewGroup(event: DragEvent) {
        if (!dragItemId || !dragFromGroupId) return;
        event.preventDefault();
        onCreateSidebarGroup({ itemId: dragItemId, fromGroupId: dragFromGroupId });
        handleDragEnd();
        onActivity();
    }

    function stopPointerDrag() {
        if (pointerRaf != null) {
            cancelAnimationFrame(pointerRaf);
            pointerRaf = null;
        }
        if (pointerId != null) {
            window.removeEventListener('pointermove', handleGlobalPointerMove);
            window.removeEventListener('pointerup', handleGlobalPointerUp);
            window.removeEventListener('pointercancel', handleGlobalPointerUp);
        }
        window.removeEventListener('mousemove', handleGlobalMouseMove);
        window.removeEventListener('mouseup', handleGlobalMouseUp);
        window.removeEventListener('touchmove', handleGlobalTouchMove);
        window.removeEventListener('touchend', handleGlobalTouchEnd);
        window.removeEventListener('touchcancel', handleGlobalTouchEnd);
        pointerPending = false;
        pointerDragging = false;
        pointerId = null;
        pointerGhostLabel = '';
        dropTarget = null;
    }

    function getDropTargetAtPoint(x: number, y: number): { groupId: string; index: number } | null {
        const el = document.elementFromPoint(x, y) as HTMLElement | null;
        if (!el) return null;
        const itemEl = el.closest('[data-dnd-item][data-dnd-group]') as HTMLElement | null;
        if (itemEl) {
            const groupId = itemEl.dataset.dndGroup || '';
            const hoveredItemId = itemEl.dataset.dndItem as SidebarItemId | undefined;
            if (!groupId || !hoveredItemId) return null;
            const group = sidebarConfig.groups.find((g) => g.id === groupId);
            if (!group) return null;
            const idx = group.items.indexOf(hoveredItemId);
            if (idx < 0) return null;
            const rect = itemEl.getBoundingClientRect();
            const after = y >= rect.top + rect.height / 2;
            return { groupId, index: idx + (after ? 1 : 0) };
        }
        const groupEl = el.closest('[data-dnd-group]') as HTMLElement | null;
        if (groupEl) {
            const groupId = groupEl.dataset.dndGroup || '';
            if (groupId === 'new') return { groupId: 'new', index: 0 };
            const group = sidebarConfig.groups.find((g) => g.id === groupId);
            if (!group) return null;
            return { groupId, index: group.items.length };
        }
        return null;
    }

    function schedulePointerFrame() {
        if (pointerRaf != null) return;
        pointerRaf = requestAnimationFrame(() => {
            pointerRaf = null;
            if (!pointerDragging || !dragItemId || !dragFromGroupId) return;
            pointerGhostX = pointerLastX;
            pointerGhostY = pointerLastY;
            const target = getDropTargetAtPoint(pointerLastX, pointerLastY);
            if (!target) {
                dropTarget = null;
                return;
            }
            const allowed = isDropAllowed(target.groupId, target.index);
            dropTarget = { ...target, allowed };
            if (!allowed) return;
            if (target.groupId === 'new') return;
            const currentLoc = getItemLocation(dragItemId);
            if (!currentLoc) return;
            if (currentLoc.groupId === target.groupId && currentLoc.index === target.index) return;
            onMoveSidebarItem({
                itemId: dragItemId,
                fromGroupId: currentLoc.groupId,
                toGroupId: target.groupId,
                toIndex: target.index
            });
            dragFromGroupId = target.groupId;
            dragFromIndex = target.index;
            onActivity();
        });
    }

    function handleGlobalPointerMove(event: PointerEvent) {
        if (pointerId == null || event.pointerId !== pointerId) return;
        pointerLastX = event.clientX;
        pointerLastY = event.clientY;
        if (!pointerPending) return;
        if (!pointerDragging) {
            const dx = Math.abs(pointerLastX - pointerStartX);
            const dy = Math.abs(pointerLastY - pointerStartY);
            if (dx > 6 || dy > 6) {
                pointerDragging = true;
                suppressClickUntil = Date.now() + 500;
                if (navigator.vibrate) {
                    try {
                        navigator.vibrate(10);
                    } catch {
                        void 0;
                    }
                }
            }
        }
        if (pointerDragging) {
            event.preventDefault();
            schedulePointerFrame();
        }
    }

    function handleGlobalPointerUp(event: PointerEvent) {
        if (pointerId == null || event.pointerId !== pointerId) return;
        const wasDragging = pointerDragging;
        const itemId = dragItemId;
        const fromGroupId = dragFromGroupId;
        const target = dropTarget && dropTarget.allowed ? { ...dropTarget } : null;
        stopPointerDrag();
        if (!wasDragging || !itemId || !fromGroupId) return;
        if (target && target.groupId === 'new') {
            onCreateSidebarGroup({ itemId, fromGroupId });
            onActivity();
            return;
        }
        if (target && target.groupId !== 'new') {
            const loc = getItemLocation(itemId);
            const from = loc?.groupId || fromGroupId;
            onMoveSidebarItem({ itemId, fromGroupId: from, toGroupId: target.groupId, toIndex: target.index });
            onActivity();
        }
        handleDragEnd();
    }

    function handlePointerDown(event: PointerEvent, itemId: SidebarItemId, groupId: string, index: number) {
        if (event.button !== 0 && event.pointerType !== 'touch') return;
        if (event.pointerType === 'touch') event.preventDefault();
        pointerPending = true;
        pointerDragging = false;
        pointerId = event.pointerId;
        pointerStartX = event.clientX;
        pointerStartY = event.clientY;
        pointerLastX = event.clientX;
        pointerLastY = event.clientY;
        pointerGhostLabel = itemMeta[itemId]?.label || String(itemId);
        pointerGhostX = event.clientX;
        pointerGhostY = event.clientY;
        dragItemId = itemId;
        dragFromGroupId = groupId;
        dragFromIndex = index;
        dropTarget = null;
        window.addEventListener('pointermove', handleGlobalPointerMove, { passive: false });
        window.addEventListener('pointerup', handleGlobalPointerUp, { passive: false });
        window.addEventListener('pointercancel', handleGlobalPointerUp, { passive: false });
        try {
            (event.currentTarget as HTMLElement | null)?.setPointerCapture?.(event.pointerId);
        } catch {
            void 0;
        }
    }

    function handleGlobalMouseMove(event: MouseEvent) {
        pointerLastX = event.clientX;
        pointerLastY = event.clientY;
        if (!pointerPending) return;
        if (!pointerDragging) {
            const dx = Math.abs(pointerLastX - pointerStartX);
            const dy = Math.abs(pointerLastY - pointerStartY);
            if (dx > 6 || dy > 6) {
                pointerDragging = true;
                suppressClickUntil = Date.now() + 500;
            }
        }
        if (pointerDragging) {
            event.preventDefault();
            schedulePointerFrame();
        }
    }

    function handleGlobalMouseUp() {
        const wasDragging = pointerDragging;
        const itemId = dragItemId;
        const fromGroupId = dragFromGroupId;
        const target = dropTarget && dropTarget.allowed ? { ...dropTarget } : null;
        stopPointerDrag();
        if (!wasDragging || !itemId || !fromGroupId) return;
        if (target && target.groupId === 'new') {
            onCreateSidebarGroup({ itemId, fromGroupId });
            onActivity();
            return;
        }
        if (target && target.groupId !== 'new') {
            const loc = getItemLocation(itemId);
            const from = loc?.groupId || fromGroupId;
            onMoveSidebarItem({ itemId, fromGroupId: from, toGroupId: target.groupId, toIndex: target.index });
            onActivity();
        }
        handleDragEnd();
    }

    function handleMouseDown(event: MouseEvent, itemId: SidebarItemId, groupId: string, index: number) {
        if (event.button !== 0) return;
        pointerPending = true;
        pointerDragging = false;
        pointerId = null;
        pointerStartX = event.clientX;
        pointerStartY = event.clientY;
        pointerLastX = event.clientX;
        pointerLastY = event.clientY;
        pointerGhostLabel = itemMeta[itemId]?.label || String(itemId);
        pointerGhostX = event.clientX;
        pointerGhostY = event.clientY;
        dragItemId = itemId;
        dragFromGroupId = groupId;
        dragFromIndex = index;
        dropTarget = null;
        window.addEventListener('mousemove', handleGlobalMouseMove, { passive: false });
        window.addEventListener('mouseup', handleGlobalMouseUp, { passive: false });
    }

    function handleGlobalTouchMove(event: TouchEvent) {
        const t = event.touches[0];
        if (!t) return;
        pointerLastX = t.clientX;
        pointerLastY = t.clientY;
        if (!pointerPending) return;
        if (!pointerDragging) {
            const dx = Math.abs(pointerLastX - pointerStartX);
            const dy = Math.abs(pointerLastY - pointerStartY);
            if (dx > 6 || dy > 6) {
                pointerDragging = true;
                suppressClickUntil = Date.now() + 500;
            }
        }
        if (pointerDragging) {
            event.preventDefault();
            schedulePointerFrame();
        }
    }

    function handleGlobalTouchEnd(event: TouchEvent) {
        const t = event.changedTouches[0];
        if (t) {
            pointerLastX = t.clientX;
            pointerLastY = t.clientY;
        }
        const wasDragging = pointerDragging;
        const itemId = dragItemId;
        const fromGroupId = dragFromGroupId;
        const target = dropTarget && dropTarget.allowed ? { ...dropTarget } : null;
        stopPointerDrag();
        if (!wasDragging || !itemId || !fromGroupId) return;
        if (target && target.groupId === 'new') {
            onCreateSidebarGroup({ itemId, fromGroupId });
            onActivity();
            return;
        }
        if (target && target.groupId !== 'new') {
            const loc = getItemLocation(itemId);
            const from = loc?.groupId || fromGroupId;
            onMoveSidebarItem({ itemId, fromGroupId: from, toGroupId: target.groupId, toIndex: target.index });
            onActivity();
        }
        handleDragEnd();
    }

    function handleTouchStart(event: TouchEvent, itemId: SidebarItemId, groupId: string, index: number) {
        const t = event.touches[0];
        if (!t) return;
        event.preventDefault();
        pointerPending = true;
        pointerDragging = false;
        pointerId = null;
        pointerStartX = t.clientX;
        pointerStartY = t.clientY;
        pointerLastX = t.clientX;
        pointerLastY = t.clientY;
        pointerGhostLabel = itemMeta[itemId]?.label || String(itemId);
        pointerGhostX = t.clientX;
        pointerGhostY = t.clientY;
        dragItemId = itemId;
        dragFromGroupId = groupId;
        dragFromIndex = index;
        dropTarget = null;
        window.addEventListener('touchmove', handleGlobalTouchMove, { passive: false });
        window.addEventListener('touchend', handleGlobalTouchEnd, { passive: false });
        window.addEventListener('touchcancel', handleGlobalTouchEnd, { passive: false });
    }

    function getItemLocation(itemId: SidebarItemId) {
        for (const group of sidebarConfig.groups) {
            const index = group.items.indexOf(itemId);
            if (index !== -1) return { groupId: group.id, index };
        }
        return null;
    }

    function handleDragStartCollapsed(event: DragEvent, itemId: SidebarItemId) {
        const location = getItemLocation(itemId);
        if (!location) return;
        handleDragStart(event, itemId, location.groupId, location.index);
    }

    function handlePointerDownCollapsed(event: PointerEvent, itemId: SidebarItemId) {
        const location = getItemLocation(itemId);
        if (!location) return;
        handlePointerDown(event, itemId, location.groupId, location.index);
    }

    function handleMouseDownCollapsed(event: MouseEvent, itemId: SidebarItemId) {
        const location = getItemLocation(itemId);
        if (!location) return;
        handleMouseDown(event, itemId, location.groupId, location.index);
    }

    function handleTouchStartCollapsed(event: TouchEvent, itemId: SidebarItemId) {
        const location = getItemLocation(itemId);
        if (!location) return;
        handleTouchStart(event, itemId, location.groupId, location.index);
    }

    function handleDragOverCollapsed(event: DragEvent, itemId: SidebarItemId) {
        const location = getItemLocation(itemId);
        if (!location) return;
        handleDragOver(event, location.groupId, location.index);
    }

    function handleDropCollapsed(event: DragEvent, itemId: SidebarItemId) {
        const location = getItemLocation(itemId);
        if (!location) return;
        handleDrop(event, location.groupId, location.index);
    }

    function isCollapsedDropTarget(itemId: SidebarItemId) {
        const location = getItemLocation(itemId);
        if (!location || !dropTarget) return false;
        return dropTarget.groupId === location.groupId && dropTarget.index === location.index && dropTarget.allowed;
    }

    onDestroy(() => {
        stopPointerDrag();
    });
</script>

<aside
    class="absolute inset-y-0 left-0 z-[200] min-h-0 sidebar-shell sidebar-theme overflow-hidden"
    class:sidebar-dnd-dragging={pointerDragging}
    style="width: {sidebarCollapsed ? '56px' : '320px'};"
    on:mouseenter={() => onHover(true)}
    on:mouseleave={() => onHover(false)}
>
    <div class="h-full min-h-0 flex flex-col">
        <div class="h-12 px-2 flex items-center sidebar-top">
            <div class="flex items-center gap-2 min-w-0 flex-1">
                {#if sidebarCollapsed}
                    <button
                        class="w-9 h-9 rounded-[6px] flex items-center justify-center sidebar-hoverable sidebar-icon-muted sidebar-focusable"
                        on:click={onExpand}
                        title="Expand Sidebar"
                    >
                        <span class="material-icons-round text-[18px]">chevron_right</span>
                    </button>
                {:else}
                    <button
                        class="w-9 h-9 rounded-[6px] flex items-center justify-center sidebar-hoverable sidebar-icon-muted sidebar-focusable"
                        on:click={onCollapse}
                        title="Collapse Sidebar"
                    >
                        <span class="material-icons-round text-[18px]">chevron_left</span>
                    </button>
                {/if}
                {#if !sidebarCollapsed}
                    <div class="min-w-0">
                        <div class="flex items-center gap-2 min-w-0">
                            <span class="w-6 h-6 rounded-[6px] sidebar-panel-sub border sidebar-border flex items-center justify-center sidebar-text shrink-0">
                                <span class="material-icons-round text-[16px]">public</span>
                            </span>
                            <div class="text-xs font-semibold tracking-wide truncate sidebar-text">Globe Media Pulse</div>
                        </div>
                    </div>
                {/if}
            </div>
        </div>

        <nav class="flex-1 min-h-0 overflow-y-auto px-1 py-2 flex flex-col gap-1" on:scroll={onScroll}>
            {#if sidebarCollapsed}
                {#each flattenedItems as itemId (itemId)}
                    {#if itemId === 'status'}
                        <button
                            type="button"
                            class={`rounded-[6px] flex items-center gap-2 px-2 sidebar-panel border sidebar-border min-w-0 overflow-hidden h-10 justify-center sidebar-focusable ${statusPanelExpanded ? 'sidebar-active' : ''}`}
                            title={statusSummary}
                            on:click={() => handleItemClick(itemId)}
                            aria-expanded={statusPanelExpanded}
                            draggable
                            aria-grabbed={dragItemId === itemId}
                            data-testid="sidebar-item-status"
                            data-dnd-item={itemId}
                            data-dnd-group={getItemLocation(itemId)?.groupId || 'core'}
                            on:dragstart={(event) => handleDragStartCollapsed(event, itemId)}
                            on:dragend={handleDragEnd}
                            on:dragover={(event) => handleDragOverCollapsed(event, itemId)}
                            on:dragleave={handleDragLeave}
                            on:drop={(event) => handleDropCollapsed(event, itemId)}
                            on:pointerdown={(event) => handlePointerDownCollapsed(event, itemId)}
                            on:mousedown={(event) => handleMouseDownCollapsed(event, itemId)}
                            on:touchstart={(event) => handleTouchStartCollapsed(event, itemId)}
                            class:sidebar-drop-shadow={isCollapsedDropTarget(itemId)}
                        >
                            <span class="w-2 h-2 rounded-full {getSystemDotClass($systemStatus)}"></span>
                            <span class="material-icons-round text-[18px] {getSystemIconClass($systemStatus)}">monitor_heart</span>
                        </button>
                    {:else}
                        <button
                            class="relative h-10 rounded-[6px] flex items-center gap-2 px-2 sidebar-hoverable border sidebar-border sidebar-focusable bg-transparent justify-center"
                            on:click={() => handleItemClick(itemId)}
                            title={itemMeta[itemId].title}
                            draggable
                            aria-grabbed={dragItemId === itemId}
                            data-testid={`sidebar-item-${itemId}`}
                            data-dnd-item={itemId}
                            data-dnd-group={getItemLocation(itemId)?.groupId || 'core'}
                            on:dragstart={(event) => handleDragStartCollapsed(event, itemId)}
                            on:dragend={handleDragEnd}
                            on:dragover={(event) => handleDragOverCollapsed(event, itemId)}
                            on:dragleave={handleDragLeave}
                            on:drop={(event) => handleDropCollapsed(event, itemId)}
                            on:pointerdown={(event) => handlePointerDownCollapsed(event, itemId)}
                            on:mousedown={(event) => handleMouseDownCollapsed(event, itemId)}
                            on:touchstart={(event) => handleTouchStartCollapsed(event, itemId)}
                            class:sidebar-drop-shadow={isCollapsedDropTarget(itemId)}
                        >
                            {#if activeView === itemId}
                                <span class="absolute left-0 top-1.5 bottom-1.5 w-[2px] rounded-full sidebar-indicator"></span>
                            {/if}
                            {#if activeView === itemId}
                                <span class="absolute bottom-1 left-1/2 -translate-x-1/2 w-1.5 h-1.5 rounded-full sidebar-indicator"></span>
                            {/if}
                            <span class="material-icons-round text-[18px] {activeView === itemId ? 'sidebar-text' : 'sidebar-text-muted'}">
                                {itemMeta[itemId].icon}
                            </span>
                        </button>
                    {/if}
                {/each}
            {:else}
                <div class="flex flex-col gap-2">
                    {#each sidebarConfig.groups as group (group.id)}
                        <div
                            class="mx-1 px-2 py-1 rounded-[6px] sidebar-panel-sub border sidebar-border text-[10px] font-mono tracking-widest sidebar-text-muted flex items-center gap-2"
                            data-testid={`sidebar-group-${group.id}`}
                            role="listitem"
                            data-dnd-group={group.id}
                            on:dragover={(event) => handleDragOver(event, group.id, group.items.length)}
                            on:dragleave={handleDragLeave}
                            on:drop={(event) => handleDrop(event, group.id, group.items.length)}
                            class:sidebar-drop-shadow={dropTarget && dropTarget.groupId === group.id && dropTarget.index === group.items.length && dropTarget.allowed}
                        >
                            <button
                                type="button"
                                class="w-5 h-5 rounded-[4px] flex items-center justify-center sidebar-hoverable sidebar-focusable"
                                on:click={() => { onToggleSidebarGroup(group.id); onActivity(); }}
                                aria-expanded={!group.collapsed}
                            >
                                <span class="material-icons-round text-[14px] sidebar-icon-muted">
                                    {group.collapsed ? 'chevron_right' : 'expand_more'}
                                </span>
                            </button>
                            <span>{group.title}</span>
                            {#if dropTarget && dropTarget.groupId === group.id && dropTarget.index === group.items.length && !dropTarget.allowed}
                                <span class="ml-auto material-icons-round text-[14px] sidebar-drop-disabled">block</span>
                            {/if}
                        </div>
                        {#if !group.collapsed}
                            <div class="flex flex-col gap-1">
                                {#each group.items as itemId, index (itemId)}
                                    {#if itemId === 'status'}
                                        <button
                                            type="button"
                                            class={`mx-1 h-10 rounded-[6px] px-2 sidebar-panel border sidebar-border text-[11px] sidebar-text flex items-center gap-2 sidebar-hoverable sidebar-focusable ${statusPanelExpanded ? 'sidebar-active' : ''}`}
                                            on:click={() => handleItemClick(itemId)}
                                            title={statusSummary}
                                            aria-expanded={statusPanelExpanded}
                                            draggable
                                            aria-grabbed={dragItemId === itemId}
                                            data-testid="sidebar-item-status"
                                            data-dnd-item={itemId}
                                            data-dnd-group={group.id}
                                            on:dragstart={(event) => handleDragStart(event, itemId, group.id, index)}
                                            on:dragend={handleDragEnd}
                                            on:dragover={(event) => handleDragOver(event, group.id, index)}
                                            on:dragleave={handleDragLeave}
                                            on:drop={(event) => handleDrop(event, group.id, index)}
                                            on:pointerdown={(event) => handlePointerDown(event, itemId, group.id, index)}
                                            on:mousedown={(event) => handleMouseDown(event, itemId, group.id, index)}
                                            on:touchstart={(event) => handleTouchStart(event, itemId, group.id, index)}
                                            class:sidebar-drop-shadow={dropTarget && dropTarget.groupId === group.id && dropTarget.index === index && dropTarget.allowed}
                                        >
                                            <span class="w-2 h-2 rounded-full {getSystemDotClass($systemStatus)}"></span>
                                            <span class="material-icons-round text-[18px] {getSystemIconClass($systemStatus)}">monitor_heart</span>
                                            <span class="text-[11px] font-mono tracking-widest sidebar-text truncate">Status</span>
                                            <span class="ml-auto text-[10px] font-mono sidebar-text-quiet">{$systemStatus}</span>
                                        </button>
                                    {:else}
                                        <button
                                            class={`relative h-10 rounded-[6px] flex items-center gap-2 px-2 sidebar-hoverable border sidebar-border sidebar-focusable mx-1 ${activeView === itemId ? 'sidebar-active' : 'bg-transparent'}`}
                                            on:click={() => handleItemClick(itemId)}
                                            title={itemMeta[itemId].title}
                                            draggable
                                            aria-grabbed={dragItemId === itemId}
                                            data-testid={`sidebar-item-${itemId}`}
                                            data-dnd-item={itemId}
                                            data-dnd-group={group.id}
                                            on:dragstart={(event) => handleDragStart(event, itemId, group.id, index)}
                                            on:dragend={handleDragEnd}
                                            on:dragover={(event) => handleDragOver(event, group.id, index)}
                                            on:dragleave={handleDragLeave}
                                            on:drop={(event) => handleDrop(event, group.id, index)}
                                            on:pointerdown={(event) => handlePointerDown(event, itemId, group.id, index)}
                                            on:mousedown={(event) => handleMouseDown(event, itemId, group.id, index)}
                                            on:touchstart={(event) => handleTouchStart(event, itemId, group.id, index)}
                                            class:sidebar-drop-shadow={dropTarget && dropTarget.groupId === group.id && dropTarget.index === index && dropTarget.allowed}
                                        >
                                            {#if activeView === itemId}
                                                <span class="absolute left-0 top-1.5 bottom-1.5 w-[2px] rounded-full sidebar-indicator"></span>
                                            {/if}
                                            <span class="material-icons-round text-[18px] {activeView === itemId ? 'sidebar-text' : 'sidebar-text-muted'}">
                                                {itemMeta[itemId].icon}
                                            </span>
                                            <span class="text-[11px] font-mono tracking-widest sidebar-text truncate">{itemMeta[itemId].label}</span>
                                            {#if expandedPanel === itemId}
                                                <span class="ml-auto w-2 h-2 rounded-full sidebar-indicator"></span>
                                            {/if}
                                            {#if dropTarget && dropTarget.groupId === group.id && dropTarget.index === index && !dropTarget.allowed}
                                                <span class="ml-auto material-icons-round text-[14px] sidebar-drop-disabled">block</span>
                                            {/if}
                                        </button>
                                    {/if}
                                {/each}
                            </div>
                        {/if}
                    {/each}
                    <button
                        type="button"
                        class="mx-1 px-2 py-1 rounded-[6px] sidebar-panel border sidebar-border text-[10px] font-mono font-semibold tracking-widest sidebar-text-muted flex items-center gap-1.5 sidebar-focusable sidebar-hoverable"
                        on:click={() => { onResetSidebarConfig(); onActivity(); }}
                        data-testid="sidebar-reset"
                    >
                        <span class="material-icons-round text-[14px] sidebar-icon-muted">restart_alt</span>
                        <span>Reset Default</span>
                    </button>
                    <button
                        type="button"
                        class="mx-1 px-2 py-1 rounded-[6px] sidebar-panel border sidebar-border text-[10px] font-mono font-semibold tracking-widest sidebar-text-muted flex items-center gap-1.5 sidebar-focusable sidebar-hoverable"
                        on:click={() => { onTidySidebarConfig(); onActivity(); }}
                        data-testid="sidebar-tidy"
                    >
                        <span class="material-icons-round text-[14px] sidebar-icon-muted">auto_fix_high</span>
                        <span>Auto Tidy</span>
                    </button>
                    <div
                        class="mx-1 px-2 py-2 rounded-[6px] sidebar-panel-sub border sidebar-border text-[10px] font-mono tracking-widest sidebar-text-muted flex items-center gap-2 sidebar-drop-zone"
                        role="listitem"
                        data-dnd-group="new"
                        on:dragover={(event) => handleDragOver(event, 'new', 0)}
                        on:dragleave={handleDragLeave}
                        on:drop={handleDropNewGroup}
                        data-testid="sidebar-new-group"
                        class:sidebar-drop-shadow={dropTarget && dropTarget.groupId === 'new' && dropTarget.allowed}
                    >
                        <span class="material-icons-round text-[14px] sidebar-icon-muted">add</span>
                        <span>New Group</span>
                        {#if dropTarget && dropTarget.groupId === 'new' && !dropTarget.allowed}
                            <span class="ml-auto material-icons-round text-[14px] sidebar-drop-disabled">block</span>
                        {/if}
                    </div>
                </div>
            {/if}

            <!-- Tools Section -->
            {#if !sidebarCollapsed}
                <div class="h-px sidebar-divider mx-1 my-2"></div>
                <button
                    type="button"
                    class="mx-1 px-2 py-1 rounded-[6px] sidebar-panel border sidebar-border text-[10px] font-mono font-semibold tracking-widest sidebar-text-muted flex items-center gap-1.5 sidebar-focusable"
                    on:click={() => { toolsExpanded = !toolsExpanded; onActivity(); }}
                >
                    <span class="material-icons-round text-[14px] sidebar-icon-muted">handyman</span><span>Tools</span>
                    <span class="ml-auto flex items-center gap-1.5">
                        <span class="px-1.5 py-0.5 rounded-[6px] sidebar-panel-sub border sidebar-border text-[9px] font-mono tracking-widest sidebar-text-quiet">System</span>
                        {#if isSystemCritical}
                            <span class={`px-1.5 py-0.5 rounded-[6px] border sidebar-panel-sub text-[10px] font-mono tracking-widest ${getSystemSlotClass($systemStatus)}`}>{$systemStatus}</span>
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
                        class="h-10 rounded-[6px] flex items-center gap-2 px-2 sidebar-hoverable border sidebar-border sidebar-text-muted sidebar-focusable {disabledClass}"
                        class:justify-center={sidebarCollapsed}
                        on:click={() => emitMapCommandWithActivity('export_png_1200')}
                        title="Export PNG (1200 DPI)"
                        disabled={isOffline}
                    >
                        <span class="material-icons-round text-[18px]">image</span>
                        {#if !sidebarCollapsed}
                            <span class="text-[11px] font-mono tracking-widest">Export PNG</span>
                            <span class="ml-auto text-[10px] font-mono sidebar-text-quiet">1200 DPI</span>
                        {/if}
                    </button>

                    <button
                        class="h-10 rounded-[6px] flex items-center gap-2 px-2 sidebar-hoverable border sidebar-border sidebar-text-muted sidebar-focusable {disabledClass}"
                        class:justify-center={sidebarCollapsed}
                        on:click={() => emitMapCommandWithActivity('export_svg_1200')}
                        title="Export SVG"
                        disabled={isOffline}
                    >
                        <span class="material-icons-round text-[18px]">schema</span>
                        {#if !sidebarCollapsed}
                            <span class="text-[11px] font-mono tracking-widest">Export SVG</span>
                            <span class="ml-auto text-[10px] font-mono sidebar-text-quiet">Vector</span>
                        {/if}
                    </button>

                    <button
                        class="h-10 rounded-[6px] flex items-center gap-2 px-2 sidebar-hoverable border sidebar-border sidebar-text-muted sidebar-focusable {disabledClass}"
                        class:justify-center={sidebarCollapsed}
                        on:click={() => emitMapCommandWithActivity('reset_view')}
                        title="Reset View"
                        disabled={isOffline}
                    >
                        <span class="material-icons-round text-[18px]">my_location</span>
                        {#if !sidebarCollapsed}
                            <span class="text-[11px] font-mono tracking-widest">Reset View</span>
                        {/if}
                    </button>

                    <button
                        class="h-10 rounded-[6px] flex items-center gap-2 px-2 sidebar-hoverable border sidebar-border sidebar-text-muted sidebar-focusable"
                        class:justify-center={sidebarCollapsed}
                        on:click={toggleSoundWithActivity}
                        title={$soundEnabled ? 'Sound: On' : 'Sound: Off'}
                        aria-pressed={$soundEnabled}
                        disabled={isOffline}
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

{#if pointerDragging}
    <div
        class="sidebar-drag-ghost sidebar-panel border sidebar-border"
        style="transform: translate3d({pointerGhostX + 10}px, {pointerGhostY + 10}px, 0);"
        aria-hidden="true"
    >
        <span class="material-icons-round text-[18px] sidebar-text-muted">{dragItemId ? itemMeta[dragItemId].icon : 'drag_indicator'}</span>
        <span class="text-[11px] font-mono tracking-widest sidebar-text truncate">{pointerGhostLabel}</span>
    </div>
{/if}
