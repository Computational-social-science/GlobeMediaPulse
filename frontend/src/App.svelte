<script>
    import { onMount, onDestroy } from 'svelte';
    import { gameStats, isPaused, playbackSpeed, windowState, simulationDate, serviceStatus } from './lib/stores.js';
    import MapContainer from './lib/components/MapContainer.svelte';
    import Header from './lib/components/Header.svelte';
    import CommandBar from './lib/components/CommandBar.svelte';
    import NewsFeed from './lib/components/NewsFeed.svelte';
    import DraggableWindow from './lib/components/DraggableWindow.svelte';
    import MonthlySummary from './lib/components/MonthlySummary.svelte';
    import CountriesContent from './lib/components/CountriesContent.svelte';
    import CorpusViewer from './lib/components/CorpusViewer.svelte';
    import StatsContent from './lib/components/StatsContent.svelte';
    import AnalysisWindow from './lib/components/AnalysisWindow.svelte';
    import GameController from './lib/components/GameController.svelte';
    import MediaAtlasContent from './lib/components/MediaAtlasContent.svelte';

    // System Health Status
    // [FROZEN] Global Health Check Linkage Logic
    let systemStatus = 'OFFLINE'; // Default status
    /** @type {any} */
    let healthCheckTimer;
    let retryCount = 0;

    /**
     * Periodically checks the system health via the API.
     * Implements an Exponential Backoff strategy for retries during outages.
     */
    async function checkSystemHealth() {
        try {
            const apiBase = import.meta.env.VITE_API_URL || import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';
            const response = await fetch(`${apiBase}/health/full`);
            if (response.ok) {
                const data = await response.json();
                
                // Update Granular Status (Feature Toggles) based on service availability
                if (data.services) {
                    serviceStatus.set(data.services);
                }

                if (data.status === 'ok') {
                    systemStatus = 'ONLINE';
                    retryCount = 0; // Reset retry counter on success
                } else if (data.status === 'degraded') {
                    // [UPDATED] Handling degraded status as per user request
                    // Show yellow warning but do NOT block UI interactions
                    systemStatus = 'DEGRADED';
                    retryCount = 0;
                } else {
                    systemStatus = 'OFFLINE';
                    // If backend returns explicitly OFFLINE (rare for health endpoint), treat as failure for backoff
                    retryCount++;
                }
            } else {
                systemStatus = 'OFFLINE';
                retryCount++;
            }
        } catch (error) {
            console.warn('Health check failed:', error);
            systemStatus = 'OFFLINE';
            retryCount++;
        }

        // Schedule next check with Exponential Backoff (Thundering Herd Protection)
        let nextDelay = 15000; // Normal interval: 15s (optimized for performance)
        
        if (systemStatus === 'OFFLINE') {
            // Backoff Strategy: 5s -> 10s -> 20s -> 40s -> 60s
            const base = 5000;
            const cap = 60000;
            // retryCount is incremented on failure. 
            // 1 failure -> 5s
            // 2 failures -> 10s
            nextDelay = Math.min(base * Math.pow(2, Math.max(0, retryCount - 1)), cap);
            console.log(`System OFFLINE. Next check in ${nextDelay/1000}s (Retry ${retryCount})`);
        }
        
        healthCheckTimer = setTimeout(checkSystemHealth, nextDelay);
    }

    // Parallax Effect Logic
    let mouseX = 0;
    let mouseY = 0;
    let hudX = 0;
    let hudY = 0;
    let frameX = 0;
    let frameY = 0;

    /** 
     * Handles mouse movement to update parallax target coordinates.
     * @param {MouseEvent} e 
     */
    function handleMouseMove(e) {
        const { clientX, clientY, currentTarget } = e;
        const { innerWidth, innerHeight } = window;
        
        // Normalize coordinates to -1 to 1 range
        const x = (clientX / innerWidth) * 2 - 1;
        const y = (clientY / innerHeight) * 2 - 1;
        
        mouseX = x;
        mouseY = y;
    }

    // Animation Loop for Smooth Parallax
    onMount(() => {
        // Initial Health Check
        checkSystemHealth();

        /** @type {number} */
        let frame;
        function loop() {
            // HUD moves slightly opposite to mouse (foreground layer effect)
            hudX += (mouseX * -15 - hudX) * 0.1;
            hudY += (mouseY * -15 - hudY) * 0.1;

            // Frame moves less than HUD (mid layer effect)
            frameX += (mouseX * -5 - frameX) * 0.1;
            frameY += (mouseY * -5 - frameY) * 0.1;
            
            frame = requestAnimationFrame(loop);
        }
        loop();
        return () => {
            cancelAnimationFrame(frame);
            clearTimeout(healthCheckTimer);
        };
    });
</script>

<svelte:window on:mousemove={handleMouseMove} />

<GameController />

<main class="relative w-full h-screen overflow-hidden bg-tech-dark text-white font-tech selection:bg-neon-blue/30 perspective-1000">
    <!-- CRT Effects -->
    <div class="scanline"></div>
    <div class="absolute inset-0 pointer-events-none z-[9999] shadow-[inset_0_0_100px_rgba(0,0,0,0.9)]"></div> <!-- Vignette -->
    
    <!-- Map Layer (Background - Static) -->
    <div class="absolute inset-0 w-full h-full z-0 pointer-events-auto">
        <MapContainer />
    </div>

    <!-- HUD Layer -->
    <div class="absolute inset-0 z-10 pointer-events-none flex flex-col justify-between p-4 transition-transform will-change-transform"
         style="transform: translate({hudX}px, {hudY}px) rotateX({-hudY * 0.05}deg) rotateY({hudX * 0.05}deg)">
        
        <!-- Perimeter HUD Frame -->
        <div class="absolute inset-4 border border-white/5 pointer-events-none rounded-lg"
             style="transform: translate({frameX - hudX}px, {frameY - hudY}px)">
            <!-- Top Left Corner -->
            <div class="absolute -top-[1px] -left-[1px] w-8 h-8 border-t-2 border-l-2 border-neon-blue/50 rounded-tl-lg"></div>
            <!-- Top Right Corner -->
            <div class="absolute -top-[1px] -right-[1px] w-8 h-8 border-t-2 border-r-2 border-neon-blue/50 rounded-tr-lg"></div>
            
            <!-- Bottom Left Corner -->
            <div class="absolute -bottom-[1px] -left-[1px] w-8 h-8 border-b-2 border-l-2 border-neon-blue/50 rounded-bl-lg"></div>
            <!-- Bottom Right Corner -->
            <div class="absolute -bottom-[1px] -right-[1px] w-8 h-8 border-b-2 border-r-2 border-neon-blue/50 rounded-br-lg"></div>
            
            <!-- Side Rulers (Decorative) -->
            <div class="absolute top-1/2 left-0 -translate-y-1/2 flex flex-col gap-2 opacity-30">
                {#each Array(10) as _, i}
                    <div class="w-2 h-[1px] bg-white"></div>
                {/each}
            </div>
            <div class="absolute top-1/2 right-0 -translate-y-1/2 flex flex-col gap-2 items-end opacity-30">
                {#each Array(10) as _, i}
                    <div class="w-2 h-[1px] bg-white"></div>
                {/each}
            </div>

            <!-- Center Crosshair -->
            <div class="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-8 h-8 border border-white/10 opacity-20 flex items-center justify-center">
                <div class="w-[1px] h-full bg-white/30"></div>
                <div class="h-[1px] w-full bg-white/30 absolute"></div>
            </div>
        </div>

        <!-- Top: Header -->
        <div class="flex flex-col items-center w-full z-20">
            <Header />
        </div>

        <!-- Middle: Floating Windows Space -->
        <div class="flex-1 relative w-full h-full pointer-events-none">
            <!-- Windows container, allowing dragging everywhere -->
            <DraggableWindow id="feed" title="SATELLITE UPLINK" icon="📡">
                <NewsFeed />
            </DraggableWindow>

            <DraggableWindow id="timeline" title="MONTHLY SUMMARY" icon="⏱">
                <MonthlySummary />
            </DraggableWindow>
            
            <DraggableWindow id="countries" title="REGIONAL STATUS" icon="🌍">
                <CountriesContent />
            </DraggableWindow>
            
            {#if $windowState.corpus?.visible}
                <CorpusViewer id="corpus" />
            {/if}

            <DraggableWindow id="stats" title="GLOBAL INTEL" icon="📊" initialX={window.innerWidth - 420} initialY={450}>
                <StatsContent />
            </DraggableWindow>

            <DraggableWindow id="analytics" title="QUANTITATIVE ANALYTICS" icon="📉" initialX={60} initialY={160}>
                <AnalysisWindow />
            </DraggableWindow>

            {#if $windowState.mediaAtlas?.visible}
                <DraggableWindow id="mediaAtlas" title="MEDIA ATLAS" icon="🌐" initialX={400} initialY={150}>
                    <MediaAtlasContent />
                </DraggableWindow>
            {/if}
        </div>

        <!-- Bottom: Command Bar -->
        <div class="w-full flex justify-center pb-4 pointer-events-auto">
            <CommandBar {systemStatus} />
        </div>
    </div>
</main>
