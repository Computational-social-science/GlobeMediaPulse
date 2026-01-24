<script>
    import { isPaused, gameStats } from '../stores.js';

    /**
     * Formats large numbers for display (e.g., 1.2 M).
     * @param {number} num - The number to format.
     */
    function formatBigNumber(num) {
        if (num >= 1000000) {
            return (num / 1000000).toFixed(3) + ' M';
        }
        return num.toLocaleString();
    }
</script>

<div class="glass-panel h-12 px-6 flex items-center justify-center gap-6 transition-all duration-500 hover:shadow-neon-blue/20">
    <!-- Active Status Indicator -->
    <div class="flex items-center gap-3">
        <div class={`w-3 h-3 rounded-full ${$isPaused ? 'bg-yellow-500' : 'bg-neon-green animate-pulse'}`}></div>
        <span class="font-mono text-sm tracking-widest">
            {$isPaused ? 'SYSTEM PAUSED' : 'MONITORING ACTIVE'}
        </span>
    </div>

    <!-- Divider -->
    <div class="h-6 w-[1px] bg-glass-border mx-2"></div>
    
    <!-- Real-time Statistics -->
    <div class="flex items-center gap-4 font-mono text-xs text-gray-300">
        <div>
            <span class="text-neon-blue">DETECTED:</span>
            <span class="text-white ml-1">{formatBigNumber($gameStats.totalItems)}</span>
        </div>
        <div>
            <span class="text-neon-pink">ANOMALIES:</span>
            <span class="text-white ml-1">{formatBigNumber($gameStats.totalErrors)}</span>
        </div>
    </div>
</div>
