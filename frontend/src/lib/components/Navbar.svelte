<script>
    import { onMount } from 'svelte';
    import { windowState } from '../stores.js';
    
    let time = new Date().toLocaleTimeString();

    onMount(() => {
        // Update clock every second
        const interval = setInterval(() => {
            time = new Date().toLocaleTimeString();
        }, 1000);
        return () => clearInterval(interval);
    });

    /** 
     * Toggles the visibility of a window by ID.
     * @param {string} id - The window identifier.
     */
    function toggleWindow(id) {
        windowState.update(s => {
            const win = s[id] || { visible: false, minimized: false, maximized: false, position: { x: 100, y: 100 } };
            if (win.visible && !win.minimized) {
                // If visible and focused (simplification: just minimize)
                win.minimized = true;
            } else {
                // Open or restore
                win.visible = true;
                win.minimized = false;
            }
            return { ...s, [id]: win };
        });
    }
</script>

<nav class="glass-panel w-full h-16 flex items-center justify-between px-6 z-50">
    <!-- Brand Identity -->
    <div class="flex items-center gap-4">
        <div class="w-8 h-8 bg-neon-blue rounded-full shadow-neon-blue animate-pulse"></div>
        <h1 class="text-2xl font-bold tracking-widest text-white neon-text-blue">SPELL ATLAS <span class="text-xs align-top opacity-70">v2.0</span></h1>
    </div>

    <div class="flex items-center gap-4">
        <!-- Window Toggle Buttons -->
        <div class="flex gap-2 mr-8">
            <button class="px-3 py-1 text-xs font-mono border border-neon-blue/30 rounded hover:bg-neon-blue/20 transition-colors text-neon-blue" 
                on:click={() => toggleWindow('feed')}>
                FEED
            </button>
            <button class="px-3 py-1 text-xs font-mono border border-neon-blue/30 rounded hover:bg-neon-blue/20 transition-colors text-neon-blue" 
                on:click={() => toggleWindow('timeline')}>
                TIMELINE
            </button>
            <button class="px-3 py-1 text-xs font-mono border border-neon-blue/30 rounded hover:bg-neon-blue/20 transition-colors text-neon-blue" 
                on:click={() => toggleWindow('countries')}>
                COUNTRIES
            </button>
            <button class="px-3 py-1 text-xs font-mono border border-neon-blue/30 rounded hover:bg-neon-blue/20 transition-colors text-neon-blue" 
                on:click={() => toggleWindow('mediaAtlas')}>
                MEDIA ATLAS
            </button>
        </div>

        <!-- System Status Indicator -->
        <div class="flex flex-col items-end">
            <span class="text-xs text-neon-green font-mono">SYSTEM STATUS</span>
            <span class="text-sm font-bold tracking-wider">OPERATIONAL</span>
        </div>
        
        <!-- Divider -->
        <div class="h-8 w-[1px] bg-glass-border"></div>
        
        <!-- Clock -->
        <div class="font-mono text-xl tracking-wider text-neon-pink">
            {time}
        </div>
    </div>
</nav>
