<script>
    import { onMount, onDestroy } from 'svelte';
    import { windowState, serviceStatus, systemStatus, backendThreadStatus } from './lib/stores.js';
    import { soundManager } from './lib/audio/SoundManager.js';
    import { webSocketService } from './lib/services/WebSocketService.js';
    import MapContainer from './lib/components/MapContainer.svelte';
    import Header from './lib/components/Header.svelte';
    import CommandBar from './lib/components/CommandBar.svelte';
    import DraggableWindow from './lib/components/DraggableWindow.svelte';
    import BrainDashboard from './lib/components/BrainDashboard.svelte';
    import SystemMonitorWindow from './lib/components/SystemMonitorWindow.svelte';

    // System Health Status
    // [FROZEN] Global Health Check Linkage Logic
    // let systemStatus = 'OFFLINE'; // Replaced by store
    /** @type {any} */
    let healthCheckTimer;
    let retryCount = 0;
    let isLoading = true; // Initial Loading State

    /**
     * Periodically checks the system health via the API.
     * Implements an Exponential Backoff strategy for retries during outages.
     */
    async function checkSystemHealth() {
        try {
            // @ts-ignore
            const apiBase = import.meta.env.VITE_API_URL || import.meta.env.VITE_API_BASE_URL || 'http://localhost:8002';
            const response = await fetch(`${apiBase}/health/full`);
            if (response.ok) {
                const data = await response.json();
                
                // Update Granular Status (Feature Toggles) based on service availability
                if (data.services) {
                    serviceStatus.set(data.services);
                }
                
                // Update Backend Thread Status
                if (data.threads) {
                    backendThreadStatus.set(data.threads);
                }

                if (data.status === 'ok') {
                    systemStatus.set('ONLINE');
                    retryCount = 0; // Reset retry counter on success
                } else if (data.status === 'degraded') {
                    // [UPDATED] Handling degraded status as per user request
                    // Show yellow warning but do NOT block UI interactions
                    systemStatus.set('DEGRADED');
                    retryCount = 0;
                } else {
                    systemStatus.set('OFFLINE');
                    // If backend returns explicitly OFFLINE (rare for health endpoint), treat as failure for backoff
                    retryCount++;
                }
            } else {
                systemStatus.set('OFFLINE');
                retryCount++;
            }
        } catch (error) {
            console.warn('Health check failed:', error);
            systemStatus.set('OFFLINE');
            retryCount++;
        } finally {
            // Disable loading screen after first check attempt (success or fail)
            // Delay slightly for smooth transition
            setTimeout(() => {
                isLoading = false;
            }, 500);
        }

        // Schedule next check with Exponential Backoff (Thundering Herd Protection)
        let nextDelay = 30000; // Normal interval: 30s (optimized for performance)
        
        if ($systemStatus === 'OFFLINE') {
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
        // Initialize Sound Manager on first user interaction
        soundManager.init();

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

        // Connect Global WebSocket Service
    // @ts-ignore
    webSocketService.connect();

        // Initialize AudioContext on first user interaction
        const initAudio = () => {
            soundManager.init();
            window.removeEventListener('click', initAudio);
            window.removeEventListener('keydown', initAudio);
        };
        window.addEventListener('click', initAudio);
        window.addEventListener('keydown', initAudio);

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

<main class="relative w-full h-screen overflow-hidden bg-tech-dark text-white font-tech selection:bg-neon-blue/30 perspective-1000">
    <!-- Initial Loading Overlay -->
    {#if isLoading}
        <div class="absolute inset-0 z-[10000] bg-black flex flex-col items-center justify-center transition-opacity duration-1000" class:opacity-0={!isLoading}>
            <div class="relative w-24 h-24">
                <div class="absolute inset-0 border-t-2 border-neon-blue rounded-full animate-spin"></div>
                <div class="absolute inset-2 border-r-2 border-neon-purple rounded-full animate-spin-slow"></div>
                <div class="absolute inset-0 flex items-center justify-center">
                    <span class="text-2xl animate-pulse">🌐</span>
                </div>
            </div>
            <div class="mt-8 font-mono text-neon-blue tracking-[0.5em] text-sm animate-pulse">INITIALIZING SYSTEM...</div>
            <div class="mt-2 font-mono text-white/50 text-xs">ESTABLISHING SATELLITE LINK</div>
        </div>
    {/if}

    <!-- CRT Effects -->
    <div class="scanline opacity-20"></div>
    <div class="absolute inset-0 pointer-events-none z-[9999] shadow-[inset_0_0_100px_rgba(0,0,0,0.5)] mix-blend-multiply"></div> <!-- Vignette (Lighter) -->
    <!-- Glass Reflection / Atmosphere -->
    <div class="absolute inset-0 pointer-events-none z-[5] bg-radial-gradient from-transparent via-transparent to-neon-blue/5 opacity-50"></div>
    
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
            {#if $windowState.brain?.visible}
                <DraggableWindow id="brain" title="NARRATIVE INTELLIGENCE" icon="🧠">
                    <BrainDashboard />
                </DraggableWindow>
            {/if}
            {#if $windowState.systemMonitor?.visible}
        <DraggableWindow id="systemMonitor" title="SYSTEM MONITOR" icon="📊" initialX={200} initialY={100} width="600px" height="450px">
            <SystemMonitorWindow />
        </DraggableWindow>
    {/if}
        </div>

        <!-- Bottom: Command Bar -->
        <div class="w-full flex justify-center pb-4 pointer-events-auto">
            <CommandBar systemStatus={$systemStatus} />
        </div>
    </div>
</main>
