<script>
    import { onMount, onDestroy } from 'svelte';
    import { simulationDate, timeScale } from '../stores.js';
    
    /** @type {any[]} List of top errors for the current period */
    let topErrors = [];
    /** @type {any[]} Time-series data for the trend curve */
    let trendCurve = [];
    
    let loading = true;
    let activeTab = 'top'; // 'top' | 'trends'
    
    /** @type {any} Reference to track date changes for reactivity */
    let currentDate = null;

    /** 
     * Fetches statistics from the backend based on the current simulation date and time scale.
     * @returns {Promise<void>}
     */
    async function fetchData() {
        loading = true;
        try {
            // Robust fallback: If env var is missing, guess based on environment
            // @ts-ignore
            const apiBase = import.meta.env.VITE_API_URL || 
                            (window.location.hostname === 'localhost' ? 'http://localhost:8000' : 'https://globemediapulse-backend-production.fly.dev');
            
            let queryParams = "";
            if ($simulationDate) {
                // Parse simulationDate
                const d = new Date($simulationDate);
                if (!isNaN(d.getTime())) {
                    let start, end;
                    let granularity = 'hour';
                    
                    if ($timeScale === 'overview') {
                        // Full Year Stats for Overview
                        start = new Date(Date.UTC(d.getFullYear(), 0, 1));
                        end = new Date(Date.UTC(d.getFullYear(), 11, 31, 23, 59, 59, 999));
                        granularity = 'month';
                    } else {
                        // Month Stats (Year or Live mode)
                        start = new Date(Date.UTC(d.getFullYear(), d.getMonth(), 1));
                        end = new Date(Date.UTC(d.getFullYear(), d.getMonth() + 1, 0, 23, 59, 59, 999));
                        granularity = 'day';
                    }
                    
                    queryParams = `&start_date=${start.toISOString()}&end_date=${end.toISOString()}&granularity=${granularity}`;
                }
            }

            const [topRes, curveRes] = await Promise.all([
                fetch(`${apiBase}/api/stats/top-errors?limit=10${queryParams}`),
                fetch(`${apiBase}/api/stats/curve?hours=24${queryParams}`)
            ]);
            
            if (topRes.ok) topErrors = await topRes.json();
            if (curveRes.ok) trendCurve = await curveRes.json();
        } catch (e) {
            console.error(e);
        } finally {
            loading = false;
        }
    }

    onMount(() => {
        fetchData();
        // Auto-refresh every 30 seconds
        const interval = setInterval(fetchData, 30000);
        return () => clearInterval(interval);
    });
    
    // React to simulationDate changes
    $: if ($simulationDate !== currentDate) {
        // @ts-ignore
        currentDate = $simulationDate;
        fetchData();
    }

    // --- Chart Rendering Helpers ---
    
    /** @type {number} Max value for scaling top error bars */
    $: maxValTop = Math.max(...topErrors.map((/** @type {{ count: number; }} */ d) => d.count), 1);
    /** @type {number} Max value for scaling trend curve */
    $: maxValCurve = Math.max(...trendCurve.map((/** @type {{ count: number; }} */ d) => d.count), 1);

    // SVG Chart Dimensions
    const chartHeight = 150;
    const chartWidth = 300;
    
    /** 
     * Calculates X coordinate for a point index.
     * @param {number} i 
     */
    function getX(i) {
        return (i / (trendCurve.length - 1 || 1)) * chartWidth;
    }
    
    /** 
     * Calculates Y coordinate for a value (inverted for SVG).
     * @param {number} val 
     */
    function getY(val) {
        return chartHeight - ((val / maxValCurve) * chartHeight);
    }
    
    /** @type {string} SVG polyline points string */
    $: points = trendCurve.map((/** @type {{ count: number; }} */ d, /** @type {number} */ i) => `${getX(i)},${getY(d.count)}`).join(' ');
    /** @type {string} SVG polygon points string for area fill */
    $: areaPoints = `${points} ${chartWidth},${chartHeight} 0,${chartHeight}`;
    
    /** 
     * Updates the global time scale store.
     * @param {string} scale 
     */
    function setTimeScale(scale) {
        timeScale.set(scale);
    }
</script>

<div class="flex flex-col h-full w-[350px] h-[340px] p-4 font-mono text-sm">
    <div class="flex justify-between items-center mb-4">
        <h3 class="text-neon-pink font-bold text-lg tracking-widest uppercase">Global Stats</h3>
        <div class="flex gap-1">
             <button 
                class="px-2 py-1 text-xs uppercase border border-white/20 rounded hover:bg-white/10 transition-colors {$timeScale === 'decade' ? 'bg-neon-blue/20 text-neon-blue border-neon-blue' : 'text-gray-400'}"
                on:click={() => setTimeScale('decade')}>
                DECADE
            </button>
            <button 
                class="px-2 py-1 text-xs uppercase border border-white/20 rounded hover:bg-white/10 transition-colors {$timeScale === 'year' ? 'bg-neon-blue/20 text-neon-blue border-neon-blue' : 'text-gray-400'}"
                on:click={() => setTimeScale('year')}>
                YEAR
            </button>
            <button 
                class="px-2 py-1 text-xs uppercase border border-white/20 rounded hover:bg-white/10 transition-colors {$timeScale === 'month' ? 'bg-neon-blue/20 text-neon-blue border-neon-blue' : 'text-gray-400'}"
                on:click={() => setTimeScale('month')}>
                MONTH
            </button>
            <button 
                class="px-2 py-1 text-xs uppercase border border-white/20 rounded hover:bg-white/10 transition-colors {$timeScale === 'day' ? 'bg-neon-blue/20 text-neon-blue border-neon-blue' : 'text-gray-400'}"
                on:click={() => setTimeScale('day')}>
                DAY
            </button>
        </div>
    </div>
    <!-- Time Scale Controls -->
    <div class="flex justify-center mb-2 space-x-2">
        {#each ['day', 'month', 'year'] as scale}
            <button 
                class="px-2 py-1 text-xs uppercase border border-white/20 rounded hover:bg-white/10 transition-colors {$timeScale === scale ? 'bg-neon-blue/20 text-neon-blue border-neon-blue' : 'text-gray-400'}"
                on:click={() => setTimeScale(scale)}>
                {scale}
            </button>
        {/each}
    </div>

    <!-- Tabs -->
    <div class="flex border-b border-white/10 mb-4">
        <button 
            class="px-4 py-2 hover:bg-white/5 transition-colors {activeTab === 'top' ? 'text-neon-blue border-b-2 border-neon-blue' : 'text-gray-500'}"
            on:click={() => activeTab = 'top'}>
            TOP ERRORS
        </button>
        <button 
            class="px-4 py-2 hover:bg-white/5 transition-colors {activeTab === 'trends' ? 'text-neon-green border-b-2 border-neon-green' : 'text-gray-500'}"
            on:click={() => activeTab = 'trends'}>
            TRENDS
        </button>
    </div>

    <!-- Content -->
    <div class="flex-1 overflow-y-auto custom-scrollbar relative">
        {#if loading && topErrors.length === 0 && trendCurve.length === 0}
            <div class="absolute inset-0 flex items-center justify-center text-neon-blue animate-pulse">
                ANALYZING DATA...
            </div>
        {:else if activeTab === 'top'}
            {#if topErrors.length === 0}
                 <div class="text-center text-gray-500 mt-10">NO DATA AVAILABLE</div>
            {:else}
                <div class="space-y-3">
                    {#each topErrors as item, i}
                        <div class="relative group">
                            <div class="flex justify-between items-end mb-1 text-xs relative z-10">
                                <span class="font-bold text-red-400">{item.word}</span>
                                <span class="text-white/60">{item.count}</span>
                            </div>
                            <div class="h-2 w-full bg-white/5 rounded-full overflow-hidden">
                                <div 
                                    class="h-full rounded-full transition-all duration-1000 ease-out bg-gradient-to-r from-red-500 to-red-400"
                                    style="width: {(item.count / maxValTop) * 100}%"
                                ></div>
                            </div>
                        </div>
                    {/each}
                </div>
            {/if}
        {:else}
            <!-- Trend Chart -->
            {#if trendCurve.length === 0}
                <div class="text-center text-gray-500 mt-10">NO TREND DATA</div>
            {:else}
                <div class="relative h-[200px] w-full mt-4">
                    <svg viewBox="0 0 {chartWidth} {chartHeight}" class="w-full h-full overflow-visible">
                        <!-- Grid Lines -->
                        {#each [0, 0.25, 0.5, 0.75, 1] as tick}
                             <line x1="0" y1={chartHeight * tick} x2={chartWidth} y2={chartHeight * tick} stroke="white" stroke-opacity="0.1" stroke-dasharray="2 2" />
                        {/each}
                        
                        <!-- Area -->
                        <path d="M0,{chartHeight} {areaPoints}" fill="rgba(0, 255, 128, 0.1)" />
                        
                        <!-- Line -->
                        <polyline points={points} fill="none" stroke="#00ff80" stroke-width="2" />
                        
                        <!-- Points -->
                        {#each trendCurve as point, i}
                            <circle cx={getX(i)} cy={getY(point.count)} r="3" fill="#00ff80" class="hover:r-4 transition-all" />
                        {/each}
                    </svg>
                    
                    <!-- X-Axis Labels (First and Last) -->
                    <div class="flex justify-between text-[10px] text-gray-500 mt-2">
                        <span>{new Date(trendCurve[0].time).getHours()}:00</span>
                        <span>{new Date(trendCurve[trendCurve.length-1].time).getHours()}:00</span>
                    </div>
                </div>
            {/if}
        {/if}
    </div>
</div>

<style>
    /* Custom Scrollbar for Webkit */
    .custom-scrollbar::-webkit-scrollbar {
        width: 4px;
    }
    .custom-scrollbar::-webkit-scrollbar-track {
        background: rgba(255, 255, 255, 0.05);
    }
    .custom-scrollbar::-webkit-scrollbar-thumb {
        background: rgba(255, 255, 255, 0.1);
        border-radius: 2px;
    }
</style>
