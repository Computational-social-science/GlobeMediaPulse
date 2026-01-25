<script>
    import { windowState, mapMode, soundEnabled, heatmapEnabled, serviceStatus } from '../stores.js';
    import { onMount, onDestroy } from 'svelte';
    
    // Windows configuration definitions
    const windows = [
        { id: 'brain', icon: '🧠', label: 'BRAIN' }
    ];

    /** 
     * Toggles the visibility or state of a window.
     * @param {string} id - The window identifier.
     */
    function toggleWindow(id) {
        windowState.update(s => {
            /** @type {any} */
            const state = s;
            const win = state[id];
            
            // Simple Toggle Logic: Open if closed, Close if open
            if (win && win.visible) {
                win.visible = false;
            } else if (win) {
                win.visible = true;
                win.minimized = false;
            }
            
            return { ...state, [id]: win };
        });
    }

    // --- System Status Logic ---
    // [FROZEN] Global Health Check Linkage Logic
    export let systemStatus = 'OFFLINE';
    
    // Only block interactions if OFFLINE. DEGRADED is strictly a visual warning.
    $: isOffline = systemStatus === 'OFFLINE';
    $: statusColor = systemStatus === 'ONLINE' ? 'emerald' : (systemStatus === 'DEGRADED' ? 'yellow' : 'red');
    $: statusText = systemStatus === 'ONLINE' ? 'SYSTEM ONLINE' : (systemStatus === 'DEGRADED' ? 'SYSTEM DEGRADED' : 'SYSTEM OFFLINE');

    $: disabledClass = isOffline ? 'opacity-50 pointer-events-none grayscale' : '';
    
    function toggleSound() {
        $soundEnabled = !$soundEnabled;
    }
</script>

<div class="fixed bottom-6 left-1/2 -translate-x-1/2 z-50 pointer-events-auto select-none flex flex-col items-center gap-2 transition-all duration-700 ease-in-out">
    <!-- Main Console Container -->
    <!-- Optimized Background: Richer dark blue (Slate-900 base), higher opacity, stronger border and shadow for better contrast against dark map -->
    <div class="h-14 px-4 bg-[#0f172a]/85 backdrop-blur-md rounded-full border border-white/25 shadow-[0_8px_32px_rgba(0,0,0,0.5),inset_0_0_20px_rgba(255,255,255,0.08)] flex items-center gap-4 relative overflow-visible group transition-all duration-500 hover:bg-[#0f172a]/95">
        
        <!-- Ambient Glow -->
        <div class="absolute inset-0 bg-gradient-to-r from-neon-blue/20 via-transparent to-neon-pink/20 pointer-events-none rounded-full blur-md opacity-50 group-hover:opacity-80 transition-opacity"></div>
        
        <!-- FAR LEFT: SYSTEM STATUS -->
        <button 
            class="flex items-center gap-1 bg-white/10 rounded-full p-0.5 border border-white/10 hover:bg-white/20 hover:border-white/30 transition-all cursor-pointer group"
            title="Toggle System Monitor"
            on:click={() => toggleWindow('systemMonitor')}
        >
            <div class="h-7 px-2 rounded-full flex items-center gap-1.5 justify-center">
                {#if systemStatus === 'OFFLINE'}
                    <div class="w-1.5 h-1.5 rounded-full bg-red-500 shadow-[0_0_8px_rgba(239,68,68,0.8)] animate-pulse"></div>
                    <span class="text-[10px] font-mono text-red-500/80 font-bold tracking-wider group-hover:text-red-400">OFFLINE</span>
                {:else if systemStatus === 'DEGRADED'}
                    <div class="w-1.5 h-1.5 rounded-full bg-yellow-500 shadow-[0_0_8px_rgba(234,179,8,0.8)] animate-pulse"></div>
                    <span class="text-[10px] font-mono text-yellow-500/80 font-bold tracking-wider group-hover:text-yellow-400">DEGRADED</span>
                {:else}
                    <div class="w-1.5 h-1.5 rounded-full bg-emerald-500 shadow-[0_0_8px_rgba(16,185,129,0.8)] animate-pulse"></div>
                    <span class="text-[10px] font-mono text-emerald-500/80 font-bold tracking-wider group-hover:text-emerald-400">ONLINE</span>
                {/if}
            </div>
        </button>
        
        <!-- DIVIDER -->
        <div class="w-[1px] h-6 bg-white/10"></div>

        <!-- LEFT SECTION: WINDOW CONTROLS -->
        <div class="flex items-center gap-1 {disabledClass}">
            {#each windows as win}
                <button 
                    class="w-7 h-7 rounded-full flex items-center justify-center transition-all duration-300 relative group/btn 
                    {$windowState[win.id]?.visible && !$windowState[win.id]?.minimized ? 'bg-white/10 text-neon-blue shadow-[0_0_15px_rgba(0,243,255,0.2)] border border-neon-blue/30' : 'text-gray-400 hover:text-white hover:bg-white/10 border border-transparent hover:border-white/10'}"
                    on:click={() => toggleWindow(win.id)}
                    title={win.label}
                >
                    <span class="material-icons-round text-lg relative z-10">{win.icon}</span>
                </button>
            {/each}
        </div>

        <!-- DIVIDER -->
        <div class="w-[1px] h-6 bg-white/15"></div>

        <!-- RIGHT SECTION: SOUND -->
        <div class="flex items-center gap-1 {disabledClass}">
             <!-- Sound Toggle -->
             <button 
                class="w-7 h-7 rounded-full flex items-center justify-center transition-all duration-300 relative group/btn
                {$soundEnabled ? 'text-neon-blue' : 'text-gray-500'}"
                on:click={toggleSound}
                title="Toggle Sound"
            >
                <span class="material-icons-round text-lg relative z-10">{$soundEnabled ? 'volume_up' : 'volume_off'}</span>
            </button>
        </div>
    </div>
</div>
