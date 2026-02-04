<script lang="ts">
    import { onMount, onDestroy, tick } from 'svelte';
    import {
        floatingWindowStack,
        floatingWindowPinned,
        floatingWindowActive,
        floatingWindowDock,
        bringFloatingWindowToFront,
        removeFloatingWindow,
        setFloatingWindowPinned,
        setFloatingWindowMinimized
    } from '@stores';

    export let windowKey: string;
    export let title: string;
    export let subtitle: string | null = null;
    export let icon: string | null = null;
    export let onClose: () => void;
    export let width = 560;
    export let height = 420;
    export let minWidth = 320;
    export let minHeight = 240;
    export let windowActions: Array<{ key: string; label: string; primary?: boolean; onClick?: () => void }> = [];
    export let tabs: Array<{ key: string; label: string }> = [];
    export let initialActiveTab: string | null = null;
    export let allowResize = true;
    export let allowDrag = true;
    export let activeTabKey: string | null = null;

    let containerEl: HTMLDivElement | null = null;
    let position = { x: 0, y: 0 };
    let size = { w: width, h: height };
    let dragging = false;
    let resizing = false;
    let maximized = false;
    let minimized = false;
    let previousRect: { x: number; y: number; w: number; h: number } | null = null;
    let dragStart = { x: 0, y: 0, px: 0, py: 0 };
    let resizeStart = { x: 0, y: 0, w: 0, h: 0 };
    let resizeRaf = 0;
    let persistTimer: ReturnType<typeof setTimeout> | null = null;
    let activeTab = initialActiveTab;
    let tabsState = tabs;

    const baseZ = 1200;

    $: stackIndex = $floatingWindowStack.indexOf(windowKey);
    $: pinned = Boolean($floatingWindowPinned.get(windowKey));
    $: dockIndex = $floatingWindowDock.indexOf(windowKey);
    $: zIndex = pinned ? baseZ + 999 : baseZ + Math.max(0, stackIndex + 1);
    $: if (tabs !== tabsState) tabsState = [...tabs];
    $: if (!activeTab && tabsState.length) setActiveTab(tabsState[0].key);
    $: if (activeTabKey && activeTabKey !== activeTab) setActiveTab(activeTabKey);
    $: if (activeTab && tabsState.length && !tabsState.find((tab) => tab.key === activeTab)) {
        setActiveTab(tabsState[0]?.key ?? null);
    }

    function clampPosition(x: number, y: number, w = size.w, h = size.h) {
        const maxX = Math.max(0, window.innerWidth - w);
        const maxY = Math.max(0, window.innerHeight - h);
        return {
            x: Math.min(Math.max(0, x), maxX),
            y: Math.min(Math.max(0, y), maxY)
        };
    }

    function loadPersistedPosition() {
        try {
            const raw = localStorage.getItem(`fw_pos_${windowKey}`);
            if (!raw) return null;
            const parsed = JSON.parse(raw);
            if (typeof parsed !== 'object' || parsed == null) return null;
            const { x, y, w, h } = parsed as { x?: number; y?: number; w?: number; h?: number };
            if (typeof x !== 'number' || typeof y !== 'number') return null;
            if (typeof w === 'number') size.w = Math.max(minWidth, w);
            if (typeof h === 'number') size.h = Math.max(minHeight, h);
            return clampPosition(x, y);
        } catch {
            return null;
        }
    }

    function persistPosition() {
        if (persistTimer) clearTimeout(persistTimer);
        persistTimer = setTimeout(() => {
            localStorage.setItem(
                `fw_pos_${windowKey}`,
                JSON.stringify({ x: position.x, y: position.y, w: size.w, h: size.h })
            );
        }, 300);
    }

    function setCenteredPosition() {
        const w = size.w;
        const h = size.h;
        const x = (window.innerWidth - w) / 2;
        const y = (window.innerHeight - h) / 2;
        position = clampPosition(x, y, w, h);
    }

    function handleFocus() {
        bringFloatingWindowToFront(windowKey);
    }

    function handleTitlePointerDown(event: PointerEvent) {
        if (!allowDrag || maximized || minimized) return;
        dragging = true;
        dragStart = { x: event.clientX, y: event.clientY, px: position.x, py: position.y };
        (event.currentTarget as HTMLElement).setPointerCapture(event.pointerId);
        handleFocus();
    }

    function handleTitlePointerMove(event: PointerEvent) {
        if (!dragging) return;
        const nextX = dragStart.px + (event.clientX - dragStart.x);
        const nextY = dragStart.py + (event.clientY - dragStart.y);
        position = clampPosition(nextX, nextY);
    }

    function handleTitlePointerUp() {
        if (!dragging) return;
        dragging = false;
        persistPosition();
    }

    function handleResizePointerDown(event: PointerEvent) {
        if (!allowResize || maximized || minimized) return;
        resizing = true;
        resizeStart = { x: event.clientX, y: event.clientY, w: size.w, h: size.h };
        (event.currentTarget as HTMLElement).setPointerCapture(event.pointerId);
        handleFocus();
    }

    function handleResizePointerMove(event: PointerEvent) {
        if (!resizing) return;
        if (resizeRaf) return;
        resizeRaf = requestAnimationFrame(() => {
            resizeRaf = 0;
            const nextW = Math.max(minWidth, resizeStart.w + (event.clientX - resizeStart.x));
            const nextH = Math.max(minHeight, resizeStart.h + (event.clientY - resizeStart.y));
            const clamped = clampPosition(position.x, position.y, nextW, nextH);
            size = { w: nextW, h: nextH };
            position = clamped;
        });
    }

    function handleResizePointerUp() {
        if (!resizing) return;
        resizing = false;
        persistPosition();
    }

    function toggleMaximize() {
        if (minimized) return;
        if (maximized && previousRect) {
            position = { x: previousRect.x, y: previousRect.y };
            size = { w: previousRect.w, h: previousRect.h };
            maximized = false;
            previousRect = null;
            persistPosition();
            return;
        }
        previousRect = { x: position.x, y: position.y, w: size.w, h: size.h };
        const w = Math.max(minWidth, Math.floor(window.innerWidth * 0.9));
        const h = Math.max(minHeight, Math.floor(window.innerHeight * 0.9));
        size = { w, h };
        position = clampPosition((window.innerWidth - w) / 2, (window.innerHeight - h) / 2, w, h);
        maximized = true;
        persistPosition();
    }

    function handleClose() {
        removeFloatingWindow(windowKey);
        onClose();
    }

    function toggleMinimize() {
        minimized = !minimized;
        setFloatingWindowMinimized(windowKey, minimized);
        if (!minimized) handleFocus();
    }

    function togglePin() {
        setFloatingWindowPinned(windowKey, !pinned);
    }

    function handleDockRestore() {
        minimized = false;
        setFloatingWindowMinimized(windowKey, false);
        handleFocus();
    }

    function handleKeydown(event: KeyboardEvent) {
        if (event.key !== 'Enter') return;
        const target = event.target as HTMLElement | null;
        const tag = target?.tagName?.toLowerCase();
        if (tag === 'textarea' || tag === 'input' || tag === 'select') return;
        const primary = windowActions.find((action) => action.primary);
        if (primary?.onClick) {
            event.preventDefault();
            primary.onClick();
        }
    }

    function closeTab(tabKey: string) {
        tabsState = tabsState.filter((tab) => tab.key !== tabKey);
        if (tabsState.length === 0) {
            handleClose();
            return;
        }
        if (activeTab === tabKey) setActiveTab(tabsState[0]?.key ?? null);
    }

    function setActiveTab(next: string | null) {
        if (next === activeTab) return;
        activeTab = next;
        if (activeTabKey !== next) {
            activeTabKey = next;
        }
    }

    onMount(async () => {
        await tick();
        bringFloatingWindowToFront(windowKey);
        const loaded = loadPersistedPosition();
        if (loaded) {
            position = loaded;
        } else {
            setCenteredPosition();
        }
        floatingWindowActive.set(windowKey);
        window.addEventListener('resize', setCenteredPosition);
    });

    onDestroy(() => {
        if (persistTimer) clearTimeout(persistTimer);
        removeFloatingWindow(windowKey);
        window.removeEventListener('resize', setCenteredPosition);
    });
</script>

{#if minimized}
    <button
        type="button"
        class="fw-dock-item"
        style={`left: ${Math.max(0, dockIndex) * 168 + 16}px;`}
        on:click={handleDockRestore}
    >
        {title}
    </button>
{:else}
    <div
        class="floating-window"
        style={`transform: translate3d(${position.x}px, ${position.y}px, 0); width: ${size.w}px; height: ${size.h}px; z-index: ${zIndex};`}
        on:pointerdown={handleFocus}
        on:keydown={handleKeydown}
        tabindex="0"
        role="dialog"
        aria-label={title}
        bind:this={containerEl}
    >
        <div
            class="fw-titlebar"
            on:pointerdown={handleTitlePointerDown}
            on:pointermove={handleTitlePointerMove}
            on:pointerup={handleTitlePointerUp}
            on:dblclick={toggleMaximize}
            on:keydown={(event) => {
                if (event.key === 'Enter' || event.key === ' ') {
                    event.preventDefault();
                    toggleMaximize();
                }
            }}
            role="button"
            tabindex="0"
        >
            {#if icon}
                <span class="material-icons-round fw-icon">{icon}</span>
            {/if}
            <div class="fw-titlebar-text">
                <div class="fw-title">{title}</div>
                {#if subtitle}
                    <div class="fw-subtitle">{subtitle}</div>
                {/if}
            </div>
            <div class="fw-titlebar-spacer"></div>
            <button type="button" class="fw-btn" on:click={togglePin} aria-label="Pin">
                <span class="material-icons-round fw-icon">{pinned ? 'push_pin' : 'push_pin'}</span>
            </button>
            <button type="button" class="fw-btn" on:click={toggleMinimize} aria-label="Minimize">
                <span class="material-icons-round fw-icon">remove</span>
            </button>
            <button type="button" class="fw-btn" on:click={handleClose} aria-label="Close">
                <span class="material-icons-round fw-icon">close</span>
            </button>
        </div>
        {#if tabsState.length}
            <div class="fw-tabs">
                {#each tabsState as tab (tab.key)}
                    <div
                        class={`fw-tab ${activeTab === tab.key ? 'fw-tab--active' : ''}`}
                        role="button"
                        tabindex="0"
                        on:click={() => setActiveTab(tab.key)}
                        on:keydown={(event) => {
                            if (event.key === 'Enter' || event.key === ' ') {
                                event.preventDefault();
                                setActiveTab(tab.key);
                            }
                        }}
                    >
                        <span>{tab.label}</span>
                        <button
                            type="button"
                            class="fw-tab-close"
                            on:click|stopPropagation={() => closeTab(tab.key)}
                            aria-label={`Close ${tab.label}`}
                        >
                            ×
                        </button>
                    </div>
                {/each}
            </div>
        {/if}
        <div class="fw-body">
            <slot {activeTab}></slot>
        </div>
        {#if windowActions.length}
            <div class="fw-footer">
                {#each windowActions as action (action.key)}
                    <button
                        type="button"
                        class={`fw-action ${action.primary ? 'fw-action--primary' : ''}`}
                        on:click={action.onClick}
                    >
                        {action.label}
                    </button>
                {/each}
            </div>
        {/if}
        {#if allowResize}
            <div
                class="fw-resize-handle"
                on:pointerdown={handleResizePointerDown}
                on:pointermove={handleResizePointerMove}
                on:pointerup={handleResizePointerUp}
            ></div>
        {/if}
    </div>
{/if}
