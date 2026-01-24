<script>
    import { onMount } from 'svelte';
    import { gameStats, simulationDate, isConnected } from '../stores.js';
    
    // Real-time Clock State
    let time = new Date().toLocaleTimeString();
    let date = new Date().toLocaleDateString();

    onMount(() => {
        // Update clock every second
        const interval = setInterval(() => {
            const now = new Date();
            time = now.toLocaleTimeString();
            date = now.toLocaleDateString();
        }, 1000);
        return () => clearInterval(interval);
    });

    /**
     * Formats large numbers into a readable format (e.g., 1.2 M).
     * @param {number} num - The number to format.
     * @returns {string} - The formatted string.
     */
    function formatBigNumber(num) {
        if (num >= 1000000) {
            return (num / 1000000).toFixed(3) + ' M';
        }
        return num.toLocaleString();
    }
</script>

<!-- Main Header Component -->
<header class="w-full h-12 flex items-center justify-between px-6 z-50 pointer-events-auto bg-gradient-to-b from-black/50 to-transparent border-b border-white/5 backdrop-blur-sm select-none">
    <!-- Left: Brand Identity -->
    <div class="flex items-center gap-4">
        <div class="flex flex-col">
            <h1 class="text-xl font-bold tracking-[0.2em] text-white leading-none">SPELL ATLAS</h1>
            <span class="text-[0.6rem] text-neon-blue font-mono tracking-widest opacity-70">Uncharted fingerprints of human misspelling behavior</span>
        </div>
    </div>

    <!-- Center: Decorative Elements -->
    <div class="hidden md:flex items-center gap-2 opacity-30">
        <div class="w-16 h-[1px] bg-white"></div>
        <div class="w-2 h-2 border border-white rotate-45"></div>
        <div class="w-16 h-[1px] bg-white"></div>
    </div>

    <!-- Right: Global Statistics Display -->
    <div class="flex items-center gap-4">
        <!-- Simulation Date Display -->
        <div class="flex items-baseline gap-1.5 border-r border-white/20 pr-4">
            <span class="text-sm font-mono font-bold text-neon-blue drop-shadow-[0_0_8px_rgba(0,243,255,0.6)]">
                {$simulationDate.toISOString().split('T')[0]}
            </span>
            <span class="text-[10px] font-mono text-neon-blue/70 font-bold uppercase">DATE</span>
        </div>

        <!-- Total Errors Detected -->
        <div class="flex items-baseline gap-1.5">
            <span class="text-base font-mono font-bold text-neon-pink drop-shadow-[0_0_8px_rgba(255,0,128,0.6)]">
                {formatBigNumber($gameStats.totalErrors)}
            </span>
            <span class="text-[10px] font-mono text-neon-pink/70 font-bold uppercase">errors</span>
        </div>

        <!-- Divider -->
        <div class="h-4 w-[1px] bg-white/20"></div>

        <!-- Total Words Processed -->
        <div class="flex items-baseline gap-1.5">
            <span class="text-lg font-mono font-bold text-white drop-shadow-md">
                {formatBigNumber(Math.max($gameStats.totalWords, $gameStats.totalErrors + 1))}
            </span>
            <span class="text-xs font-mono text-white/50 font-bold uppercase">words</span>
        </div>
    </div>
</header>
