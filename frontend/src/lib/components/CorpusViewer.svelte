<script>
    import DraggableWindow from './DraggableWindow.svelte';
    import { onMount } from 'svelte';

    export let id;
    
    /** @type {any[]} List of detected error events */
    let errorEvents = [];
    /** @type {any[]} List of skipped or non-error events */
    let skippedEvents = [];
    
    let activeTab = 'errors'; // 'errors' | 'skipped'
    let loading = false;
    let autoRefresh = false;
    /** @type {any} Interval ID for auto-refresh */
    let intervalId;

    /**
     * Fetches the latest corpus data (errors and skipped items) from the backend.
     */
    async function fetchData() {
        loading = true;
        try {
            const [errRes, skipRes] = await Promise.all([
                fetch('http://localhost:8000/api/corpus/errors?limit=50'),
                fetch('http://localhost:8000/api/corpus/skipped?limit=50')
            ]);
            
            if (errRes.ok) errorEvents = await errRes.json();
            if (skipRes.ok) skippedEvents = await skipRes.json();
        } catch (e) {
            console.error("Failed to fetch corpus:", e);
        } finally {
            loading = false;
        }
    }

    onMount(() => {
        fetchData();
        return () => {
            if (intervalId) clearInterval(intervalId);
        };
    });

    // Toggle auto-refresh interval
    $: if (autoRefresh) {
        if (!intervalId) intervalId = setInterval(fetchData, 5000);
    } else {
        if (intervalId) clearInterval(intervalId);
        intervalId = null;
    }

    /**
     * Highlights the target word in the context string.
     * @param {string} context - The full sentence or context.
     * @param {string} word - The word to highlight.
     * @returns {string} - HTML string with highlighting.
     */
    function highlightDiff(context, word) {
        if (!context || !word) return context;
        // Simple case-insensitive replace with highlight span
        const regex = new RegExp(`(${word})`, 'gi');
        return context.replace(regex, '<span class="text-neon-pink bg-neon-pink/10 font-bold border-b border-neon-pink">$1</span>');
    }
    
    /**
     * Highlights the suggested correction in the corrected context string.
     * @param {string} context - The corrected sentence.
     * @param {string} word - Original word (unused in logic but kept for interface consistency).
     * @param {string} suggestion - The suggested correction.
     * @returns {string} - HTML string with highlighting.
     */
    function highlightCorrected(context, word, suggestion) {
        if (!context || !suggestion) return context;
        // In corrected context, we look for the suggestion
        const regex = new RegExp(`(${suggestion})`, 'gi');
        return context.replace(regex, '<span class="text-neon-blue bg-neon-blue/10 font-bold border-b border-neon-blue">$1</span>');
    }
</script>

<DraggableWindow {id} title="Research Corpus Fingerprint" width="800px" height="600px">
    <div class="flex flex-col h-full text-xs font-mono">
        <!-- Toolbar -->
        <div class="flex items-center justify-between p-2 border-b border-white/10 bg-white/5">
            <div class="flex gap-2">
                <button 
                    class="px-3 py-1 rounded-sm border transition-colors {activeTab === 'errors' ? 'bg-neon-pink/20 border-neon-pink text-neon-pink shadow-[0_0_10px_rgba(255,0,128,0.2)]' : 'border-white/10 hover:bg-white/5 text-white/60'}"
                    on:click={() => activeTab = 'errors'}
                >
                    Errors ({errorEvents.length})
                </button>
                <button 
                    class="px-3 py-1 rounded-sm border transition-colors {activeTab === 'skipped' ? 'bg-neon-blue/20 border-neon-blue text-neon-blue shadow-[0_0_10px_rgba(0,243,255,0.2)]' : 'border-white/10 hover:bg-white/5 text-white/60'}"
                    on:click={() => activeTab = 'skipped'}
                >
                    Skipped/Non-Errors ({skippedEvents.length})
                </button>
            </div>
            
            <div class="flex gap-2 items-center">
                <label class="flex items-center gap-1 cursor-pointer select-none text-white/50 hover:text-white transition-colors">
                    <input type="checkbox" bind:checked={autoRefresh} class="accent-neon-blue">
                    <span>Live</span>
                </label>
                <button 
                    class="p-1 hover:text-white text-white/50 transition-colors" 
                    on:click={fetchData}
                    title="Refresh"
                >
                    <span class="material-icons-round text-sm">refresh</span>
                </button>
            </div>
        </div>

        <!-- Content -->
        <div class="flex-1 overflow-auto p-2 space-y-2 custom-scrollbar">
            {#if loading && errorEvents.length === 0}
                <div class="flex items-center justify-center h-full text-white/30 animate-pulse">Loading corpus...</div>
            {:else if activeTab === 'errors'}
                <table class="w-full text-left border-collapse">
                    <thead class="sticky top-0 bg-[#050a14]/95 backdrop-blur-md z-10 text-white/40 shadow-sm">
                        <tr>
                            <th class="p-2 border-b border-white/10 w-16">ISO</th>
                            <th class="p-2 border-b border-white/10 w-32">Word -> Sugg</th>
                            <th class="p-2 border-b border-white/10">Context vs Corrected</th>
                        </tr>
                    </thead>
                    <tbody>
                        {#each errorEvents as event}
                            <tr class="border-b border-white/5 hover:bg-white/5 group transition-colors">
                                <td class="p-2 align-top opacity-50">{event.country_code}</td>
                                <td class="p-2 align-top">
                                    <div class="text-neon-pink drop-shadow-[0_0_3px_rgba(255,0,128,0.5)]">{event.word}</div>
                                    <div class="text-white/30 text-[10px]">&darr;</div>
                                    <div class="text-neon-blue drop-shadow-[0_0_3px_rgba(0,243,255,0.5)]">{event.suggestion}</div>
                                </td>
                                <td class="p-2 align-top space-y-1">
                                    <div class="text-white/80 leading-relaxed bg-black/40 p-1.5 rounded border border-white/5">
                                        {@html highlightDiff(event.context, event.word)}
                                    </div>
                                    {#if event.corrected_context}
                                        <div class="text-white/60 leading-relaxed bg-neon-blue/5 p-1.5 rounded border border-white/5">
                                            {@html highlightCorrected(event.corrected_context, event.word, event.suggestion)}
                                        </div>
                                    {/if}
                                    <div class="text-[10px] text-white/20 truncate max-w-md group-hover:text-white/40 transition-colors">
                                        {event.url}
                                    </div>
                                </td>
                            </tr>
                        {/each}
                    </tbody>
                </table>
            {:else}
                <table class="w-full text-left border-collapse">
                    <thead class="sticky top-0 bg-[#050a14]/95 backdrop-blur-md z-10 text-white/40 shadow-sm">
                        <tr>
                            <th class="p-2 border-b border-white/10 w-24">Reason</th>
                            <th class="p-2 border-b border-white/10 w-24">Word</th>
                            <th class="p-2 border-b border-white/10">Context</th>
                        </tr>
                    </thead>
                    <tbody>
                        {#each skippedEvents as event}
                            <tr class="border-b border-white/5 hover:bg-white/5">
                                <td class="p-2 align-top">
                                    <span class="px-1.5 py-0.5 rounded bg-white/10 text-white/60 text-[10px] border border-white/5">
                                        {event.reason || event.tag}
                                    </span>
                                </td>
                                <td class="p-2 align-top text-white/80 font-bold">{event.word}</td>
                                <td class="p-2 align-top text-white/60">
                                    {event.context}
                                </td>
                            </tr>
                        {/each}
                    </tbody>
                </table>
            {/if}
        </div>
    </div>
</DraggableWindow>

<style>
    .custom-scrollbar::-webkit-scrollbar {
        width: 4px;
        height: 4px;
    }
    .custom-scrollbar::-webkit-scrollbar-track {
        background: rgba(0, 0, 0, 0.2);
    }
    .custom-scrollbar::-webkit-scrollbar-thumb {
        background: rgba(255, 255, 255, 0.2);
        border-radius: 2px;
    }
    .custom-scrollbar::-webkit-scrollbar-thumb:hover {
        background: rgba(255, 255, 255, 0.4);
    }
</style>