
<script>
    import { backendThreadStatus } from '../stores.js';
    
    /** @type {string | null} */
    let lastAction = null;
    let isLoading = false;
    let message = '';

    /**
     * @param {string} action
     */
    async function controlCrawler(action) {
        isLoading = true;
        message = '';
        try {
            // @ts-ignore
            const apiBase = import.meta.env.VITE_API_URL || import.meta.env.VITE_API_BASE_URL || 'http://localhost:8002';
            const res = await fetch(`${apiBase}/api/system/crawler/${action}`, { method: 'POST' });
            const data = await res.json();
            
            if (res.ok) {
                message = `Command '${action}' executed: ${data.status}`;
                // Refresh status immediately
                await refreshStatus();
            } else {
                message = `Error: ${data.detail || 'Unknown error'}`;
            }
        } catch (e) {
            // @ts-ignore
            message = `Network Error: ${e.message}`;
        } finally {
            isLoading = false;
        }
    }

    async function refreshStatus() {
        try {
            // @ts-ignore
            const apiBase = import.meta.env.VITE_API_URL || import.meta.env.VITE_API_BASE_URL || 'http://localhost:8002';
            const res = await fetch(`${apiBase}/health/full`);
            if (res.ok) {
                const data = await res.json();
                if (data.threads) {
                    backendThreadStatus.set(data.threads);
                }
            }
        } catch (e) {
            console.warn('Failed to refresh status:', e);
        }
    }

    /**
     * @param {string} mode
     */
    async function triggerHeal(mode) {
        isLoading = true;
        message = 'Initiating self-healing...';
        try {
            // @ts-ignore
            const apiBase = import.meta.env.VITE_API_URL || import.meta.env.VITE_API_BASE_URL || 'http://localhost:8002';
            // Use correct endpoint /api/system/health/autoheal (POST)
            const res = await fetch(`${apiBase}/api/system/health/autoheal`, { method: 'POST' });
            const data = await res.json();
            message = `Heal Result: ${data.status}`;
            if (data.self_heal && data.self_heal.actions) {
                 message += ` | Actions: ${data.self_heal.actions.join(', ')}`;
            }
            // Refresh status immediately
            await refreshStatus();
        } catch (e) {
            // @ts-ignore
            message = `Heal Failed: ${e.message}`;
        } finally {
            isLoading = false;
        }
    }
</script>

<div class="flex flex-col h-full space-y-4">
    <!-- Crawler Control -->
    <div class="bg-white/5 p-3 rounded border border-white/10">
        <h4 class="text-neon-pink font-bold text-xs uppercase mb-3 flex items-center gap-2">
            <span class="material-icons-round text-sm">bug_report</span>
            Crawler Control
        </h4>
        
        <div class="grid grid-cols-3 gap-2 mb-3">
            <button class="flex flex-col items-center justify-center p-2 rounded bg-white/5 hover:bg-white/10 transition-all border border-white/10 text-[10px] font-bold text-green-400 hover:border-green-400/50 disabled:opacity-50 disabled:cursor-not-allowed" on:click={() => controlCrawler('start')} disabled={isLoading || $backendThreadStatus.crawler === 'running'}>
                <span class="material-icons-round text-sm">play_arrow</span> START
            </button>
            <button class="flex flex-col items-center justify-center p-2 rounded bg-white/5 hover:bg-white/10 transition-all border border-white/10 text-[10px] font-bold text-red-400 hover:border-red-400/50 disabled:opacity-50 disabled:cursor-not-allowed" on:click={() => controlCrawler('stop')} disabled={isLoading || $backendThreadStatus.crawler !== 'running'}>
                <span class="material-icons-round text-sm">stop</span> STOP
            </button>
            <button class="flex flex-col items-center justify-center p-2 rounded bg-white/5 hover:bg-white/10 transition-all border border-white/10 text-[10px] font-bold text-yellow-400 hover:border-yellow-400/50 disabled:opacity-50 disabled:cursor-not-allowed" on:click={() => controlCrawler('restart')} disabled={isLoading}>
                <span class="material-icons-round text-sm">restart_alt</span> RESTART
            </button>
        </div>
        
        <div class="text-[10px] font-mono text-gray-400 bg-black/30 p-2 rounded min-h-[40px]">
            {#if isLoading}
                <span class="animate-pulse">Processing command...</span>
            {:else}
                {message || 'Ready for command.'}
            {/if}
        </div>
    </div>

    <!-- Guardian Control -->
    <div class="bg-white/5 p-3 rounded border border-white/10">
        <h4 class="text-purple-400 font-bold text-xs uppercase mb-3 flex items-center gap-2">
            <span class="material-icons-round text-sm">health_and_safety</span>
            System Guardian
        </h4>
        
        <div class="flex justify-between items-center bg-black/20 p-2 rounded mb-2">
            <div class="text-xs text-gray-300">Auto-Recovery Protocol</div>
            <button class="px-2 py-1 bg-purple-500/20 text-purple-400 border border-purple-500/50 rounded text-[10px] hover:bg-purple-500/40"
                    on:click={() => triggerHeal('full')}
                    disabled={isLoading}>
                FORCE HEAL
            </button>
        </div>
        
        <div class="text-[10px] text-gray-500">
            Current Status: 
            <span class:text-green-400={$backendThreadStatus.crawler === 'running'}
                  class:text-red-400={$backendThreadStatus.crawler !== 'running'}>
                CRAWLER: {$backendThreadStatus.crawler?.toUpperCase() || 'UNK'}
            </span>
        </div>
    </div>
</div>

<style>
    /* Removed @apply rules to fix linter warnings and improve compatibility */
</style>
