<script>
    import { onMount } from 'svelte';
    
    export let countryCode = 'USA'; // Default selected country
    
    let activeTab = 'fingerprint'; // 'fingerprint' | 'stability' | 'evolution'
    /** @type {any} Holds the fetched analysis data */
    let data = null;
    let loading = false;
    /** @type {string|null} Error message if fetch fails */
    let error = null;

    // Available Countries (Simplified list for prototype)
    const countries = ['USA', 'GBR', 'CAN', 'AUS', 'IND', 'CHN', 'RUS', 'FRA', 'DEU', 'JPN'];

    /**
     * Fetches analysis metrics for the selected country and tab.
     */
    async function fetchData() {
        if (!countryCode) return;
        loading = true;
        error = null;
        data = null;
        
        try {
            // @ts-ignore
            const apiBase = import.meta.env.VITE_API_URL || 'http://localhost:8000';
            const url = `${apiBase}/api/analysis/${countryCode}/${activeTab}`;
            const res = await fetch(url);
            if (res.ok) {
                data = await res.json();
            } else {
                error = "Failed to fetch data";
            }
        } catch (e) {
            // @ts-ignore
            error = e.message;
        } finally {
            loading = false;
        }
    }

    // Reactively fetch data when country or tab changes
    $: if (countryCode && activeTab) {
        fetchData();
    }

    // --- Visualization Helpers ---
    
    // Evolution Chart Configuration
    const chartH = 150;
    const chartW = 320;
    
    /** @type {string} SVG points for the evolution chart polyline */
    $: evoPoints = (activeTab === 'evolution' && data?.timeline) 
        ? data.timeline.map((/** @type {{ count: number; }} */ d, /** @type {number} */ i) => {
            const x = (i / (data.timeline.length - 1 || 1)) * chartW;
            const maxVal = Math.max(...data.timeline.map((/** @type {{ count: number; }} */ x) => x.count), 1);
            const y = chartH - ((d.count / maxVal) * chartH);
            return `${x},${y}`;
        }).join(' ')
        : '';

    /**
     * Calculates X coordinate for chart points.
     * @param {number} i - Index
     * @param {number} len - Total length
     */
    function getX(i, len) { return (i / (len - 1 || 1)) * chartW; }
</script>

<div class="w-[360px] h-[400px] flex flex-col font-mono text-xs">
    <!-- Header / Country Selector -->
    <div class="p-3 border-b border-white/10 flex justify-between items-center bg-white/5">
        <span class="text-neon-blue font-bold tracking-widest">ANALYTICS://</span>
        <select 
            bind:value={countryCode} 
            class="bg-black/50 border border-white/30 text-white px-2 py-1 rounded outline-none hover:border-neon-blue transition-colors backdrop-blur-sm">
            {#each countries as c}
                <option value={c}>{c}</option>
            {/each}
        </select>
    </div>

    <!-- Tabs -->
    <div class="flex border-b border-white/10">
        {#each ['fingerprint', 'stability', 'evolution'] as tab}
            <button 
                class="flex-1 py-2 text-center uppercase tracking-wider hover:bg-white/5 transition-colors
                       {activeTab === tab ? 'text-neon-green border-b-2 border-neon-green bg-white/5' : 'text-gray-500'}"
                on:click={() => activeTab = tab}>
                {tab}
            </button>
        {/each}
    </div>

    <!-- Content Area -->
    <div class="flex-1 p-4 overflow-y-auto custom-scrollbar relative">
        {#if loading}
            <div class="absolute inset-0 flex items-center justify-center text-neon-blue animate-pulse">
                COMPUTING METRICS...
            </div>
        {:else if error}
            <div class="text-red-400 text-center mt-10">ERROR: {error}</div>
        {:else if !data}
            <div class="text-gray-500 text-center mt-10">NO DATA</div>
        {:else}
        
            <!-- VIEW: FINGERPRINT -->
            {#if activeTab === 'fingerprint'}
                <div class="space-y-4">
                    <div class="grid grid-cols-2 gap-2">
                        <div class="bg-white/5 p-2 rounded">
                            <div class="text-gray-400 text-[10px] mb-1">COSINE DISTANCE</div>
                            <div class="text-xl text-neon-blue font-bold">{data.cosine_distance?.toFixed(4) || 'N/A'}</div>
                        </div>
                        <div class="bg-white/5 p-2 rounded">
                            <div class="text-gray-400 text-[10px] mb-1">EUCLIDEAN DIST</div>
                            <div class="text-xl text-amber-400 font-bold">{data.euclidean_distance?.toFixed(4) || 'N/A'}</div>
                        </div>
                    </div>
                    
                    {#if data.distinctive_features?.length}
                        <div>
                            <div class="text-gray-400 mb-2 border-b border-white/10 pb-1">DISTINCTIVE ERRORS (vs Global)</div>
                            {#each data.distinctive_features as feat}
                                <div class="flex justify-between items-center py-1">
                                    <span class="text-white">{feat.word}</span>
                                    <div class="flex items-center gap-2">
                                        <span class="text-xs text-green-400">+{feat.delta.toFixed(3)}</span>
                                        <div class="w-16 h-1 bg-white/10 rounded-full overflow-hidden">
                                            <div class="h-full bg-green-500" style="width: {Math.min(feat.delta * 1000, 100)}%"></div>
                                        </div>
                                    </div>
                                </div>
                            {/each}
                        </div>
                    {/if}
                </div>

            <!-- VIEW: STABILITY -->
            {:else if activeTab === 'stability'}
                <div class="flex flex-col items-center justify-center h-full space-y-6">
                    <div class="relative w-32 h-32 flex items-center justify-center">
                        <!-- Circular Gauge Background -->
                        <svg class="w-full h-full transform -rotate-90">
                            <circle cx="64" cy="64" r="60" stroke="rgba(255,255,255,0.1)" stroke-width="8" fill="none" />
                            <circle 
                                cx="64" cy="64" r="60" 
                                stroke={data.stability_score > 0.8 ? '#00ff80' : data.stability_score > 0.5 ? '#fbbf24' : '#ef4444'} 
                                stroke-width="8" 
                                fill="none" 
                                stroke-dasharray="{2 * Math.PI * 60}"
                                stroke-dashoffset="{2 * Math.PI * 60 * (1 - (data.stability_score || 0))}"
                                class="transition-all duration-1000 ease-out"
                            />
                        </svg>
                        <div class="absolute text-center">
                            <div class="text-3xl font-bold text-white">{(data.stability_score * 100).toFixed(0)}%</div>
                            <div class="text-[10px] text-gray-400">STABILITY</div>
                        </div>
                    </div>
                    
                    <div class="text-center space-y-2">
                        <div class="text-lg text-white font-bold">{data.interpretation || 'Unknown'}</div>
                        <div class="text-xs text-gray-400 px-4">
                            Sample Size: {data.sample_size || 0} events
                            <br/>
                            Based on within-country permutation similarity.
                        </div>
                    </div>
                </div>

            <!-- VIEW: EVOLUTION -->
            {:else if activeTab === 'evolution'}
                <div class="h-full flex flex-col">
                    <div class="flex justify-between text-[10px] text-gray-400 mb-2">
                        <span>METRIC: {data.drift_metric}</span>
                        <span>CHANGE POINTS: {data.change_points?.length || 0}</span>
                    </div>
                    
                    <div class="flex-1 relative border border-white/5 bg-black/20 p-2">
                         {#if data.timeline?.length}
                            <svg viewBox="0 0 {chartW} {chartH}" class="w-full h-full overflow-visible">
                                <!-- Grid -->
                                <line x1="0" y1={chartH/2} x2={chartW} y2={chartH/2} stroke="white" stroke-opacity="0.1" stroke-dasharray="4 4" />
                                
                                <!-- Line -->
                                <polyline points={evoPoints} fill="none" stroke="#00f3ff" stroke-width="2" />
                                
                                <!-- Change Points (Vertical Lines) -->
                                {#each data.change_points || [] as cp}
                                    <line 
                                        x1={getX(cp.index, data.timeline.length)} y1="0" 
                                        x2={getX(cp.index, data.timeline.length)} y2={chartH} 
                                        stroke="#ef4444" stroke-width="1" stroke-dasharray="2 2" 
                                    />
                                    <text 
                                        x={getX(cp.index, data.timeline.length)} y="-5" 
                                        fill="#ef4444" font-size="8" text-anchor="middle">
                                        ALERT
                                    </text>
                                {/each}
                            </svg>
                            <!-- Date Labels -->
                            <div class="flex justify-between text-[8px] text-gray-500 mt-1">
                                <span>{data.timeline[0].date}</span>
                                <span>{data.timeline[data.timeline.length-1].date}</span>
                            </div>
                         {:else}
                            <div class="flex items-center justify-center h-full text-gray-500">
                                NO TIMELINE DATA
                            </div>
                         {/if}
                    </div>
                </div>
            {/if}
        {/if}
    </div>
</div>

<style>
    .custom-scrollbar::-webkit-scrollbar { width: 4px; }
    .custom-scrollbar::-webkit-scrollbar-track { background: rgba(255, 255, 255, 0.05); }
    .custom-scrollbar::-webkit-scrollbar-thumb { background: rgba(255, 255, 255, 0.1); border-radius: 2px; }
</style>
