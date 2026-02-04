<script lang="ts">
    import { onMount, tick } from 'svelte';

    export let title: string;
    export let subtitle: string | null = null;
    export let icon: string | null = null;
    export let onClose: () => void;

    let containerEl: HTMLDivElement | null = null;
    const titleId = `gmp-dialog-title-${Math.random().toString(36).slice(2)}`;

    const focusableSelector =
        'a[href],button:not([disabled]),input:not([disabled]),select:not([disabled]),textarea:not([disabled]),[tabindex]:not([tabindex="-1"])';

    function getFocusableElements(): HTMLElement[] {
        if (!containerEl) return [];
        const nodes = Array.from(containerEl.querySelectorAll<HTMLElement>(focusableSelector));
        return nodes.filter((el) => {
            const style = window.getComputedStyle(el);
            if (style.visibility === 'hidden' || style.display === 'none') return false;
            if ((el as HTMLButtonElement).disabled) return false;
            return true;
        });
    }

    function focusFirst() {
        const focusables = getFocusableElements();
        (focusables[0] ?? containerEl)?.focus?.();
    }

    function handleOverlayPointerDown(e: PointerEvent) {
        if (e.target === e.currentTarget) onClose();
    }

    function handleKeydown(e: KeyboardEvent) {
        if (e.key === 'Escape') {
            e.preventDefault();
            onClose();
            return;
        }
        if (e.key !== 'Tab') return;

        const focusables = getFocusableElements();
        if (!focusables.length) {
            e.preventDefault();
            containerEl?.focus?.();
            return;
        }

        const active = document.activeElement as HTMLElement | null;
        const currentIndex = active ? focusables.indexOf(active) : -1;
        const nextIndex = e.shiftKey
            ? (currentIndex <= 0 ? focusables.length - 1 : currentIndex - 1)
            : (currentIndex === -1 || currentIndex === focusables.length - 1 ? 0 : currentIndex + 1);

        e.preventDefault();
        focusables[nextIndex]?.focus();
    }

    onMount(async () => {
        await tick();
        focusFirst();
    });
</script>

<div
    class="gmp-dialog-overlay sidebar-theme"
    role="presentation"
    on:pointerdown={handleOverlayPointerDown}
    on:keydown|capture={handleKeydown}
>
    <div
        class="gmp-dialog"
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        tabindex="-1"
        bind:this={containerEl}
    >
        <div class="gmp-dialog-titlebar">
            {#if icon}
                <span class="material-icons-round text-[18px] sidebar-icon-muted">{icon}</span>
            {/if}
            <div class="min-w-0">
                <div id={titleId} class="gmp-dialog-titlebar-title">{title}</div>
                {#if subtitle}
                    <div class="gmp-dialog-titlebar-subtitle">{subtitle}</div>
                {/if}
            </div>
            <div class="gmp-dialog-titlebar-spacer"></div>
            <button
                type="button"
                class="gmp-dialog-titlebar-btn sidebar-focusable"
                on:click={onClose}
                aria-label="Close"
                title="Close"
            >
                <span class="material-icons-round text-[18px]">close</span>
            </button>
        </div>
        <div class="gmp-dialog-body">
            <slot></slot>
        </div>
        <div class="gmp-dialog-footer">
            <slot name="footer"></slot>
        </div>
    </div>
</div>
