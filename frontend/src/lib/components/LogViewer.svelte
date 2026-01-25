
<script>
    import { onMount, afterUpdate } from 'svelte';
    import { systemLogs } from '../stores.js';

    /** @type {HTMLElement} */
    let logContainer;

    // Auto-scroll to bottom when new logs arrive
    afterUpdate(() => {
        if (logContainer) {
            logContainer.scrollTop = logContainer.scrollHeight;
        }
    });

    /**
     * @param {string} level
     */
    function getLevelColor(level) {
        switch (level) {
            case 'INFO': return 'text-green-400';
            case 'WARNING': return 'text-yellow-400';
            case 'ERROR': return 'text-red-500 font-bold';
            case 'CRITICAL': return 'text-red-600 font-bold bg-white/10';
            default: return 'text-gray-400';
        }
    }
</script>

<div class="flex flex-col h-full bg-black/80 font-mono text-[10px] p-2 rounded border border-white/10 overflow-hidden">
    <div class="flex justify-between items-center mb-2 pb-2 border-b border-white/10">
        <h4 class="text-neon-blue font-bold uppercase flex items-center gap-2">
            <span class="material-icons-round text-sm">terminal</span>
            System Stream
        </h4>
        <span class="text-xs text-gray-500">{$systemLogs.length} events</span>
    </div>

    <div bind:this={logContainer} class="flex-1 overflow-y-auto space-y-1 scrollbar-hide">
        {#each $systemLogs as log (log.timestamp)}
            <div class="break-all border-l-2 pl-2 border-transparent hover:bg-white/5 transition-colors"
                 class:border-red-500={log.level === 'ERROR'}
                 class:border-yellow-500={log.level === 'WARNING'}>
                <div class="flex gap-2 text-gray-500 mb-0.5">
                    <span>{new Date(log.timestamp * 1000).toLocaleTimeString()}</span>
                    <span class="{getLevelColor(log.level)}">[{log.level}]</span>
                    <span class="text-blue-400">{log.name}</span>
                </div>
                <div class="text-gray-300 pl-4">{log.message}</div>
            </div>
        {/each}
        
        {#if $systemLogs.length === 0}
            <div class="text-center text-gray-600 mt-10 italic">
                Waiting for system events...
            </div>
        {/if}
    </div>
</div>

<style>
    .scrollbar-hide::-webkit-scrollbar {
        display: none;
    }
    .scrollbar-hide {
        -ms-overflow-style: none;
        scrollbar-width: none;
    }
</style>
