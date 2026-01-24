<script>
    import { simulationDate, timeScale } from '../stores.js';
    import { onMount } from 'svelte';
    
    /** @type {any[]} List of top detected spelling errors */
    let topErrors = [];
    /** @type {any[]} List of countries with highest activity */
    let topCountries = [];
    
    let isLoading = false;
    let currentPeriodStr = '';

    // Reactively fetch data when simulation date or time scale changes
    $: {
        const d = $simulationDate;
        const scale = $timeScale;
        let periodStr = '';

        if (scale === 'year') {
            periodStr = `${d.getFullYear()} SUMMARY`;
        } else {
            periodStr = d.toLocaleString('en-US', { month: 'long', year: 'numeric' });
        }
        
        // Debounce/Check if period actually changed before fetching
        if (periodStr !== currentPeriodStr) {
            currentPeriodStr = periodStr;
            fetchData();
        }
    }

    /**
     * Fetches summary statistics from the backend for the current period.
     */
    async function fetchData() {
        isLoading = true;
        try {
            const d = $simulationDate;
            const scale = $timeScale;
            const year = d.getFullYear();
            
            let startStr, endStr;

            if (scale === 'year') {
                // Full Year Range
                startStr = `${year}-01-01`;
                endStr = `${year}-12-31`;
            } else {
                if (scale === 'live') {
                    // Current Month Logic
                    const month = d.getMonth() + 1;
                    const m = month < 10 ? `0${month}` : month;
                    const lastDay = new Date(year, month, 0).getDate();
                    startStr = `${year}-${m}-01`;
                    endStr = `${year}-${m}-${lastDay}`;
                } else {
                    // Overview or default to Annual
                    startStr = `${year}-01-01`;
                    endStr = `${year}-12-31`;
                }
            }
            
            // @ts-ignore
            const apiBase = import.meta.env.VITE_API_URL || 
                           (window.location.hostname === 'localhost' ? 'http://localhost:8000' : 'https://spellatlas-backend-production.fly.dev');
            
            // Fetch Top Errors
            const resErrors = await fetch(`${apiBase}/api/stats/top-errors?limit=30&start_date=${startStr}&end_date=${endStr}`);
            if (resErrors.ok) topErrors = await resErrors.json();
            
            // Fetch Top Countries
            const resCountries = await fetch(`${apiBase}/api/stats/top-countries?limit=30&start_date=${startStr}&end_date=${endStr}`);
            if (resCountries.ok) topCountries = await resCountries.json();
            
        } catch (e) {
            console.error("Failed to fetch summary", e);
        } finally {
            isLoading = false;
        }
    }
</script>

<div class="p-4 w-[480px] h-[320px] flex flex-col gap-4 text-white font-tech">
    <!-- Header -->
    <div class="flex justify-between items-center border-b border-white/10 pb-2">
        <div class="flex items-center gap-2">
            <span class="material-icons-round text-neon-blue">calendar_today</span>
            <h2 class="text-neon-blue font-mono font-bold text-lg tracking-wider">{currentPeriodStr.toUpperCase()}</h2>
        </div>
        {#if isLoading}
            <div class="flex items-center gap-2">
                <div class="w-2 h-2 rounded-full bg-neon-pink animate-ping"></div>
                <span class="text-xs text-neon-pink font-mono">SYNCING...</span>
            </div>
        {/if}
    </div>
    
    <!-- Content Area -->
    <div class="flex-1 flex gap-4 min-h-0">
        
        <!-- Errors Column -->
        <div class="flex-1 flex flex-col min-h-0 bg-black/20 rounded border border-white/5">
            <div class="p-2 bg-white/5 border-b border-white/5 flex justify-between items-center">
                <h3 class="text-xs text-gray-400 font-bold uppercase tracking-wider">Top 30 Errors</h3>
                <span class="text-[10px] text-gray-600 font-mono">FREQ</span>
            </div>
            
            <div class="flex-1 overflow-auto custom-scrollbar p-1">
                <table class="w-full text-xs">
                    <tbody>
                        {#each topErrors as err, i}
                            <tr class="border-b border-white/5 last:border-0 hover:bg-white/5 transition-colors group">
                                <td class="py-1.5 px-2 text-gray-500 font-mono w-6">{i+1}</td>
                                <td class="py-1.5 px-2 font-mono text-white/90 group-hover:text-neon-pink transition-colors whitespace-nowrap relative">
                                    <div class="absolute inset-y-0 left-0 bg-neon-pink/10 -z-10" style="width: {Math.min(100, (err.count / (topErrors[0]?.count || 1)) * 100)}%"></div>
                                    {err.word}
                                </td>
                                <td class="py-1.5 px-2 text-right font-bold text-neon-blue/80">{err.count}</td>
                            </tr>
                        {/each}
                        {#if topErrors.length === 0 && !isLoading}
                            <tr><td colspan="3" class="text-center py-4 text-gray-500">No errors recorded</td></tr>
                        {/if}
                    </tbody>
                </table>
            </div>
        </div>
        
        <!-- Countries Column -->
        <div class="flex-1 flex flex-col min-h-0 bg-black/20 rounded border border-white/5">
            <div class="p-2 bg-white/5 border-b border-white/5 flex justify-between items-center">
                <h3 class="text-xs text-gray-400 font-bold uppercase tracking-wider">Affected Regions</h3>
                <span class="text-[10px] text-gray-600 font-mono">VOL</span>
            </div>
            
            <div class="flex-1 overflow-auto custom-scrollbar p-1">
                <table class="w-full text-xs">
                    <tbody>
                        {#each topCountries as c, i}
                            <tr class="border-b border-white/5 last:border-0 hover:bg-white/5 transition-colors group">
                                <td class="py-1.5 px-2 text-gray-500 font-mono w-6">{i+1}</td>
                                <td class="py-1.5 px-2 font-mono text-white/90 group-hover:text-neon-blue transition-colors whitespace-nowrap relative">
                                    <div class="absolute inset-y-0 left-0 bg-neon-blue/10 -z-10" style="width: {Math.min(100, (c.count / (topCountries[0]?.count || 1)) * 100)}%"></div>
                                    {c.name}
                                </td>
                                <td class="py-1.5 px-2 text-right font-bold text-neon-blue/80">{c.count}</td>
                            </tr>
                        {/each}
                        {#if topCountries.length === 0 && !isLoading}
                             <tr><td colspan="3" class="text-center py-4 text-gray-500">No data</td></tr>
                        {/if}
                    </tbody>
                </table>
            </div>
        </div>
    </div>
</div>

<style>
    .custom-scrollbar::-webkit-scrollbar {
        width: 6px;
        height: 6px;
    }
    .custom-scrollbar::-webkit-scrollbar-track {
        background: rgba(0, 0, 0, 0.2);
    }
    .custom-scrollbar::-webkit-scrollbar-thumb {
        background: rgba(255, 255, 255, 0.1);
        border-radius: 3px;
    }
    .custom-scrollbar::-webkit-scrollbar-thumb:hover {
        background: rgba(0, 243, 255, 0.3);
    }
    .custom-scrollbar::-webkit-scrollbar-corner {
        background: transparent;
    }
</style>