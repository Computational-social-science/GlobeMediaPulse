<script>
    import { isPaused, isPlaying, playbackSpeed, windowState, mapMode, gameStats, soundEnabled, heatmapEnabled, is3DMode, timeScale, simulationDate, serviceStatus } from '../stores.js';
    import { onMount, onDestroy } from 'svelte';
    
    // Windows configuration definitions
    const windows = [
        { id: 'feed', icon: '📡', label: 'UPLINK' },
        { id: 'timeline', icon: '⏱', label: 'TEMPORAL' },
        { id: 'countries', icon: '🌍', label: 'REGIONAL' },
        { id: 'corpus', icon: '🔬', label: 'RESEARCH' }
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
            if (win.visible && !win.minimized) {
                // If focused/open, minimize it
                win.minimized = true;
            } else {
                // Open if closed, or restore if minimized
                win.visible = true;
                win.minimized = false;
            }
            return { ...state, [id]: win };
        });
    }

    // --- Time Scrubber Logic ---
    /** @type {number} */
    let min = 0;
    /** @type {number} */
    let max = 100;
    /** @type {number} */
    let step = 1;
    /** @type {number} */
    let value = 0;
    /** @type {string} */
    let label = '';

    // Redis status check for real-time features
    $: isRedisDown = $serviceStatus.redis !== 'ok' && $serviceStatus.redis !== 'unknown';

    // Reactively update slider configuration based on timeScale and simulationDate
    $: {
        const date = new Date($simulationDate);
        const now = new Date();
        const currentYear = now.getFullYear();
        
        if ($timeScale === 'overview') {
            // Overview Mode: 2017 to Current Year (Full History)
            min = 2017;
            max = currentYear;
            step = 1;
            value = date.getFullYear();
            label = `${value}`;
        } else if ($timeScale === 'year') {
            // Year Mode: 2017 to Last Year (Historical Analysis)
            min = 2017;
            max = currentYear - 1;
            step = 1;
            value = date.getFullYear();
            
            // Auto-snap to valid range if switching from Live/Overview
            if (value > max) {
                 const d = new Date(date);
                 d.setFullYear(max);
                 simulationDate.set(d);
                 value = max;
            }
            
            label = `${value}`;
        } else if ($timeScale === 'live') {
            // Live Mode: Jan to Current Month of Current Year
            min = 1;
            max = now.getMonth() + 1; // 0-11 -> 1-12
            step = 1;
            value = date.getMonth() + 1; // 0-11 -> 1-12
            
            // Auto-lock to current year if not already
            if (date.getFullYear() !== currentYear) {
                const d = new Date(date);
                d.setFullYear(currentYear);
                simulationDate.set(d);
            }
            
            label = date.toLocaleString('en-US', { month: 'short' }) + ' (LIVE)';
        }
    }

    /** 
     * Handles slider input changes to update simulation time.
     * @param {Event} e 
     */
    function handleInput(e) {
        // @ts-ignore
        const val = parseInt(e.target.value);
        const d = new Date($simulationDate);
        
        if ($timeScale === 'overview' || $timeScale === 'year') {
            d.setFullYear(val);
        } else if ($timeScale === 'live') {
            d.setMonth(val - 1); // 1-12 -> 0-11
        }
        
        simulationDate.set(d);
    }
    
    // --- System Status Logic ---
    // [FROZEN] Global Health Check Linkage Logic
    export let systemStatus = 'OFFLINE';
    
    // Only block interactions if OFFLINE. DEGRADED is strictly a visual warning.
    $: isOffline = systemStatus === 'OFFLINE';
    $: statusColor = systemStatus === 'ONLINE' ? 'emerald' : (systemStatus === 'DEGRADED' ? 'yellow' : 'red');
    $: statusText = systemStatus === 'ONLINE' ? 'SYSTEM ONLINE' : (systemStatus === 'DEGRADED' ? 'SYSTEM DEGRADED' : 'SYSTEM OFFLINE');

    $: disabledClass = isOffline ? 'opacity-50 pointer-events-none grayscale' : '';
    
    /** @param {string} scale */
    function setTimeScale(scale) {
        // @ts-ignore
        $timeScale = scale;
    }

    // --- Auto-Play Logic ---
    function togglePlay() {
        $isPlaying = !$isPlaying;
    }
    
    // --- Auto-Hide Logic ---
    let isIdle = false;
    /** @type {any} */
    let idleTimer;

    function resetIdleTimer() {
        isIdle = false;
        clearTimeout(idleTimer);
        idleTimer = setTimeout(() => {
            if (!$isPlaying) { 
                 // If paused, hide after timeout
                 isIdle = true;
            } else {
                 // If playing, also hide to avoid clutter
                 isIdle = true;
            }
        }, 60000); // 60 seconds timeout
    }
    
    onMount(() => {
        window.addEventListener('mousemove', resetIdleTimer);
        window.addEventListener('keydown', resetIdleTimer);
        window.addEventListener('click', resetIdleTimer);
        resetIdleTimer(); // Start timer
        
        return () => {
            window.removeEventListener('mousemove', resetIdleTimer);
            window.removeEventListener('keydown', resetIdleTimer);
            window.removeEventListener('click', resetIdleTimer);
            clearTimeout(idleTimer);
        };
    });

    onDestroy(() => {
        // No local cleanup needed for stores
    });
</script>

<div class="fixed bottom-6 left-1/2 -translate-x-1/2 z-50 pointer-events-auto select-none flex flex-col items-center gap-2 transition-all duration-700 ease-in-out {isIdle ? 'translate-y-[150%] opacity-0 pointer-events-none' : 'translate-y-0 opacity-100'}">
    <!-- Main Console Container -->
    <!-- Optimized Background: Richer dark blue (Slate-900 base), higher opacity, stronger border and shadow for better contrast against dark map -->
    <div class="h-14 px-4 bg-[#0f172a]/85 backdrop-blur-md rounded-full border border-white/25 shadow-[0_8px_32px_rgba(0,0,0,0.5),inset_0_0_20px_rgba(255,255,255,0.08)] flex items-center gap-4 relative overflow-visible group transition-all duration-500 hover:bg-[#0f172a]/95">
        
        <!-- Ambient Glow -->
        <div class="absolute inset-0 bg-gradient-to-r from-neon-blue/20 via-transparent to-neon-pink/20 pointer-events-none rounded-full blur-md opacity-50 group-hover:opacity-80 transition-opacity"></div>
        
        <!-- FAR LEFT: SYSTEM STATUS -->
        <div class="flex items-center gap-1 bg-white/10 rounded-full p-0.5 border border-white/10" title="System Status: {systemStatus}">
            <div class="h-7 px-2 rounded-full flex items-center gap-1.5 justify-center">
                {#if systemStatus === 'OFFLINE'}
                    <div class="w-1.5 h-1.5 rounded-full bg-red-500 shadow-[0_0_8px_rgba(239,68,68,0.8)] animate-pulse"></div>
                    <span class="text-[10px] font-mono text-red-500/80 font-bold tracking-wider">OFFLINE</span>
                {:else if systemStatus === 'DEGRADED'}
                    <div class="w-1.5 h-1.5 rounded-full bg-yellow-500 shadow-[0_0_8px_rgba(234,179,8,0.8)] animate-pulse"></div>
                    <span class="text-[10px] font-mono text-yellow-500/80 font-bold tracking-wider">DEGRADED</span>
                {:else}
                    <div class="w-1.5 h-1.5 rounded-full bg-emerald-500 shadow-[0_0_8px_rgba(16,185,129,0.8)] animate-pulse"></div>
                    <span class="text-[10px] font-mono text-emerald-500/80 font-bold tracking-wider">ONLINE</span>
                {/if}
            </div>
        </div>
        
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

        <!-- CENTER SECTION: TIMELINE CONTROLS (Merged Pill) -->
        <div class="flex items-center gap-2 justify-center">
            <!-- Unified Timeline Pill -->
            <div class="flex items-center gap-1.5 bg-white/10 rounded-full p-0.5 border border-white/10 pr-2.5">
                <!-- Mode Toggles -->
                <div class="flex items-center gap-1">
                    <button class="px-2 h-7 text-[10px] font-bold rounded-full transition-colors {isRedisDown ? 'text-gray-600 cursor-not-allowed' : 'hover:bg-white/10'} {$timeScale === 'live' && !isRedisDown ? 'text-neon-pink bg-white/10 shadow-[0_0_10px_rgba(255,0,128,0.2)]' : (!isRedisDown ? 'text-gray-400 hover:text-gray-200' : '')}"
                        disabled={isRedisDown}
                        title={isRedisDown ? "Real-time unavailable (Redis Service Down)" : "Switch to Live Mode"}
                        on:click={() => setTimeScale('live')}>
                        LIVE
                    </button>
                    <button class="px-2 h-7 text-[10px] font-bold rounded-full hover:bg-white/10 transition-colors {$timeScale === 'year' ? 'text-neon-blue bg-white/10 shadow-[0_0_10px_rgba(0,243,255,0.1)]' : 'text-gray-400 hover:text-gray-200'}"
                        on:click={() => setTimeScale('year')}>
                        YEAR
                    </button>
                    <button class="px-2 h-7 text-[10px] font-bold rounded-full hover:bg-white/10 transition-colors {$timeScale === 'overview' ? 'text-neon-blue bg-white/10 shadow-[0_0_10px_rgba(0,243,255,0.1)]' : 'text-gray-400 hover:text-gray-200'}"
                        on:click={() => setTimeScale('overview')}>
                        OVERVIEW
                    </button>
                </div>

                <!-- Vertical Divider inside Pill -->
                <div class="w-[1px] h-4 bg-white/15"></div>

                <!-- Embedded Scrubber -->
                <div class="flex items-center gap-1.5 w-24 relative group/scrubber">
                    <span class="text-[9px] font-mono text-neon-blue/70 w-6 text-right">{min}</span>
                    <div class="relative flex-1 h-4 flex items-center">
                        <input 
                            type="range" 
                            {min} 
                            {max} 
                            {step} 
                            {value} 
                            on:input={handleInput}
                            class="w-full h-1 bg-white/20 rounded-lg appearance-none cursor-pointer focus:outline-none z-10
                            [&::-webkit-slider-thumb]:appearance-none [&::-webkit-slider-thumb]:w-2.5 [&::-webkit-slider-thumb]:h-2.5 [&::-webkit-slider-thumb]:bg-neon-blue [&::-webkit-slider-thumb]:rounded-full [&::-webkit-slider-thumb]:shadow-[0_0_6px_rgba(0,243,255,0.8)] [&::-webkit-slider-thumb]:transition-transform [&::-webkit-slider-thumb]:hover:scale-125"
                        />
                        <!-- Value Tooltip -->
                        <div class="absolute -top-7 left-1/2 -translate-x-1/2 -ml-[calc(50%-var(--thumb-pos))] text-neon-blue font-mono font-bold text-[10px] bg-black/80 px-1.5 py-0.5 rounded border border-neon-blue/30 opacity-0 group-hover/scrubber:opacity-100 transition-opacity pointer-events-none whitespace-nowrap">
                            {label}
                        </div>
                    </div>
                    <span class="text-[9px] font-mono text-neon-blue/70 w-6">{max}</span>
                </div>
            </div>

            <!-- Playback Controls Group -->
            <div class="flex items-center gap-1 bg-white/10 rounded-full p-0.5 border border-white/10">
                <!-- Play Button -->
                <button 
                    class="w-7 h-7 rounded-full flex items-center justify-center transition-all duration-300 relative group/btn
                    {$isPlaying ? 'bg-neon-pink/20 text-neon-pink shadow-[0_0_10px_rgba(255,0,128,0.2)] border border-neon-pink/30' : 'text-gray-400 hover:text-white hover:bg-white/10 border border-transparent'}"
                    on:click={togglePlay}
                    title={$isPlaying ? "Pause" : "Play"}
                >
                    <span class="material-icons-round text-base relative z-10">{$isPlaying ? 'pause' : 'play_arrow'}</span>
                </button>

                <!-- Speed Controls -->
                <button 
                    class="h-6 px-1.5 rounded-full flex items-center justify-center text-neon-blue font-mono font-bold text-[10px] hover:bg-white/10 transition-all border border-transparent hover:border-white/10"
                    on:click={() => {
                        if ($playbackSpeed === 1) $playbackSpeed = 2;
                        else if ($playbackSpeed === 2) $playbackSpeed = 5;
                        else $playbackSpeed = 1;
                    }}
                    title="Playback Speed"
                >
                    {$playbackSpeed}x
                </button>
            </div>
        </div>

        <!-- DIVIDER -->
        <div class="w-[1px] h-6 bg-white/15"></div>

        <!-- RIGHT SECTION: 3D & STATUS -->
        <div class="flex items-center gap-1 {disabledClass}">
             <!-- Sound Toggle -->
             <button 
                class="w-7 h-7 rounded-full flex items-center justify-center transition-all duration-300 relative group/btn
                {$soundEnabled ? 'text-neon-blue shadow-[0_0_15px_rgba(0,243,255,0.2)]' : 'text-gray-400 hover:text-white hover:bg-white/10'}"
                on:click={() => $soundEnabled = !$soundEnabled}
                title={$soundEnabled ? "Mute Sound" : "Enable Sound"}
            >
                <span class="material-icons-round text-lg relative z-10">{$soundEnabled ? 'volume_up' : 'volume_off'}</span>
            </button>

             <!-- 3D Toggle -->
             <button 
                class="w-7 h-7 rounded-full flex items-center justify-center transition-all duration-300 relative group/btn
                {$is3DMode ? 'bg-white/10 text-neon-blue shadow-[0_0_15px_rgba(0,243,255,0.2)] border border-neon-blue/30' : 'text-gray-400 hover:text-white hover:bg-white/10 border border-transparent hover:border-white/10'}"
                on:click={() => $is3DMode = !$is3DMode}
                title="Toggle 3D Mode"
            >
                <span class="material-icons-round text-lg relative z-10">view_in_ar</span>
            </button>
        </div>

    </div>
</div>

<style>
    /* No custom input styles needed as we use a custom visual thumb */
</style>
