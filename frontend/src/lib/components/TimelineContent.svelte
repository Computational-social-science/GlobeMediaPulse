<script>
    import { timelineData, timeScale, simulationDate } from '../stores.js';
    import { onMount } from 'svelte';

    /** @type {HTMLCanvasElement} Reference to the canvas element */
    let canvas;
    /** @type {CanvasRenderingContext2D} Canvas 2D context */
    let ctx;
    
    /** @type {any[]} Stores fetched historical data for the timeline */
    let historicalData = [];
    /** @type {boolean} Loading state indicator */
    let isLoading = false;

    // Reactive Trigger for Draw: Redraw when data or time scale changes
    $: if (canvas && (historicalData || $timeScale)) {
        requestAnimationFrame(drawTimeline);
    }
    
    let lastFetchKey = '';

    // Reactively fetch data when simulation params change
    $: {
        const date = $simulationDate;
        const scale = $timeScale;
        
        let key = '';
        if (scale === 'overview') key = `overview`;
        else if (scale === 'year') key = `year-${date.getFullYear()}`;
        else if (scale === 'live') key = `live-${new Date().getFullYear()}`; // Live always shows current year
        
        // Debounce fetch based on key change
        if (key !== lastFetchKey) {
            lastFetchKey = key;
            fetchHistoricalData();
        }
    }

    /**
     * Fetches historical error volume data from the backend.
     * Adapts query range and granularity based on the current time scale.
     */
    async function fetchHistoricalData() {
        isLoading = true;
        try {
            let granularity = 'year';
            let startStr = '';
            let endStr = '';
            const date = $simulationDate;
            const now = new Date();

            if ($timeScale === 'overview') {
                // Overview: Annual data from 2017 to present
                granularity = 'year';
                startStr = '2017-01-01';
                const y = new Date();
                y.setDate(y.getDate() - 1);
                endStr = y.toISOString().split('T')[0];
            } else if ($timeScale === 'year') {
                // Year Mode: Monthly data for the selected year
                granularity = 'month';
                const year = date.getFullYear();
                startStr = `${year}-01-01`;
                endStr = `${year}-12-31`;
            } else if ($timeScale === 'live') {
                // Live Mode: Monthly data for the current year up to today
                granularity = 'month';
                const year = now.getFullYear();
                startStr = `${year}-01-01`;
                endStr = now.toISOString().split('T')[0];
            }

            // @ts-ignore
            const apiBase = import.meta.env.VITE_API_URL || 
                           (window.location.hostname === 'localhost' ? 'http://localhost:8000' : 'https://spellatlas-backend-production.fly.dev');
            
            const res = await fetch(`${apiBase}/api/stats/curve?granularity=${granularity}&start_date=${startStr}&end_date=${endStr}`);
            if (res.ok) {
                historicalData = await res.json();
                drawTimeline();
            }
        } catch (e) {
            console.error("Failed to fetch historical timeline", e);
        } finally {
            isLoading = false;
        }
    }

    /** 
     * Handles clicks on the canvas to seek to a specific time period.
     * @param {MouseEvent} e 
     */
    function handleCanvasClick(e) {
        const rect = canvas.getBoundingClientRect();
        const x = e.clientX - rect.left;
        const width = canvas.width;
        
        const data = historicalData;
        if (!data || data.length === 0) return;
        
        const barWidth = (width - 40) / Math.max(data.length, 1);
        const index = Math.floor((x - 20) / barWidth);

        if (index >= 0 && index < data.length) {
            const item = data[index];
            const d = new Date($simulationDate);
            
            if ($timeScale === 'overview') {
                // Click on Year -> Switch to Year Mode for that year
                const itemDate = new Date(item.time);
                d.setFullYear(itemDate.getFullYear());
                timeScale.set('year');
            } else if ($timeScale === 'year' || $timeScale === 'live') {
                // Click on Month -> Seek to that month
                const itemDate = new Date(item.time);
                d.setMonth(itemDate.getMonth());
                d.setFullYear(itemDate.getFullYear());
            }
            simulationDate.set(d);
        }
    }

    onMount(() => {
        if (canvas) {
            ctx = /** @type {CanvasRenderingContext2D} */ (canvas.getContext('2d'));
            // Initial draw attempt
            if (historicalData.length > 0) drawTimeline();
        }
    });

    /**
     * Renders the timeline chart on the canvas.
     */
    function drawTimeline() {
        if (!ctx || !canvas) return;
        const width = canvas.width;
        const height = canvas.height;
        ctx.clearRect(0, 0, width, height);

        const data = historicalData;

        if (data.length === 0) {
            ctx.fillStyle = 'rgba(255,255,255,0.2)';
            ctx.font = '12px monospace';
            ctx.fillText('NO DATA', 20, 30);
            return;
        }

        // Find max value for scaling
        const getValue = (/** @type {any} */ d) => d.count;
        const maxVal = Math.max(...data.map(getValue), 1);
        
        const barWidth = (width - 40) / Math.max(data.length, 1);
        
        // @ts-ignore
        data.forEach((d, i) => {
            const val = getValue(d);
            const h = (val / maxVal) * (height - 40); // Leave space for labels
            const x = i * barWidth + 20;
            const y = height - h - 20;
            
            // Set Bar Color
            if ($timeScale === 'live') {
                ctx.fillStyle = '#ff0080'; // Neon Pink for Live
                ctx.shadowColor = '#ff0080';
            } else {
                ctx.fillStyle = '#00f3ff'; // Neon Blue for History
                ctx.shadowColor = '#00f3ff';
            }
            
            // Highlight current selection
            const dDate = new Date(d.timestamp);
            const sDate = $simulationDate;
            let isActive = false;
            
            if ($timeScale === 'overview') {
                if (dDate.getFullYear() === sDate.getFullYear()) isActive = true;
            } else {
                if (dDate.getMonth() === sDate.getMonth() && dDate.getFullYear() === sDate.getFullYear()) isActive = true;
            }
            
            if (isActive) {
                ctx.shadowBlur = 15;
                ctx.fillStyle = '#ffffff';
            } else {
                ctx.shadowBlur = 0;
            }

            ctx.fillRect(x, y, barWidth - 2, h);
            
            // Draw Labels (Sparse)
            const labelStep = Math.ceil(data.length / 10);
            
            if (i % labelStep === 0) {
                ctx.fillStyle = '#888';
                ctx.shadowBlur = 0;
                ctx.font = '10px monospace';
                let label = '';
                const date = new Date(d.timestamp);
                
                if ($timeScale === 'overview') {
                    label = date.getFullYear().toString();
                } else {
                    label = date.toLocaleDateString('en-US', { month: 'short' }).toUpperCase();
                }
                ctx.fillText(label, x, height - 5);
            }
        });
    }
</script>

<div class="p-4 w-full h-full flex flex-col">
    <div class="flex justify-between items-center mb-2 text-xs font-mono text-gray-400">
        <span class="font-bold tracking-wider text-white/70">TEMPORAL LAYERS</span>
        <div class="flex items-center gap-1">
            <button class="px-3 py-1 rounded text-[10px] font-bold transition-all duration-300 border border-transparent {$timeScale === 'overview' ? 'bg-neon-blue text-black shadow-[0_0_10px_rgba(0,243,255,0.5)] border-neon-blue' : 'bg-white/5 hover:bg-white/10 text-gray-400 hover:text-white border-white/5'}" on:click={() => $timeScale = 'overview'}>OVERVIEW</button>
            <button class="px-3 py-1 rounded text-[10px] font-bold transition-all duration-300 border border-transparent {$timeScale === 'year' ? 'bg-neon-blue text-black shadow-[0_0_10px_rgba(0,243,255,0.5)] border-neon-blue' : 'bg-white/5 hover:bg-white/10 text-gray-400 hover:text-white border-white/5'}" on:click={() => $timeScale = 'year'}>YEAR</button>
            <div class="w-[1px] h-4 bg-white/20 mx-1"></div>
            <button class="px-3 py-1 rounded text-[10px] font-bold transition-all duration-300 border border-transparent {$timeScale === 'live' ? 'bg-neon-pink text-black shadow-[0_0_10px_rgba(255,0,128,0.5)] border-neon-pink' : 'bg-white/5 hover:bg-white/10 text-gray-400 hover:text-white border-white/5'}" on:click={() => $timeScale = 'live'}>LIVE</button>
        </div>
    </div>
    
    <div class="relative flex-1 min-h-0">
         <canvas 
            bind:this={canvas} 
            width="460" 
            height="250" 
            class="w-full h-full bg-black/20 rounded border border-white/5 cursor-pointer hover:border-neon-blue/30"
            on:click={handleCanvasClick}
         ></canvas>
         
         {#if isLoading}
            <div class="absolute inset-0 flex items-center justify-center bg-black/50 backdrop-blur-sm rounded">
                <span class="text-neon-blue font-mono animate-pulse text-xs">SYNCING...</span>
            </div>
         {/if}
    </div>
</div>