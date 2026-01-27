<script lang="ts">
    import { onMount, onDestroy, afterUpdate, setContext } from 'svelte';
    import { get } from 'svelte/store';
    import {
        windowState,
        serviceStatus,
        systemStatus,
        backendThreadStatus,
        systemLogs,
        isConnected,
        newsEvents,
        soundEnabled,
        audioEnabled,
        audioVolume
    } from './lib/stores.js';
    import MapContainer from './lib/components/MapContainer.svelte';

    class SoundManager {
        ctx: AudioContext | null = null;
        masterGain: GainNode | null = null;
        humOscillator: { osc: OscillatorNode; gain: GainNode } | null = null;
        isInitialized = false;
        systemStatus = 'OFFLINE';

        /**
         * Initialize the audio pipeline after user activation.
         * Research motivation: align sensory feedback with system state to improve operator trust.
         */
        init() {
            if (this.isInitialized) return;

            try {
                // @ts-expect-error webkit audio context
                const AudioContext = window.AudioContext || window.webkitAudioContext;
                this.ctx = new AudioContext();
                this.masterGain = this.ctx.createGain();
                this.masterGain.connect(this.ctx.destination);
                const ctx = this.ctx;
                const masterGain = this.masterGain;
                if (!ctx || !masterGain) return;

                audioVolume.subscribe(vol => {
                    masterGain.gain.setValueAtTime(vol, ctx.currentTime);
                });

                systemStatus.subscribe(status => {
                    this.systemStatus = status;
                });

                this.isInitialized = true;
                console.log('🔊 SoundManager Initialized');
            } catch (e) {
                console.error('Failed to initialize SoundManager:', e);
            }
        }

        /**
         * Play a short hover cue with exponential envelope $g(t)=g_0 e^{-k t}$.
         * Parameters: $g_0=0.05$, $k\approx 100$, duration $T=0.05$.
         */
        playHover() {
            if (!get(audioEnabled) || !this.ctx || !this.masterGain) return;
            if (this.systemStatus !== 'OFFLINE') return;
            if (this.ctx.state === 'suspended') this.ctx.resume();
            const masterGain = this.masterGain;

            const osc = this.ctx.createOscillator();
            const gain = this.ctx.createGain();

            osc.connect(gain);
            gain.connect(masterGain);

            osc.type = 'sine';
            osc.frequency.setValueAtTime(800, this.ctx.currentTime);
            osc.frequency.exponentialRampToValueAtTime(1200, this.ctx.currentTime + 0.05);

            gain.gain.setValueAtTime(0.05, this.ctx.currentTime);
            gain.gain.exponentialRampToValueAtTime(0.001, this.ctx.currentTime + 0.05);

            osc.start();
            osc.stop(this.ctx.currentTime + 0.05);
        }

        /**
         * Play a click cue with frequency decay $f(t)=f_0 e^{-\lambda t}$.
         * Parameters: $f_0=300$, $\lambda\approx 3$, $T=0.1$.
         */
        playClick() {
            if (!get(audioEnabled) || !this.ctx || !this.masterGain) return;
            if (this.systemStatus !== 'OFFLINE') return;
            if (this.ctx.state === 'suspended') this.ctx.resume();
            const masterGain = this.masterGain;

            const osc = this.ctx.createOscillator();
            const gain = this.ctx.createGain();

            osc.connect(gain);
            gain.connect(masterGain);

            osc.type = 'triangle';
            osc.frequency.setValueAtTime(300, this.ctx.currentTime);
            osc.frequency.exponentialRampToValueAtTime(50, this.ctx.currentTime + 0.1);

            gain.gain.setValueAtTime(0.1, this.ctx.currentTime);
            gain.gain.exponentialRampToValueAtTime(0.001, this.ctx.currentTime + 0.1);

            osc.start();
            osc.stop(this.ctx.currentTime + 0.1);
        }

        /**
         * Play a data chirp with linear sweep $f(t)=f_0 + (f_1-f_0)\tfrac{t}{T}$.
         * Parameters: $f_0=2000$, $f_1=4000$, $T=0.05$.
         */
        playDataChirp() {
            if (!get(audioEnabled) || !this.ctx || !this.masterGain) return;
            if (this.ctx.state === 'suspended') this.ctx.resume();

            const t = this.ctx.currentTime;
            const masterGain = this.masterGain;
            const osc = this.ctx.createOscillator();
            const gain = this.ctx.createGain();

            osc.connect(gain);
            gain.connect(masterGain);

            osc.type = 'sine';
            osc.frequency.setValueAtTime(2000, t);
            osc.frequency.linearRampToValueAtTime(4000, t + 0.05);

            gain.gain.setValueAtTime(0.05, t);
            gain.gain.exponentialRampToValueAtTime(0.001, t + 0.05);

            osc.start(t);
            osc.stop(t + 0.05);
        }

        /**
         * Toggle ambience with constant-frequency carrier $f(t)=40$ Hz.
         * Parameter: gain $g=0.005$ to avoid masking foreground alerts.
         */
        toggleHum(active: boolean) {
            if (!this.ctx || !this.masterGain) return;
            const masterGain = this.masterGain;

            if (active && !this.humOscillator && get(audioEnabled)) {
                const osc = this.ctx.createOscillator();
                const gain = this.ctx.createGain();

                osc.connect(gain);
                gain.connect(masterGain);

                osc.type = 'sawtooth';
                osc.frequency.setValueAtTime(40, this.ctx.currentTime);
                gain.gain.setValueAtTime(0.005, this.ctx.currentTime);

                osc.start();
                this.humOscillator = { osc, gain };
            } else if (!active && this.humOscillator) {
                this.humOscillator.osc.stop();
                this.humOscillator.osc.disconnect();
                this.humOscillator.gain.disconnect();
                this.humOscillator = null;
            }
        }
    }

    class WebSocketService {
        ws: WebSocket | null = null;
        reconnectInterval = 5000;
        url: string;

        constructor() {
            // @ts-expect-error vite env typing
            const apiBase = import.meta.env.VITE_API_URL || 'http://localhost:8002';
            // @ts-expect-error vite env typing
            const wsBase = import.meta.env.VITE_WS_URL || apiBase.replace(/^http/, 'ws');
            this.url = wsBase.endsWith('/ws') ? wsBase : `${wsBase}/ws`;
            console.log(`[WebSocket] Initialized with URL: ${this.url}`);
        }

        /**
         * Connect and stream updates with deterministic retry delay $\Delta t=5000$ ms.
         */
        connect() {
            if (this.ws) return;

            console.log(`Connecting to WebSocket: ${this.url}`);
            this.ws = new WebSocket(this.url);

            this.ws.onopen = () => {
                console.log('✅ WebSocket Connected');
                isConnected.set(true);
                systemStatus.set('ONLINE');
            };

            this.ws.onmessage = (event: MessageEvent) => {
                try {
                    const message = JSON.parse(event.data);
                    switch (message.type) {
                        case 'news':
                        case 'discovery':
                        case 'news_event': {
                            let article = message.payload;
                            if (typeof article === 'string') {
                                article = JSON.parse(article);
                            }
                            newsEvents.set(article);
                            break;
                        }
                        case 'log':
                        case 'log_entry':
                            systemLogs.update(logs => {
                                const newLogs = [message.payload, ...logs];
                                if (newLogs.length > 100) newLogs.pop();
                                return newLogs;
                            });
                            break;
                        default:
                            console.log('Unknown WS Message:', message);
                    }
                } catch (e) {
                    console.error('WS Parse Error:', e);
                }
            };

            this.ws.onclose = () => {
                console.log('⚠️ WebSocket Closed');
                isConnected.set(false);
                setOfflineTelemetry();
                systemStatus.set('OFFLINE');
                this.ws = null;
                setTimeout(() => this.connect(), this.reconnectInterval);
            };

            this.ws.onerror = (e: Event) => {
                console.error('WebSocket Error:', e);
            };
        }
    }

    const soundManager = new SoundManager();
    const webSocketService = new WebSocketService();
    setContext('soundManager', soundManager);

    let totalSources = 0;
    let healthCheckTimer: ReturnType<typeof setTimeout>;
    let retryCount = 0;
    let isLoading = true;

    let activeTab = 'health';
    let showFlagDiagnostics = false;
    const flagDiagnosticAlpha2 = ['US', 'CN', 'GB', 'FR', 'DE', 'JP', 'IN', 'BR', 'RU', 'ZA'];

    let logContainer: HTMLElement | null = null;

    let isDragging = false;
    let draggingId: string | null = null;
    let dragOffset = { x: 0, y: 0 };

    let mouseX = 0;
    let mouseY = 0;
    let hudX = 0;
    let hudY = 0;
    let frameX = 0;
    let frameY = 0;

    let brainStats = {
        top_entities: [],
        narrative_divergence: {
            tier_0_sentiment: 0,
            tier_2_sentiment: 0,
            divergence: 0,
            alert: false
        }
    };
    let brainLoading = true;

    const windows: Array<{ id: string; title: string; icon: string; width: string; height: string }> = [
        { id: 'systemMonitor', title: 'SYSTEM MONITOR', icon: '📡', width: '560px', height: '640px' },
        { id: 'brain', title: 'BRAIN', icon: '🧠', width: '420px', height: '360px' }
    ];

    $: isOffline = $systemStatus === 'OFFLINE';
    $: disabledClass = isOffline ? 'opacity-50 pointer-events-none grayscale' : '';
    let isExpanded = true;

    $: divergenceColor = brainStats?.narrative_divergence?.alert ? 'text-red-500' : 'text-green-500';

    afterUpdate(() => {
        if (logContainer) {
            logContainer.scrollTop = logContainer.scrollHeight;
        }
    });

    /**
     * Health check with exponential backoff $\Delta t_n=\min(\Delta t_0 2^{n-1}, \Delta t_{max})$.
     * Parameters: $\Delta t_0=5000$ ms, $\Delta t_{max}=60000$ ms.
     */
    function setOfflineTelemetry() {
        serviceStatus.set({ postgres: 'unknown', redis: 'unknown' });
        backendThreadStatus.set({ crawler: 'unknown', analyzer: 'unknown', cleanup: 'unknown' });
    }

    async function checkSystemHealth() {
        const controller = new AbortController();
        const abortTimer = setTimeout(() => controller.abort(), 4000);
        try {
            // @ts-expect-error vite env typing
            const apiBase = import.meta.env.VITE_API_URL || import.meta.env.VITE_API_BASE_URL || 'http://localhost:8002';
            const response = await fetch(`${apiBase}/health/full`, { signal: controller.signal });
            if (response.ok) {
                const data = await response.json();
                if (data.services) serviceStatus.set(data.services);
                if (data.threads) backendThreadStatus.set(data.threads);

                if (data.status === 'ok') {
                    systemStatus.set('ONLINE');
                    retryCount = 0;
                } else if (data.status === 'degraded') {
                    systemStatus.set('DEGRADED');
                    retryCount = 0;
                } else {
                    systemStatus.set('OFFLINE');
                    retryCount++;
                }
            } else {
                setOfflineTelemetry();
                systemStatus.set('OFFLINE');
                retryCount++;
            }
        } catch (error) {
            console.warn('Health check failed:', error);
            setOfflineTelemetry();
            systemStatus.set('OFFLINE');
            retryCount++;
        } finally {
            clearTimeout(abortTimer);
            setTimeout(() => {
                isLoading = false;
            }, 500);
        }

        let nextDelay = 30000;
        if ($systemStatus === 'OFFLINE') {
            const base = 5000;
            const cap = 60000;
            nextDelay = Math.min(base * Math.pow(2, Math.max(0, retryCount - 1)), cap);
            console.log(`System OFFLINE. Next check in ${nextDelay / 1000}s (Retry ${retryCount})`);
        }

        healthCheckTimer = setTimeout(checkSystemHealth, nextDelay);
    }

    function handleMouseMove(e: MouseEvent) {
        soundManager.init();
        const { clientX, clientY } = e;
        const { innerWidth, innerHeight } = window;
        mouseX = (clientX / innerWidth) * 2 - 1;
        mouseY = (clientY / innerHeight) * 2 - 1;
    }

    function toggleWindow(id: string) {
        windowState.update(s => {
            const win = s[id];
            if (win && win.visible) {
                win.visible = false;
            } else if (win) {
                win.visible = true;
                win.minimized = false;
            }
            return { ...s, [id]: win };
        });
    }

    function startDrag(id: string, e: MouseEvent) {
        if ($windowState[id]?.maximized) return;
        soundManager.playClick();
        isDragging = true;
        draggingId = id;
        dragOffset.x = e.clientX - $windowState[id].position.x;
        dragOffset.y = e.clientY - $windowState[id].position.y;
        window.addEventListener('mousemove', handleDrag);
        window.addEventListener('mouseup', stopDrag);
    }

    function handleDrag(e: MouseEvent) {
        const activeId = draggingId;
        if (!isDragging || !activeId) return;
        const newX = e.clientX - dragOffset.x;
        const newY = e.clientY - dragOffset.y;
        windowState.update(s => ({
            ...s,
            [activeId]: { ...s[activeId], position: { x: newX, y: newY } }
        }));
    }

    function stopDrag() {
        isDragging = false;
        draggingId = null;
        window.removeEventListener('mousemove', handleDrag);
        window.removeEventListener('mouseup', stopDrag);
    }

    function toggleMinimize(id: string) {
        soundManager.playHover();
        windowState.update(s => ({
            ...s,
            [id]: { ...s[id], minimized: !s[id].minimized }
        }));
    }

    function closeWindow(id: string) {
        windowState.update(s => ({
            ...s,
            [id]: { ...s[id], visible: false }
        }));
    }

    function bringToFront(id: string) {
        windowState.update(s => {
            let maxZ = 10;
            Object.values(s).forEach(w => {
                if (w.zIndex && w.zIndex > maxZ) maxZ = w.zIndex;
            });
            return {
                ...s,
                [id]: { ...s[id], zIndex: maxZ + 1 }
            };
        });
    }

    function toggleSound() {
        $soundEnabled = !$soundEnabled;
    }

    async function fetchHeaderStats() {
        try {
            // @ts-expect-error vite env typing
            const apiBase = import.meta.env.VITE_API_URL || import.meta.env.VITE_API_BASE_URL || 'http://localhost:8002';
            const res = await fetch(`${apiBase}/api/map-data`);
            if (res.ok) {
                const data = await res.json();
                if (data.total_sources) {
                    totalSources = data.total_sources;
                }
            }
        } catch (e) {
            console.error('Failed to fetch map stats:', e);
        }
    }

    function formatBigNumber(num: number) {
        if (num >= 1000000) {
            return (num / 1000000).toFixed(3) + ' M';
        }
        return num.toLocaleString();
    }

    /**
     * Dispatch crawler control with bounded latency budget $T \leq 5\text{s}$ and explicit action $a \in \{\text{start, stop, restart}\}$.
     * Research motivation: stabilize data ingestion to preserve downstream inference validity.
     * @param {string} action
     */
    async function controlCrawler(action: string) {
        isCrawlerLoading = true;
        crawlerMessage = '';
        try {
            // @ts-expect-error vite env typing
            const apiBase = import.meta.env.VITE_API_URL || import.meta.env.VITE_API_BASE_URL || 'http://localhost:8002';
            const res = await fetch(`${apiBase}/api/system/crawler/${action}`, { method: 'POST' });
            const data = await res.json();
            if (res.ok) {
                crawlerMessage = `Command '${action}' executed: ${data.status}`;
                await refreshStatus();
            } else {
                crawlerMessage = `Error: ${data.detail || 'Unknown error'}`;
            }
        } catch (e) {
            const error = e instanceof Error ? e : new Error(String(e));
            crawlerMessage = `Network Error: ${error.message}`;
        } finally {
            isCrawlerLoading = false;
        }
    }

    /**
     * Refresh backend thread status to reduce staleness error $\epsilon(t)=\|\hat{s}(t)-s(t)\|$.
     */
    async function refreshStatus() {
        try {
            // @ts-expect-error vite env typing
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
     * Trigger auto-recovery policy with single-shot action $u(t)=1$ to mitigate cascading failure.
     */
    async function triggerHeal() {
        isCrawlerLoading = true;
        crawlerMessage = 'Initiating self-healing...';
        try {
            // @ts-expect-error vite env typing
            const apiBase = import.meta.env.VITE_API_URL || import.meta.env.VITE_API_BASE_URL || 'http://localhost:8002';
            const res = await fetch(`${apiBase}/api/system/health/autoheal`, { method: 'POST' });
            const data = await res.json();
            crawlerMessage = `Heal Result: ${data.status}`;
            if (data.self_heal && data.self_heal.actions) {
                crawlerMessage += ` | Actions: ${data.self_heal.actions.join(', ')}`;
            }
            await refreshStatus();
        } catch (e) {
            const error = e instanceof Error ? e : new Error(String(e));
            crawlerMessage = `Heal Failed: ${error.message}`;
        } finally {
            isCrawlerLoading = false;
        }
    }

    /**
     * Fetch narrative metrics and entities, treating divergence as $\Delta = \mu_{T0}-\mu_{T2}$.
     */
    async function fetchBrainStats() {
        brainLoading = true;
        try {
            // @ts-expect-error vite env typing
            const apiBase = import.meta.env.VITE_API_URL ||
                (window.location.hostname === 'localhost'
                    ? 'http://localhost:8002'
                    : 'https://globemediapulse-backend-production.fly.dev');
            const res = await fetch(`${apiBase}/api/stats/brain`);
            if (res.ok) {
                brainStats = await res.json();
            }
        } catch (e) {
            console.error(e);
        } finally {
            brainLoading = false;
        }
    }

    let isCrawlerLoading = false;
    let crawlerMessage = '';

    onMount(() => {
        checkSystemHealth();
        webSocketService.connect();

        const initAudio = () => {
            soundManager.init();
            window.removeEventListener('click', initAudio);
            window.removeEventListener('keydown', initAudio);
        };
        window.addEventListener('click', initAudio);
        window.addEventListener('keydown', initAudio);

        fetchHeaderStats();
        const statsInterval = setInterval(fetchHeaderStats, 60000);

        fetchBrainStats();
        const brainInterval = setInterval(fetchBrainStats, 60000);

        let frame: number;
        function loop() {
            hudX += (mouseX * -15 - hudX) * 0.1;
            hudY += (mouseY * -15 - hudY) * 0.1;
            frameX += (mouseX * -5 - frameX) * 0.1;
            frameY += (mouseY * -5 - frameY) * 0.1;
            frame = requestAnimationFrame(loop);
        }
        loop();

        return () => {
            cancelAnimationFrame(frame);
            clearTimeout(healthCheckTimer);
            clearInterval(statsInterval);
            clearInterval(brainInterval);
            window.removeEventListener('mousemove', handleDrag);
            window.removeEventListener('mouseup', stopDrag);
        };
    });

    onDestroy(() => {
        clearTimeout(healthCheckTimer);
    });

    function getStatusColor(status?: string) {
        if (status === 'ok' || status === 'running' || status === 'active') return 'text-green-400';
        if (status === 'degraded' || status === 'warning') return 'text-yellow-400';
        if (status === 'disabled' || status === 'unknown') return 'text-gray-400';
        return 'text-red-400';
    }

    function getLevelColor(level?: string) {
        switch (level) {
            case 'INFO': return 'text-green-400';
            case 'WARNING': return 'text-yellow-400';
            case 'ERROR': return 'text-red-500 font-bold';
            case 'CRITICAL': return 'text-red-600 font-bold bg-white/10';
            case 'DEBUG': return 'text-blue-400';
            case 'TRACE': return 'text-purple-400';
            default: return 'text-gray-400';
        }
    }

    function getSubTypeStyle(subType?: string) {
        if (!subType) return '';
        if (subType.includes('START')) return 'text-cyan-400 font-bold';
        if (subType.includes('COMPLETE')) return 'text-green-400 font-bold';
        if (subType.includes('FAIL')) return 'text-red-400 font-bold';
        if (subType.includes('WHOIS')) return 'text-yellow-300';
        if (subType.includes('NLP')) return 'text-pink-300';
        if (subType.includes('STEP')) return 'text-blue-300 italic';
        if (subType.includes('CONSENSUS')) return 'text-purple-300';
        return 'text-gray-300';
    }

    function formatDetails(details: unknown) {
        if (!details) return [];
        if (typeof details === 'string') return [details];
        if (Array.isArray(details)) return details;
        return [JSON.stringify(details)];
    }
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
                {#each Array.from({ length: 10 }, (_, i) => i) as i (i)}
                    <div class="w-2 h-[1px] bg-white"></div>
                {/each}
            </div>
            <div class="absolute top-1/2 right-0 -translate-y-1/2 flex flex-col gap-2 items-end opacity-30">
                {#each Array.from({ length: 10 }, (_, i) => i) as i (i)}
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
            <header class="w-full h-20 flex items-center justify-between px-6 z-50 pointer-events-auto bg-[#0f172a]/85 border-b border-white/25 backdrop-blur-md select-none shadow-[0_8px_32px_rgba(0,0,0,0.5),inset_0_0_20px_rgba(255,255,255,0.08)]">
                <div class="flex items-center gap-4">
                    <div class="relative w-12 h-12 flex items-center justify-center">
                        <div class="absolute inset-0 rounded-full border border-neon-blue/30 animate-spin-slow"></div>
                        <div class="absolute w-8 h-8 rounded-full bg-neon-blue/10 animate-pulse border border-neon-blue/50 flex items-center justify-center">
                            <div class="w-4 h-4 bg-neon-blue/80 rounded-full shadow-[0_0_15px_#00f3ff]"></div>
                        </div>
                        <div class="absolute inset-0 rounded-full border-t-2 border-neon-blue/80 animate-spin shadow-[0_0_10px_#00f3ff]"></div>
                    </div>
                    <div class="flex flex-col">
                        <h1 class="text-2xl font-black tracking-tighter text-transparent bg-clip-text bg-gradient-to-r from-white via-neon-blue to-neon-purple drop-shadow-[0_0_10px_rgba(0,243,255,0.5)] font-tech">
                            GLOBE MEDIA PULSE
                        </h1>
                        <span class="text-xs tracking-[0.2em] text-neon-blue/80 font-mono font-bold">Uncharted Pulse of Global Media</span>
                    </div>
                </div>

                <div class="hidden lg:flex items-center gap-2 opacity-40">
                    <div class="w-24 h-[1px] bg-gradient-to-r from-transparent via-white to-transparent"></div>
                    <div class="w-2 h-2 border border-white rotate-45 animate-pulse"></div>
                    <div class="w-24 h-[1px] bg-gradient-to-r from-transparent via-white to-transparent"></div>
                </div>

                <div class="flex items-center gap-4">
                    <div class="hidden md:flex items-center gap-3 border-r border-white/10 pr-4">
                        <div class="flex flex-col items-end">
                            <span class="text-[10px] text-neon-blue/70 font-mono tracking-widest uppercase">SOURCES</span>
                            <span class="text-xl font-mono font-bold text-white drop-shadow-[0_0_5px_rgba(255,255,255,0.5)] flex items-center gap-2">
                                <span class="w-2 h-2 rounded-full bg-green-500 animate-pulse"></span>
                                {formatBigNumber(totalSources)}
                            </span>
                        </div>
                    </div>
                </div>
            </header>
        </div>

        <!-- Middle: Floating Windows Space -->
        <div class="flex-1 relative w-full h-full pointer-events-none">
            {#each windows as win (win.id)}
                {#if $windowState[win.id]?.visible}
                    <div 
                        class="fixed bg-[#050a14]/85 backdrop-blur-2xl border border-white/15 ring-1 ring-white/5 shadow-[0_10px_50px_rgba(0,0,0,0.8)] rounded-xl overflow-hidden flex flex-col transition-shadow duration-300 pointer-events-auto"
                        class:ring-neon-blue={isDragging && draggingId === win.id}
                        class:shadow-[0_0_30px_rgba(0,243,255,0.15)]={isDragging && draggingId === win.id}
                        style="top: {$windowState[win.id].position.y}px; left: {$windowState[win.id].position.x}px; width: {win.width}; height: {win.height}; z-index: {$windowState[win.id].zIndex || 10}; transform-origin: top left;"
                        on:mousedown={() => bringToFront(win.id)}
                        role="dialog"
                        aria-label={win.title}
                        tabindex="0"
                    >
                        <div 
                            class="h-11 bg-gradient-to-r from-white/10 via-white/5 to-transparent border-b border-white/10 flex items-center justify-between px-4 cursor-move select-none relative overflow-hidden"
                            on:mousedown={(e) => startDrag(win.id, e)}
                            role="button"
                            aria-label={`Drag ${win.title}`}
                            tabindex="0"
                        >
                            <div class="absolute top-0 left-0 w-full h-[1px] bg-gradient-to-r from-transparent via-white/20 to-transparent"></div>
                            <div class="flex items-center gap-3 text-cyan-400 font-mono text-sm tracking-widest relative z-10">
                                <span class="text-lg opacity-80 drop-shadow-[0_0_5px_rgba(34,211,238,0.5)]">{win.icon}</span>
                                <span class="font-bold drop-shadow-md">{win.title}</span>
                            </div>
                            <div class="flex items-center gap-2">
                                <button 
                                    class="w-6 h-6 flex items-center justify-center rounded hover:bg-white/10 text-gray-400 hover:text-white transition-colors"
                                    on:click={() => toggleMinimize(win.id)}
                                    title={$windowState[win.id].minimized ? 'Restore' : 'Minimize'}
                                >
                                    <span class="material-icons-round text-sm">
                                        {$windowState[win.id].minimized ? 'open_in_full' : 'minimize'}
                                    </span>
                                </button>
                                <button 
                                    class="w-6 h-6 flex items-center justify-center rounded hover:bg-red-500/20 text-gray-400 hover:text-red-400 transition-colors"
                                    on:click={() => closeWindow(win.id)}
                                    title="Close"
                                >
                                    <span class="material-icons-round text-sm">close</span>
                                </button>
                            </div>
                        </div>

                        {#if !$windowState[win.id].minimized}
                            <div class="flex-1 min-h-0 overflow-hidden bg-transparent p-3 text-gray-300 font-mono text-sm">
                                {#if win.id === 'systemMonitor'}
                                    <div class="h-full min-h-0 flex flex-col">
                                        <div class="flex border-b border-white/10 mb-4">
                                            <button class="px-3 py-2 text-xs font-bold uppercase transition-colors flex items-center gap-1 {activeTab === 'health' ? 'text-neon-blue border-b-2 border-neon-blue' : 'text-gray-500 hover:text-white'}"
                                                    on:click={() => activeTab = 'health'}>
                                                <span class="material-icons-round text-[12px]">monitor_heart</span>
                                                Health
                                            </button>
                                            <button class="px-3 py-2 text-xs font-bold uppercase transition-colors flex items-center gap-1 {activeTab === 'logs' ? 'text-neon-blue border-b-2 border-neon-blue' : 'text-gray-500 hover:text-white'}"
                                                    on:click={() => activeTab = 'logs'}>
                                                <span class="material-icons-round text-[12px]">terminal</span>
                                                Logs
                                            </button>
                                            <button class="px-3 py-2 text-xs font-bold uppercase transition-colors flex items-center gap-1 {activeTab === 'controls' ? 'text-neon-blue border-b-2 border-neon-blue' : 'text-gray-500 hover:text-white'}"
                                                    on:click={() => activeTab = 'controls'}>
                                                <span class="material-icons-round text-[12px]">tune</span>
                                                Controls
                                            </button>
                                        </div>

                                        <div class="flex-1 min-h-0 overflow-hidden overflow-y-hidden pr-1 pl-1">
                                            {#if activeTab === 'health'}
                                                <div class="h-full overflow-hidden space-y-4">
                                                    <div class="bg-white/5 p-3 rounded border border-white/10">
                                                        <h4 class="text-neon-blue font-bold text-xs uppercase mb-2 flex items-center gap-2">
                                                            <span class="material-icons-round text-sm">dns</span>
                                                            System Health
                                                        </h4>

                                                        <div class="mb-3">
                                                            <div class="text-[10px] text-gray-400 mb-1 font-mono uppercase">Infrastructure</div>
                                                            <div class="grid grid-cols-2 gap-2 text-xs">
                                                                <div class="flex justify-between bg-black/20 p-1.5 rounded">
                                                                    <span class="flex items-center gap-1">
                                                                        <span class="material-icons-round text-[10px] text-neon-blue/70">storage</span>
                                                                        Postgres
                                                                    </span>
                                                                    <span class="font-mono {getStatusColor($serviceStatus.postgres)}">{$serviceStatus.postgres?.toUpperCase() || 'UNK'}</span>
                                                                </div>
                                                                <div class="flex justify-between bg-black/20 p-1.5 rounded">
                                                                    <span class="flex items-center gap-1">
                                                                        <span class="material-icons-round text-[10px] text-neon-blue/70">bolt</span>
                                                                        Redis
                                                                    </span>
                                                                    <span class="font-mono {getStatusColor($serviceStatus.redis)}">{$serviceStatus.redis?.toUpperCase() || 'UNK'}</span>
                                                                </div>
                                                            </div>
                                                        </div>

                                                        <div>
                                                            <div class="text-[10px] text-gray-400 mb-1 font-mono uppercase">Active Threads</div>
                                                            <div class="space-y-1 text-xs">
                                                                <div class="flex justify-between bg-black/20 p-1.5 rounded border-l-2 border-neon-blue">
                                                                    <span class="flex items-center gap-1">
                                                                        <span class="material-icons-round text-[10px] text-neon-blue/70">public</span>
                                                                        News Crawler
                                                                    </span>
                                                                    <span class="font-mono {getStatusColor($backendThreadStatus.crawler)}">{$backendThreadStatus.crawler?.toUpperCase() || 'UNK'}</span>
                                                                </div>
                                                                <div class="flex justify-between bg-black/20 p-1.5 rounded border-l-2 border-purple-500">
                                                                    <span class="flex items-center gap-1">
                                                                        <span class="material-icons-round text-[10px] text-purple-300">psychology</span>
                                                                        AI Analyzer
                                                                    </span>
                                                                    <span class="font-mono {getStatusColor($backendThreadStatus.analyzer)}">{$backendThreadStatus.analyzer?.toUpperCase() || 'UNK'}</span>
                                                                </div>
                                                                <div class="flex justify-between bg-black/20 p-1.5 rounded border-l-2 border-gray-500">
                                                                    <span class="flex items-center gap-1">
                                                                        <span class="material-icons-round text-[10px] text-gray-300">delete_sweep</span>
                                                                        System Cleanup
                                                                    </span>
                                                                    <span class="font-mono {getStatusColor($backendThreadStatus.cleanup)}">{$backendThreadStatus.cleanup?.toUpperCase() || 'UNK'}</span>
                                                                </div>
                                                            </div>
                                                        </div>

                                                        <div class="mt-3">
                                                            <div class="flex items-center justify-between mb-2">
                                                                <div class="text-[10px] text-gray-400 font-mono uppercase">Flag Diagnostics</div>
                                                                <button
                                                                    class="text-[10px] font-mono px-2 py-1 rounded bg-black/20 border border-white/10 hover:bg-black/30 transition-colors"
                                                                    on:click={() => showFlagDiagnostics = !showFlagDiagnostics}
                                                                >
                                                                    {showFlagDiagnostics ? 'HIDE' : 'SHOW'}
                                                                </button>
                                                            </div>

                                                            {#if showFlagDiagnostics}
                                                                <div class="grid grid-cols-2 gap-2 text-xs">
                                                                    {#each flagDiagnosticAlpha2 as alpha2 (alpha2)}
                                                                        <div class="flex items-center justify-between bg-black/20 p-1.5 rounded">
                                                                            <span class="flex items-center gap-2">
                                                                                <span class="fi fi-{alpha2.toLowerCase()} gmp-flag opacity-80" aria-label={alpha2}></span>
                                                                                <span class="font-mono tracking-wider">{alpha2}</span>
                                                                            </span>
                                                                            <span class="text-[10px] text-gray-500">fi-{alpha2.toLowerCase()}</span>
                                                                        </div>
                                                                    {/each}
                                                                </div>
                                                            {/if}
                                                        </div>
                                                    </div>
                                                </div>
                                            {:else if activeTab === 'logs'}
                                                <div class="flex flex-col h-full min-h-0 bg-black/95 font-mono text-[10px] p-2 rounded border border-green-500/30 overflow-hidden shadow-[inset_0_0_20px_rgba(0,50,0,0.2)]" data-testid="system-logs">
                                                    <div class="flex justify-between items-center mb-2 pb-2 border-b border-green-500/30 bg-black/40 -mx-2 px-2 pt-1">
                                                        <h4 class="text-neon-blue font-bold uppercase flex items-center gap-2 tracking-wider">
                                                            <span class="material-icons-round text-sm animate-pulse text-green-500">terminal</span>
                                                            <span class="text-green-500">GEOPARSING OPS CENTER</span>
                                                        </h4>
                                                        <div class="flex items-center gap-2">
                                                            <div class="flex gap-1">
                                                                <div class="w-1.5 h-1.5 rounded-full bg-green-500 animate-pulse"></div>
                                                                <div class="w-1.5 h-1.5 rounded-full bg-green-500/50 animate-pulse delay-75"></div>
                                                                <div class="w-1.5 h-1.5 rounded-full bg-green-500/30 animate-pulse delay-150"></div>
                                                            </div>
                                                            <span class="text-xs text-green-500/70">{$systemLogs.length} OPS</span>
                                                        </div>
                                                    </div>

                                                    <div bind:this={logContainer} class="flex-1 overflow-y-auto space-y-0.5 font-mono leading-tight pr-1" data-testid="system-logs-scroll">
                                                        {#each $systemLogs as log (log.timestamp + Math.random())}
                                                            <div class="group flex flex-col gap-0.5 hover:bg-green-500/5 transition-colors px-1 py-1 border-l-[3px] border-b border-white/5"
                                                                 class:border-transparent={!log.level || log.level === 'INFO'}
                                                                 class:border-l-red-500={log.level === 'ERROR' || log.level === 'CRITICAL'}
                                                                 class:border-l-yellow-500={log.level === 'WARNING'}
                                                                 class:border-l-cyan-500={log.sub_type && log.sub_type.includes('START')}
                                                                 class:border-l-green-500={log.sub_type && log.sub_type.includes('COMPLETE')}>

                                                                <div class="flex gap-2 items-center">
                                                                    <span class="text-gray-600 min-w-[50px] opacity-70">{new Date(log.timestamp * 1000).toLocaleTimeString([], {hour12: false, hour: '2-digit', minute:'2-digit', second:'2-digit'})}</span>
                                                                    {#if log.sub_type}
                                                                        <span class="min-w-[80px] text-right {getSubTypeStyle(log.sub_type)}">[{log.sub_type}]</span>
                                                                    {:else}
                                                                        <span class="min-w-[40px] text-right {getLevelColor(log.level)}">[{log.level || 'INFO'}]</span>
                                                                    {/if}
                                                                    <span class="text-gray-300 break-all flex-1 font-bold">
                                                                        {#if log.data && log.data.domain}
                                                                            <span class="text-white">TARGET: {log.data.domain}</span>
                                                                        {:else}
                                                                            {log.message}
                                                                        {/if}
                                                                    </span>
                                                                </div>

                                                                {#if log.data}
                                                                    <div class="pl-[140px] text-gray-400 flex flex-col gap-0.5">
                                                                        {#if log.data.step}
                                                                            <div class="flex items-center gap-2 text-cyan-300">
                                                                                <span class="material-icons-round text-[10px]">arrow_right</span>
                                                                                <span class="uppercase text-[9px] border border-cyan-500/30 px-1 rounded">{log.data.step}</span>
                                                                                <span class="text-gray-300">{log.data.message}</span>
                                                                            </div>
                                                                        {/if}

                                                                        {#if log.data.result}
                                                                            <div class="flex items-center gap-2 mt-1">
                                                                                <span class="text-green-400 font-bold">>> LOCKED: {log.data.result}</span>
                                                                                <span class="text-xs border border-green-500/50 px-1 rounded text-green-300 bg-green-900/20">CONFIDENCE: {log.data.confidence?.toUpperCase()}</span>
                                                                            </div>
                                                                        {/if}

                                                                        {#if log.data.details}
                                                                            <div class="mt-1 pl-2 border-l border-gray-700 space-y-0.5">
                                                                                {#each formatDetails(log.data.details) as detail, index (index)}
                                                                                    <div class="text-[9px] text-gray-500 flex items-center gap-1">
                                                                                        <span class="w-1 h-1 bg-gray-600 rounded-full"></span>
                                                                                        {detail}
                                                                                    </div>
                                                                                {/each}
                                                                            </div>
                                                                        {/if}

                                                                        {#if log.data.error}<span class="text-red-400 bg-red-900/20 px-1">ERROR: {log.data.error}</span>{/if}
                                                                    </div>
                                                                {/if}
                                                            </div>
                                                        {/each}

                                                        {#if $systemLogs.length === 0}
                                                            <div class="flex flex-col items-center justify-center h-full opacity-30">
                                                                <span class="material-icons-round text-4xl mb-2">satellite_alt</span>
                                                                <span class="text-xs tracking-widest">AWAITING TELEMETRY...</span>
                                                            </div>
                                                        {/if}

                                                        <div class="h-4 flex items-center pl-1">
                                                            <span class="w-2 h-4 bg-neon-blue/50 animate-pulse"></span>
                                                        </div>
                                                    </div>
                                                </div>
                                            {:else if activeTab === 'controls'}
                                                <div class="flex flex-col h-full min-h-0 gap-2 overflow-hidden overflow-y-hidden" data-testid="system-controls">
                                                    <div class="bg-white/5 p-1.5 rounded border border-white/10 flex-1 min-h-0 overflow-hidden">
                                                        <h4 class="text-neon-pink font-bold text-xs uppercase mb-2 flex items-center gap-2">
                                                            <span class="material-icons-round text-sm">bug_report</span>
                                                            Crawler Control
                                                        </h4>

                                                        <div class="grid grid-cols-3 gap-2 mb-2">
                                                            <button class="flex flex-col items-center justify-center p-2 rounded bg-white/5 hover:bg-white/10 transition-all border border-white/10 text-[10px] font-bold text-green-400 hover:border-green-400/50 disabled:opacity-50 disabled:cursor-not-allowed" on:click={() => controlCrawler('start')} disabled={isCrawlerLoading || $backendThreadStatus.crawler === 'running'}>
                                                                <span class="material-icons-round text-sm">play_arrow</span> START
                                                            </button>
                                                            <button class="flex flex-col items-center justify-center p-2 rounded bg-white/5 hover:bg-white/10 transition-all border border-white/10 text-[10px] font-bold text-red-400 hover:border-red-400/50 disabled:opacity-50 disabled:cursor-not-allowed" on:click={() => controlCrawler('stop')} disabled={isCrawlerLoading || $backendThreadStatus.crawler !== 'running'}>
                                                                <span class="material-icons-round text-sm">stop</span> STOP
                                                            </button>
                                                            <button class="flex flex-col items-center justify-center p-2 rounded bg-white/5 hover:bg-white/10 transition-all border border-white/10 text-[10px] font-bold text-yellow-400 hover:border-yellow-400/50 disabled:opacity-50 disabled:cursor-not-allowed" on:click={() => controlCrawler('restart')} disabled={isCrawlerLoading}>
                                                                <span class="material-icons-round text-sm">restart_alt</span> RESTART
                                                            </button>
                                                        </div>

                                                        <div class="text-[10px] font-mono text-gray-400 bg-black/30 p-1.5 rounded min-h-[28px]">
                                                            {#if isCrawlerLoading}
                                                                <span class="animate-pulse">Processing command...</span>
                                                            {:else}
                                                                {crawlerMessage || 'Ready for command.'}
                                                            {/if}
                                                        </div>
                                                    </div>

                                                    <div class="bg-white/5 p-1.5 rounded border border-white/10 flex-1 min-h-0 overflow-hidden">
                                                        <h4 class="text-purple-400 font-bold text-xs uppercase mb-2 flex items-center gap-2">
                                                            <span class="material-icons-round text-sm">health_and_safety</span>
                                                            System Guardian
                                                        </h4>

                                                        <div class="flex justify-between items-center bg-black/20 p-1.5 rounded mb-2">
                                                            <div class="text-xs text-gray-300">Auto-Recovery Protocol</div>
                                                            <button class="px-2 py-1 bg-purple-500/20 text-purple-400 border border-purple-500/50 rounded text-[10px] hover:bg-purple-500/40 flex items-center gap-1"
                                                                    on:click={triggerHeal}
                                                                    disabled={isCrawlerLoading}>
                                                                <span class="material-icons-round text-[12px]">auto_fix_high</span>
                                                                FORCE HEAL
                                                            </button>
                                                        </div>

                                                        <div class="text-[10px] text-gray-500 flex items-center gap-2">
                                                            <span>Current Status:</span>
                                                            <span class="flex items-center gap-1">
                                                                <span class="material-icons-round text-[11px]"
                                                                      class:text-green-400={$backendThreadStatus.crawler === 'running'}
                                                                      class:text-red-400={$backendThreadStatus.crawler !== 'running'}>
                                                                    {$backendThreadStatus.crawler === 'running' ? 'power' : 'power_settings_new'}
                                                                </span>
                                                                <span class:text-green-400={$backendThreadStatus.crawler === 'running'}
                                                                      class:text-red-400={$backendThreadStatus.crawler !== 'running'}>
                                                                    CRAWLER: {$backendThreadStatus.crawler?.toUpperCase() || 'UNK'}
                                                                </span>
                                                            </span>
                                                        </div>
                                                    </div>
                                                </div>
                                            {/if}
                                        </div>
                                    </div>
                                {:else if win.id === 'brain'}
                                    <div class="h-full flex flex-col space-y-4">
                                        <div class="bg-white/5 p-3 rounded">
                                            <h4 class="text-neon-pink font-bold text-xs uppercase mb-2">Narrative Conflict Monitor</h4>
                                            <div class="flex justify-between items-center text-xs mb-2">
                                                <span>Divergence:</span>
                                                <span class="font-bold {divergenceColor}">{(brainStats?.narrative_divergence?.divergence || 0).toFixed(2)}</span>
                                            </div>

                                            <div class="space-y-1">
                                                <div class="flex justify-between text-[10px] text-gray-400">
                                                    <span>Tier-0 (Global)</span>
                                                    <span>{(brainStats?.narrative_divergence?.tier_0_sentiment || 0).toFixed(2)}</span>
                                                </div>
                                                <div class="w-full bg-white/10 h-1 rounded overflow-hidden">
                                                    <div class="h-full bg-blue-500" style="width: {((brainStats?.narrative_divergence?.tier_0_sentiment || 0) + 1) * 50}%"></div>
                                                </div>

                                                <div class="flex justify-between text-[10px] text-gray-400 mt-2">
                                                    <span>Tier-2 (Local)</span>
                                                    <span>{(brainStats?.narrative_divergence?.tier_2_sentiment || 0).toFixed(2)}</span>
                                                </div>
                                                <div class="w-full bg-white/10 h-1 rounded overflow-hidden">
                                                    <div class="h-full bg-green-500" style="width: {((brainStats?.narrative_divergence?.tier_2_sentiment || 0) + 1) * 50}%"></div>
                                                </div>
                                            </div>
                                        </div>

                                        <div class="bg-white/5 p-3 rounded">
                                            <h4 class="text-yellow-400 font-bold text-xs uppercase mb-2">Top Entities (24h)</h4>
                                            <div class="flex flex-wrap gap-2">
                                                {#each (brainStats?.top_entities || []) as entity (entity)}
                                                    <span class="px-2 py-1 bg-white/10 rounded text-[10px] text-gray-300 border border-white/5">
                                                        {entity}
                                                    </span>
                                                {/each}
                                            </div>
                                            {#if brainLoading}
                                                <div class="text-[10px] text-gray-500 mt-2">Loading…</div>
                                            {/if}
                                        </div>
                                    </div>
                                {/if}
                            </div>
                        {/if}
                    </div>
                {/if}
            {/each}
        </div>

        <!-- Bottom: Command Bar -->
        <div class="w-full flex justify-center pb-4 pointer-events-auto">
            <div class="fixed bottom-6 left-1/2 -translate-x-1/2 z-50 pointer-events-auto select-none flex flex-col items-center gap-2 transition-all duration-700 ease-in-out">
                <div class="
                    h-14 
                    {isExpanded ? 'px-4 w-auto' : 'px-2 w-14 justify-center'} 
                    bg-[#0f172a]/85 backdrop-blur-md rounded-full border border-white/25 shadow-[0_8px_32px_rgba(0,0,0,0.5),inset_0_0_20px_rgba(255,255,255,0.08)] 
                    flex items-center gap-4 relative overflow-hidden group transition-all duration-500 hover:bg-[#0f172a]/95
                ">
                    <div class="absolute inset-0 bg-gradient-to-r from-neon-blue/20 via-transparent to-neon-pink/20 pointer-events-none rounded-full blur-md opacity-50 group-hover:opacity-80 transition-opacity"></div>

                    {#if !isExpanded}
                        <button 
                            class="w-10 h-10 rounded-full flex items-center justify-center text-neon-blue/80 hover:text-neon-blue hover:bg-white/10 transition-all"
                            on:click={() => isExpanded = true}
                            title="Expand Control Bar"
                        >
                            <span class="material-icons-round text-xl">menu</span>
                        </button>
                    {/if}

                    {#if isExpanded}
                        <button 
                            class="flex items-center gap-1 bg-white/10 rounded-full p-0.5 border border-white/10 hover:bg-white/20 hover:border-white/30 transition-all cursor-pointer group shrink-0"
                            title="Toggle System Monitor"
                            on:click={() => toggleWindow('systemMonitor')}
                        >
                            <div class="h-7 px-2 rounded-full flex items-center gap-1.5 justify-center">
                                {#if $systemStatus === 'OFFLINE'}
                                    <div class="w-1.5 h-1.5 rounded-full bg-red-500 shadow-[0_0_8px_rgba(239,68,68,0.8)] animate-pulse"></div>
                                    <span class="material-icons-round text-[12px] text-red-500/80">power_settings_new</span>
                                    <span class="text-[10px] font-mono text-red-500/80 font-bold tracking-wider group-hover:text-red-400">OFFLINE</span>
                                {:else if $systemStatus === 'DEGRADED'}
                                    <div class="w-1.5 h-1.5 rounded-full bg-yellow-500 shadow-[0_0_8px_rgba(234,179,8,0.8)] animate-pulse"></div>
                                    <span class="material-icons-round text-[12px] text-yellow-500/80">report_problem</span>
                                    <span class="text-[10px] font-mono text-yellow-500/80 font-bold tracking-wider group-hover:text-yellow-400">DEGRADED</span>
                                {:else}
                                    <div class="w-1.5 h-1.5 rounded-full bg-emerald-500 shadow-[0_0_8px_rgba(16,185,129,0.8)] animate-pulse"></div>
                                    <span class="material-icons-round text-[12px] text-emerald-500/80">check_circle</span>
                                    <span class="text-[10px] font-mono text-emerald-500/80 font-bold tracking-wider group-hover:text-emerald-400">ONLINE</span>
                                {/if}
                            </div>
                        </button>

                        <div class="w-[1px] h-6 bg-white/10"></div>

                        <div class="flex items-center gap-1 {disabledClass}">
                            <button 
                                class="w-7 h-7 rounded-full flex items-center justify-center transition-all duration-300 relative group/btn 
                                {$windowState.brain?.visible && !$windowState.brain?.minimized ? 'bg-white/10 text-neon-blue shadow-[0_0_15px_rgba(0,243,255,0.2)] border border-neon-blue/30' : 'text-gray-400 hover:text-white hover:bg-white/10 border border-transparent hover:border-white/10'}"
                                on:click={() => toggleWindow('brain')}
                                title="BRAIN"
                            >
                                <span class="material-icons-round text-lg relative z-10">🧠</span>
                            </button>
                        </div>

                        <div class="w-[1px] h-6 bg-white/15"></div>

                        <div class="flex items-center gap-1 {disabledClass}">
                            <button 
                                class="w-7 h-7 rounded-full flex items-center justify-center transition-all duration-300 relative group/btn
                                {$soundEnabled ? 'text-neon-blue' : 'text-gray-500'}"
                                on:click={toggleSound}
                                title={$soundEnabled ? 'Sound: ON' : 'Sound: OFF'}
                                aria-pressed={$soundEnabled}
                            >
                                <span class="material-icons-round text-lg relative z-10">{$soundEnabled ? 'volume_up' : 'volume_off'}</span>
                                {#if !$soundEnabled}
                                    <span class="absolute inset-0 flex items-center justify-center pointer-events-none">
                                        <span class="material-icons-round text-[10px] opacity-60">do_not_disturb_on</span>
                                    </span>
                                {/if}
                            </button>
                        </div>

                        <div class="w-[1px] h-6 bg-white/15"></div>
                        <button 
                            class="w-6 h-6 rounded-full flex items-center justify-center text-gray-400 hover:text-white transition-all"
                            on:click={() => isExpanded = false}
                            title="Collapse Control Bar"
                        >
                            <span class="material-icons-round text-sm">chevron_right</span>
                        </button>
                    {/if}
                </div>
            </div>
        </div>
    </div>
</main>

<style>
    .scrollbar-hide::-webkit-scrollbar {
        display: none;
    }
    .scrollbar-hide {
        -ms-overflow-style: none;
        scrollbar-width: none;
    }
</style>
