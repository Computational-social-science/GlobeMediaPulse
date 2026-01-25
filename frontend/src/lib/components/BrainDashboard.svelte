
<script>
    import { onMount } from 'svelte';
    
    let stats = {
        /** @type {any[]} */
        top_entities: [],
        narrative_divergence: {
            tier_0_sentiment: 0,
            tier_2_sentiment: 0,
            divergence: 0,
            alert: false
        }
    };
    let loading = true;

    async function fetchBrainStats() {
        loading = true;
        try {
            // @ts-ignore
            const apiBase = import.meta.env.VITE_API_URL || 
                            (window.location.hostname === 'localhost' ? 'http://localhost:8002' : 'https://globemediapulse-backend-production.fly.dev');
            
            const res = await fetch(`${apiBase}/api/stats/brain`);
            if (res.ok) {
                stats = await res.json();
            }
        } catch (e) {
            console.error(e);
        } finally {
            loading = false;
        }
    }

    onMount(() => {
        fetchBrainStats();
        const interval = setInterval(fetchBrainStats, 60000); // 1 min refresh
        return () => clearInterval(interval);
    });

    // Color helpers
    $: divergenceColor = stats.narrative_divergence.alert ? 'text-red-500' : 'text-green-500';

</script>

<div class="h-full flex flex-col space-y-4">
    <!-- Narrative Conflict Monitor -->
    <div class="bg-white/5 p-3 rounded">
        <h4 class="text-neon-pink font-bold text-xs uppercase mb-2">Narrative Conflict Monitor</h4>
        <div class="flex justify-between items-center text-xs mb-2">
            <span>Divergence:</span>
            <span class="font-bold {divergenceColor}">{stats.narrative_divergence.divergence.toFixed(2)}</span>
        </div>
        
        <div class="space-y-1">
            <div class="flex justify-between text-[10px] text-gray-400">
                <span>Tier-0 (Global)</span>
                <span>{stats.narrative_divergence.tier_0_sentiment.toFixed(2)}</span>
            </div>
            <div class="w-full bg-white/10 h-1 rounded overflow-hidden">
                <div class="h-full bg-blue-500" style="width: {(stats.narrative_divergence.tier_0_sentiment + 1) * 50}%"></div>
            </div>

            <div class="flex justify-between text-[10px] text-gray-400 mt-2">
                <span>Tier-2 (Local)</span>
                <span>{stats.narrative_divergence.tier_2_sentiment.toFixed(2)}</span>
            </div>
            <div class="w-full bg-white/10 h-1 rounded overflow-hidden">
                <div class="h-full bg-green-500" style="width: {(stats.narrative_divergence.tier_2_sentiment + 1) * 50}%"></div>
            </div>
        </div>
    </div>

    <!-- Entity Monitor -->
    <div class="bg-white/5 p-3 rounded">
        <h4 class="text-yellow-400 font-bold text-xs uppercase mb-2">Top Entities (24h)</h4>
        <div class="flex flex-wrap gap-2">
            {#each stats.top_entities as entity}
                <span class="px-2 py-1 bg-white/10 rounded text-[10px] text-gray-300 border border-white/5">
                    {entity}
                </span>
            {/each}
        </div>
    </div>
</div>
