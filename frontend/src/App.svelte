<script lang="ts">
    import { onMount, onDestroy, setContext } from 'svelte';
    import { get } from 'svelte/store';
    import {
        serviceStatus,
        systemStatus,
        backendThreadStatus,
        systemLogs,
        isConnected,
        newsEvents,
        soundEnabled,
        audioEnabled,
        audioVolume,
        mapCommand,
        mediaProfileStats,
    } from './lib/stores.js';
    import MapContainer from './lib/components/MapContainer.svelte';
    import { DATA } from './lib/data.js';

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
            this.url = '';
        }

        /**
         * Connect and stream updates with deterministic retry delay $\Delta t=5000$ ms.
         */
        connect() {
            if (isStaticMode()) return;
            if (!this.url) {
                const apiBase = resolveApiBase();
                const wsBase = resolveWsBase(apiBase);
                this.url = wsBase ? (wsBase.endsWith('/ws') ? wsBase : `${wsBase}/ws`) : '';
            }
            if (!this.url) return;
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
                if (isStaticMode()) return;
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

    function getViteEnv(): { VITE_API_URL?: string; VITE_API_BASE_URL?: string; VITE_WS_URL?: string; VITE_STATIC_MODE?: string } {
        return (
            (import.meta as {
                env?: { VITE_API_URL?: string; VITE_API_BASE_URL?: string; VITE_WS_URL?: string; VITE_STATIC_MODE?: string };
            }).env || {}
        );
    }

    function isStaticMode(): boolean {
        const env = getViteEnv();
        const forced = String(env.VITE_STATIC_MODE || '').trim().toLowerCase();
        if (forced === '1' || forced === 'true' || forced === 'yes') return true;
        return window.location.hostname !== 'localhost' && !env.VITE_API_URL && !env.VITE_API_BASE_URL;
    }

    function resolveApiBase(): string {
        if (isStaticMode()) return '';
        const env = getViteEnv();
        return (
            env.VITE_API_URL ||
            env.VITE_API_BASE_URL ||
            (window.location.hostname === 'localhost' ? 'http://localhost:8002' : '')
        );
    }

    function resolveWsBase(apiBase: string): string {
        const env = getViteEnv();
        return env.VITE_WS_URL || apiBase.replace(/^http/, 'ws');
    }

    let totalSources = 0;
    let healthCheckTimer: ReturnType<typeof setTimeout>;
    let retryCount = 0;
    let isLoading = true;
    let apiOk = false;
    let apiLatencyMs: number | null = null;
    let healthUpdatedAt = 0;
    let uiNow = Date.now();
    let gdeMetrics: {
        gde: number;
        shannon_entropy: number;
        normalized_shannon: number;
        geographic_dispersion_km: number;
        normalized_dispersion: number;
        country_count: number;
        total_visits: number;
        window_hours: number;
        gini_coefficient: number;
        alpha: number;
    } | null = null;
    const gdeWindowOptions = [6, 12, 24, 72];
    const gdeAlphaOptions = [0.4, 0.6, 0.8];
    let gdeWindowHours = 24;
    let gdeAlpha = 0.6;
    let growthMetrics: Array<{
        day: string;
        media_sources_net: number;
        candidate_sources_growth_rate: number;
        news_articles_net: number;
        media_sources_count: number;
        candidate_sources_count: number;
        news_articles_count: number;
    }> = [];

    let activeView: 'health' | 'autoheal' | 'gde' = 'gde';
    let expandedPanel: 'health' | 'autoheal' | 'gde' | null = 'gde';
    let sidebarCollapsed = true;
    let lastExpandedPanel: 'health' | 'autoheal' | 'gde' | null = 'gde';
    let toolsExpanded = false;
    let healthDetailExpanded = false;
    let autohealDetailExpanded = false;
    let safetyArmed = false;
    let safetyAutoDisarmTimer: ReturnType<typeof setTimeout> | null = null;
    let statusPanelExpanded = true;
    const SIDEBAR_IDLE_MS = 12000;
    let sidebarIdleTimer: ReturnType<typeof setTimeout> | null = null;
    let sidebarScrollTimer: ReturnType<typeof setTimeout> | null = null;
    let isSidebarHovered = false;
    let isSidebarScrolling = false;

    $: isOffline = $systemStatus === 'OFFLINE';
    $: isDegraded = $systemStatus === 'DEGRADED';
    $: isSystemCritical = $systemStatus === 'OFFLINE' || $systemStatus === 'DEGRADED';
    $: disabledClass = isOffline ? 'opacity-50 pointer-events-none grayscale' : '';
    $: if (isOffline) safetyArmed = false;
    $: if (expandedPanel !== 'autoheal') safetyArmed = false;
    $: if (!safetyArmed && safetyAutoDisarmTimer) {
        clearTimeout(safetyAutoDisarmTimer);
        safetyAutoDisarmTimer = null;
    }

    $: statusSummary =
        `${$systemStatus} | ${formatBigNumber(totalSources)} SRC | WS ${$isConnected ? '✓' : '×'} | API ${apiOk ? '✓' : '×'}${
            apiOk && apiLatencyMs != null ? ` ${apiLatencyMs}ms` : ''
        } | HEALTH ${formatAgeSeconds(healthUpdatedAt, uiNow)}`;
    $: growthLatest = growthMetrics.length ? growthMetrics[0] : null;

    function scheduleSidebarAutoCollapse() {
        if (sidebarIdleTimer) clearTimeout(sidebarIdleTimer);
        sidebarIdleTimer = setTimeout(() => {
            if (isSidebarHovered || isSidebarScrolling) {
                scheduleSidebarAutoCollapse();
                return;
            }
            if (!sidebarCollapsed) collapseSidebar(true);
        }, SIDEBAR_IDLE_MS);
    }

    function registerSidebarActivity() {
        scheduleSidebarAutoCollapse();
    }

    function setSidebarHovering(nextValue: boolean) {
        isSidebarHovered = nextValue;
        if (nextValue) {
            if (sidebarIdleTimer) clearTimeout(sidebarIdleTimer);
            return;
        }
        registerSidebarActivity();
    }

    function handleSidebarScroll() {
        isSidebarScrolling = true;
        if (sidebarIdleTimer) clearTimeout(sidebarIdleTimer);
        if (sidebarScrollTimer) clearTimeout(sidebarScrollTimer);
        sidebarScrollTimer = setTimeout(() => {
            isSidebarScrolling = false;
            registerSidebarActivity();
        }, 800);
    }

    function expandSidebar() {
        sidebarCollapsed = false;
        if (expandedPanel == null) expandedPanel = lastExpandedPanel || 'gde';
        registerSidebarActivity();
    }

    function collapseSidebar(isAuto = false) {
        if (!sidebarCollapsed) lastExpandedPanel = expandedPanel;
        sidebarCollapsed = true;
        expandedPanel = null;
        if (!isAuto) registerSidebarActivity();
    }

    function togglePanel(view: 'health' | 'autoheal' | 'gde') {
        if (sidebarCollapsed) {
            expandSidebar();
            activeView = view;
            expandedPanel = view;
            return;
        }
        activeView = view;
        expandedPanel = expandedPanel === view ? null : view;
        registerSidebarActivity();
    }

    function emitMapCommand(type: string) {
        mapCommand.update((current: { nonce?: number; type?: string | null }) => ({
            nonce: (Number(current?.nonce) || 0) + 1,
            type,
        }));
    }

    function emitMapCommandWithActivity(type: string) {
        emitMapCommand(type);
        registerSidebarActivity();
    }

    function toggleSoundWithActivity() {
        toggleSound();
        registerSidebarActivity();
    }

    function toggleStatusPanel() {
        statusPanelExpanded = !statusPanelExpanded;
        registerSidebarActivity();
    }

    function openDiagnosticPanel() {
        expandSidebar();
        activeView = isOffline ? 'health' : isDegraded ? 'autoheal' : 'health';
        expandedPanel = activeView;
        registerSidebarActivity();
    }

    function getSystemSlotClass() {
        if ($systemStatus === 'OFFLINE') return 'border-red-400/70 text-red-200';
        if ($systemStatus === 'DEGRADED') return 'border-yellow-400/70 text-yellow-200';
        return 'sidebar-border sidebar-text';
    }

    function getSecondarySlotClass() {
        return isSystemCritical ? 'sidebar-border-soft sidebar-text-quiet' : 'sidebar-border sidebar-text';
    }

    function getSystemTitleClass() {
        if ($systemStatus === 'OFFLINE') return 'text-red-200';
        if ($systemStatus === 'DEGRADED') return 'text-yellow-200';
        return 'sidebar-text-muted';
    }

    /**
     * Health check with exponential backoff $\Delta t_n=\min(\Delta t_0 2^{n-1}, \Delta t_{max})$.
     * Parameters: $\Delta t_0=5000$ ms, $\Delta t_{max}=60000$ ms.
     */
    function setOfflineTelemetry() {
        serviceStatus.set({ postgres: 'unknown', redis: 'unknown' });
        backendThreadStatus.set({ crawler: 'unknown', analyzer: 'unknown', cleanup: 'unknown' });
    }

    async function checkSystemHealth() {
        if (isStaticMode()) {
            apiOk = false;
            apiLatencyMs = null;
            healthUpdatedAt = Date.now();
            systemStatus.set('STATIC');
            return;
        }
        const startedAt = Date.now();
        const controller = new AbortController();
        const abortTimer = setTimeout(() => controller.abort(), 4000);
        try {
            const apiBase = resolveApiBase();
            const response = await fetch(`${apiBase}/health/full`, { signal: controller.signal });
            apiOk = response.ok;
            apiLatencyMs = Math.max(0, Date.now() - startedAt);
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
            apiOk = false;
            apiLatencyMs = null;
            setOfflineTelemetry();
            systemStatus.set('OFFLINE');
            retryCount++;
        } finally {
            clearTimeout(abortTimer);
            healthUpdatedAt = Date.now();
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

    function toggleSound() {
        $soundEnabled = !$soundEnabled;
    }

    async function fetchHeaderStats() {
        if (isStaticMode()) return;
        try {
            const apiBase = resolveApiBase();
            const res = await fetch(`${apiBase}/api/map-data`, { cache: 'no-store' });
            if (res.ok) {
                const data = await res.json();
                if (data && data.total_sources != null) totalSources = Number(data.total_sources) || 0;
            }
        } catch (e) {
            console.error('Failed to fetch map stats:', e);
        }
    }

    async function fetchGdeMetrics() {
        if (isStaticMode()) return;
        try {
            const apiBase = resolveApiBase();
            const query = `window_hours=${encodeURIComponent(String(gdeWindowHours))}&alpha=${encodeURIComponent(String(gdeAlpha))}`;
            const res = await fetch(`${apiBase}/api/stats/gde/current?${query}`, { cache: 'no-store' });
            if (res.ok) {
                const data = await res.json();
                if (data && data.status !== 'error') {
                    gdeMetrics = {
                        gde: Number(data.gde) || 0,
                        shannon_entropy: Number(data.shannon_entropy) || 0,
                        normalized_shannon: Number(data.normalized_shannon) || 0,
                        geographic_dispersion_km: Number(data.geographic_dispersion_km) || 0,
                        normalized_dispersion: Number(data.normalized_dispersion) || 0,
                        country_count: Number(data.country_count) || 0,
                        total_visits: Number(data.total_visits) || 0,
                        window_hours: Number(data.window_hours) || 0,
                        gini_coefficient: Number(data.gini_coefficient) || 0,
                        alpha: Number(data.alpha) || 0,
                    };
                }
            }
        } catch (e) {
            console.error('Failed to fetch GDE metrics:', e);
        }
    }

    function setGdeWindow(hours: number) {
        gdeWindowHours = hours;
        fetchGdeMetrics();
    }

    function setGdeAlpha(alpha: number) {
        gdeAlpha = alpha;
        fetchGdeMetrics();
    }

    async function fetchGrowthMetrics() {
        if (isStaticMode()) return;
        try {
            const apiBase = resolveApiBase();
            const res = await fetch(`${apiBase}/api/stats/growth/recent?days=7`, { cache: 'no-store' });
            if (res.ok) {
                const data = await res.json();
                if (Array.isArray(data)) {
                    growthMetrics = data.map(item => ({
                        day: String(item.day || ''),
                        media_sources_net: Number(item.media_sources_net) || 0,
                        candidate_sources_growth_rate: Number(item.candidate_sources_growth_rate) || 0,
                        news_articles_net: Number(item.news_articles_net) || 0,
                        media_sources_count: Number(item.media_sources_count) || 0,
                        candidate_sources_count: Number(item.candidate_sources_count) || 0,
                        news_articles_count: Number(item.news_articles_count) || 0,
                    }));
                }
            }
        } catch (e) {
            console.error('Failed to fetch growth metrics:', e);
        }
    }

    function formatBigNumber(num: number) {
        if (num >= 1000000) {
            return (num / 1000000).toFixed(3) + 'M';
        }
        return num.toLocaleString();
    }

    function formatMetric(value: number | null | undefined, digits = 3) {
        if (value == null || Number.isNaN(value)) return '—';
        return value.toFixed(digits);
    }

    function formatPercent(value: number | null | undefined) {
        if (value == null || Number.isNaN(value)) return '—';
        return `${(value * 100).toFixed(2)}%`;
    }

    function formatAgeSeconds(fromEpochMs: number, nowEpochMs: number) {
        if (!fromEpochMs) return '—';
        const sec = Math.max(0, Math.floor((nowEpochMs - fromEpochMs) / 1000));
        if (sec < 60) return `${sec}s`;
        const min = Math.floor(sec / 60);
        if (min < 60) return `${min}m`;
        const hr = Math.floor(min / 60);
        return `${hr}h`;
    }

    function getSystemDotClass(status?: string) {
        if (status === 'ONLINE') return 'status-dot-ok';
        if (status === 'DEGRADED') return 'status-dot-warn';
        if (status === 'OFFLINE') return 'status-dot-error';
        return 'status-dot-neutral';
    }

    function scheduleSafetyAutoDisarm() {
        if (safetyAutoDisarmTimer) clearTimeout(safetyAutoDisarmTimer);
        safetyAutoDisarmTimer = setTimeout(() => {
            safetyArmed = false;
        }, 45000);
    }

    function toggleSafety() {
        if (isOffline) return;
        if (!safetyArmed) {
            if (isDegraded) {
                const ok = window.confirm('System is DEGRADED. Arm high-risk controls?');
                if (!ok) return;
            }
            safetyArmed = true;
            scheduleSafetyAutoDisarm();
            return;
        }
        safetyArmed = false;
    }

    async function runHighRisk(actionLabel: string, op: () => Promise<void>) {
        if (isOffline) return;
        if (!safetyArmed) return;
        if (isDegraded) {
            const ok = window.confirm(`DEGRADED risk. Confirm ${actionLabel}?`);
            if (!ok) return;
        }
        scheduleSafetyAutoDisarm();
        await op();
    }

    /**
     * Dispatch crawler control with bounded latency budget $T \leq 5\text{s}$ and explicit action $a \in \{\text{start, stop, restart}\}$.
     * Research motivation: stabilize data ingestion to preserve downstream inference validity.
     * @param {string} action
     */
    async function controlCrawler(action: string) {
        if (action === 'stop' || action === 'restart') {
            const ok = window.confirm(`Confirm crawler ${action.toUpperCase()}?`);
            if (!ok) return;
        }
        isCrawlerLoading = true;
        crawlerMessage = '';
        try {
            const apiBase = resolveApiBase();
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
        if (isStaticMode()) {
            crawlerMessage = 'Static mode: backend operations are disabled.';
            return;
        }
        try {
            const apiBase = resolveApiBase();
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
        if (isStaticMode()) {
            crawlerMessage = 'Static mode: autoheal is disabled.';
            return;
        }
        const ok = window.confirm('Confirm forcing autoheal now?');
        if (!ok) return;
        isCrawlerLoading = true;
        crawlerMessage = 'Initiating self-healing...';
        try {
            const apiBase = resolveApiBase();
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

    let isCrawlerLoading = false;
    let crawlerMessage = '';

    onMount(() => {
        if (isStaticMode()) {
            const sources = (DATA as unknown as { MEDIA_SOURCES?: unknown }).MEDIA_SOURCES;
            totalSources = Array.isArray(sources) ? sources.length : 0;
            systemStatus.set('STATIC');
        }
        checkSystemHealth();
        if (!isStaticMode()) webSocketService.connect();
        scheduleSidebarAutoCollapse();

        const initAudio = () => {
            soundManager.init();
            window.removeEventListener('click', initAudio);
            window.removeEventListener('keydown', initAudio);
        };
        window.addEventListener('click', initAudio);
        window.addEventListener('keydown', initAudio);

        const uiClock = setInterval(() => {
            uiNow = Date.now();
        }, 1000);

        const handleShortcuts = (e: KeyboardEvent) => {
            registerSidebarActivity();
            const target = e.target as HTMLElement | null;
            const tag = target?.tagName?.toLowerCase();
            if (tag === 'input' || tag === 'textarea' || tag === 'select' || target?.isContentEditable) return;
            if (!e.ctrlKey || !e.shiftKey) return;

            const key = e.key.toLowerCase();
            if (key === 'h') {
                activeView = 'health';
                expandedPanel = 'health';
                expandSidebar();
                e.preventDefault();
                return;
            }
            if (key === 'a') {
                activeView = 'autoheal';
                expandedPanel = 'autoheal';
                expandSidebar();
                e.preventDefault();
                return;
            }
            if (key === 'g') {
                activeView = 'gde';
                expandedPanel = 'gde';
                expandSidebar();
                e.preventDefault();
                return;
            }
            if (key === 'k') {
                if (expandedPanel !== 'autoheal') return;
                toggleSafety();
                e.preventDefault();
                return;
            }
            if (key === 'r') {
                emitMapCommand('reset_view');
                e.preventDefault();
                return;
            }
            if (key === 'p') {
                emitMapCommand('export_png_1200');
                e.preventDefault();
                return;
            }
            if (key === 's') {
                emitMapCommand('export_svg_1200');
                e.preventDefault();
                return;
            }
        };
        window.addEventListener('keydown', handleShortcuts);

        const handleActivity = () => registerSidebarActivity();
        window.addEventListener('pointerdown', handleActivity);
        window.addEventListener('pointermove', handleActivity);
        window.addEventListener('wheel', handleActivity, { passive: true });
        window.addEventListener('touchstart', handleActivity, { passive: true });
        window.addEventListener('focus', handleActivity);

        fetchHeaderStats();
        const statsInterval = setInterval(fetchHeaderStats, 60000);
        fetchGdeMetrics();
        fetchGrowthMetrics();
        const gdeInterval = setInterval(fetchGdeMetrics, 60000);
        const growthInterval = setInterval(fetchGrowthMetrics, 300000);

        return () => {
            clearTimeout(healthCheckTimer);
            clearInterval(statsInterval);
            clearInterval(gdeInterval);
            clearInterval(growthInterval);
            clearInterval(uiClock);
            window.removeEventListener('keydown', handleShortcuts);
            window.removeEventListener('pointerdown', handleActivity);
            window.removeEventListener('pointermove', handleActivity);
            window.removeEventListener('wheel', handleActivity);
            window.removeEventListener('touchstart', handleActivity);
            window.removeEventListener('focus', handleActivity);
            if (sidebarIdleTimer) clearTimeout(sidebarIdleTimer);
            if (sidebarScrollTimer) clearTimeout(sidebarScrollTimer);
            if (safetyAutoDisarmTimer) clearTimeout(safetyAutoDisarmTimer);
        };
    });

    onDestroy(() => {
        clearTimeout(healthCheckTimer);
    });

    function getStatusColor(status?: string) {
        const value = String(status || '').toLowerCase();
        if (!value || value === 'unknown') return 'status-text-neutral';
        if (value === 'ok' || value === 'running' || value === 'active') return 'status-text-ok';
        if (value === 'disabled' || value === 'idle') return 'status-text-neutral';
        if (value === 'restarting' || value === 'starting' || value === 'warning' || value === 'degraded' || value === 'waiting')
            return 'status-text-warn';
        if (value === 'stalled' || value === 'stopped' || value === 'error' || value === 'failed' || value === 'offline')
            return 'status-text-error';
        return 'status-text-error';
    }

    function getThreadStatusColor(status?: string) {
        return getStatusColor(status);
    }

    function getSystemIconClass(status?: string) {
        if (status === 'ONLINE') return 'sidebar-text-muted';
        if (status === 'DEGRADED') return 'text-yellow-400';
        if (status === 'OFFLINE') return 'text-red-500';
        return 'sidebar-text-dim';
    }
</script>

<main class="w-full h-screen bg-slate-950 text-slate-100 font-serif selection:bg-slate-600/40">
    {#if isLoading}
        <div class="fixed inset-0 z-[10000] bg-slate-950 flex items-center justify-center">
            <div class="text-xs font-mono tracking-widest text-slate-300">Initializing…</div>
        </div>
    {/if}

    <div class="h-full min-h-0 relative">
        <section class="absolute inset-0 bg-slate-950">
            <MapContainer />
        </section>

        <aside
            class="absolute inset-y-0 left-0 z-[200] min-h-0 sidebar-shell shadow-[inset_0_1px_0_rgba(255,255,255,0.06)] overflow-hidden"
            style="width: {sidebarCollapsed ? '56px' : '320px'};"
            on:mouseenter={() => setSidebarHovering(true)}
            on:mouseleave={() => setSidebarHovering(false)}
        >
            <div class="h-full min-h-0 flex flex-col">
                <div class="h-12 px-2 flex items-center sidebar-top">
                    <div class="flex items-center gap-2 min-w-0 flex-1">
                        {#if sidebarCollapsed}
                            <button
                                class="w-9 h-9 rounded flex items-center justify-center sidebar-hoverable sidebar-icon-muted"
                                on:click={expandSidebar}
                                title="Expand Sidebar"
                            >
                                <span class="material-icons-round text-[18px]">chevron_right</span>
                            </button>
                        {:else}
                            <button
                                class="w-9 h-9 rounded flex items-center justify-center sidebar-hoverable sidebar-icon-muted"
                                on:click={() => collapseSidebar(false)}
                                title="Collapse Sidebar"
                            >
                                <span class="material-icons-round text-[18px]">chevron_left</span>
                            </button>
                        {/if}
                        {#if !sidebarCollapsed}
                            <div class="min-w-0">
                                <div class="flex items-center gap-2 min-w-0">
                                    <span class="w-6 h-6 rounded sidebar-panel-sub border sidebar-border flex items-center justify-center sidebar-text shrink-0">
                                        <span class="material-icons-round text-[16px]">public</span>
                                    </span>
                                    <div class="text-xs font-semibold tracking-wide truncate">Globe Media Pulse</div>
                                </div>
                            </div>
                        {/if}
                    </div>
                </div>

                <nav class="flex-1 min-h-0 overflow-y-auto px-1 py-2 flex flex-col gap-1" on:scroll={handleSidebarScroll}>
                    {#if !sidebarCollapsed}
                        <button
                            type="button"
                            class="mx-1 mt-1 px-2 py-1 rounded sidebar-panel border sidebar-border text-[10px] font-mono font-semibold tracking-widest sidebar-text-muted flex items-center gap-1.5"
                            on:click={toggleStatusPanel}
                        >
                            <span class="material-icons-round text-[14px] {getSystemTitleClass()}">monitor_heart</span><span class={getSystemTitleClass()}>Status</span>
                            <span class="ml-auto material-icons-round text-[16px] sidebar-icon-dim">{statusPanelExpanded ? 'expand_less' : 'expand_more'}</span>
                        </button>
                    {/if}
                    {#if sidebarCollapsed}
                        <button
                            type="button"
                            class="rounded flex items-center gap-2 px-2 sidebar-panel border sidebar-border min-w-0 overflow-hidden h-10 justify-center"
                            title={statusSummary}
                            on:click={expandSidebar}
                        >
                            <span class="w-2 h-2 rounded-full {getSystemDotClass($systemStatus)}"></span>
                            <span class="material-icons-round text-[18px] {getSystemIconClass($systemStatus)}">monitor_heart</span>
                        </button>
                    {:else if statusPanelExpanded}
                        <div class="mx-1 mb-1 space-y-1">
                            {#if isSystemCritical}
                                <button
                                    type="button"
                                    class={`flex items-center gap-2 px-2 py-1 rounded border sidebar-panel-soft ${getSystemSlotClass()}`}
                                    on:click={openDiagnosticPanel}
                                >
                                    <span class="material-icons-round text-[14px] {getSystemIconClass($systemStatus)}">healing</span>
                                    <span class="text-[10px] font-mono tracking-widest flex-1">诊断直达</span>
                                    <span class="text-[10px] font-mono tracking-widest">{isOffline ? 'Health' : 'Autoheal'}</span>
                                </button>
                            {/if}
                            <div class={`flex items-center justify-between px-2 py-1 rounded border sidebar-panel-soft ${getSystemSlotClass()}`}>
                                <span class="text-[10px] font-mono tracking-widest">SYSTEM</span>
                                <span class="text-[10px] font-mono tracking-widest">{$systemStatus}</span>
                            </div>
                            <div class={`flex items-center justify-between px-2 py-1 rounded border sidebar-panel-soft ${getSecondarySlotClass()}`}>
                                <span class="text-[10px] font-mono tracking-widest">SRC</span>
                                <span class="text-[10px] font-mono tracking-widest">{formatBigNumber(totalSources)}</span>
                            </div>
                            <div class={`flex items-center justify-between px-2 py-1 rounded border sidebar-panel-soft ${getSecondarySlotClass()}`}>
                                <span class="text-[10px] font-mono tracking-widest">WS</span>
                                <span class="text-[10px] font-mono tracking-widest">{$isConnected ? '✓' : '×'}</span>
                            </div>
                            <div class={`flex items-center justify-between px-2 py-1 rounded border sidebar-panel-soft ${getSecondarySlotClass()}`}>
                                <span class="text-[10px] font-mono tracking-widest">API</span>
                                <span class="text-[10px] font-mono tracking-widest">{apiOk ? '✓' : '×'}{apiOk && apiLatencyMs != null ? ` ${apiLatencyMs}ms` : ''}</span>
                            </div>
                            <div class={`flex items-center justify-between px-2 py-1 rounded border sidebar-panel-soft ${getSecondarySlotClass()}`}>
                                <span class="text-[10px] font-mono tracking-widest">HEALTH</span>
                                <span class="text-[10px] font-mono tracking-widest">{formatAgeSeconds(healthUpdatedAt, uiNow)}</span>
                            </div>
                            <div class={`flex items-center justify-between px-2 py-1 rounded border sidebar-panel-soft ${getSecondarySlotClass()}`}>
                                <span class="text-[10px] font-mono tracking-widest">PROFILE</span>
                                <span class="text-[10px] font-mono tracking-widest">
                                    {$mediaProfileStats.total
                                        ? `${formatPercent($mediaProfileStats.rate)} ${$mediaProfileStats.hit}/${$mediaProfileStats.total}`
                                        : '—'}
                                </span>
                            </div>
                        </div>
                    {/if}

                    {#if !sidebarCollapsed}
                        <div class="h-px sidebar-divider mx-1 my-2"></div>
                    {/if}

                    <button
                        class="relative h-10 rounded flex items-center gap-2 px-2 sidebar-hoverable border sidebar-border {activeView === 'gde' ? 'sidebar-active' : 'bg-transparent'}"
                        class:justify-center={sidebarCollapsed}
                        on:click={() => togglePanel('gde')}
                        title="Geographic Diversity Entropy"
                    >
                        {#if activeView === 'gde'}
                            <span class="absolute left-0 top-1.5 bottom-1.5 w-[2px] rounded-full sidebar-indicator"></span>
                        {/if}
                        {#if sidebarCollapsed && activeView === 'gde'}
                            <span class="absolute bottom-1 left-1/2 -translate-x-1/2 w-1.5 h-1.5 rounded-full sidebar-indicator"></span>
                        {/if}
                        <span class="material-icons-round text-[18px] {activeView === 'gde' ? 'sidebar-text' : 'sidebar-text-muted'}">diversity_3</span>
                        {#if !sidebarCollapsed}
                            <span class="text-[11px] font-mono tracking-widest sidebar-text truncate">Geographic Diversity Entropy</span>
                            <span class="ml-auto text-[10px] font-mono sidebar-text-quiet flex items-center gap-1">
                                <span class="material-icons-round text-[16px] sidebar-icon-dim">{expandedPanel === 'gde' ? 'expand_less' : 'expand_more'}</span>
                            </span>
                        {/if}
                    </button>

                    {#if !sidebarCollapsed && expandedPanel === 'gde'}
                        <div class="mx-1 mb-1 rounded sidebar-panel-soft border sidebar-border overflow-hidden">
                            <div class="h-9 px-2 flex items-center gap-2 border-b sidebar-border">
                                <span class="material-icons-round text-[18px] sidebar-icon-muted">diversity_3</span>
                                <div class="text-xs font-semibold">Geographic Diversity Entropy</div>
                            </div>
                            <div class="p-3 text-[11px] sidebar-text-dim space-y-2">
                                <div class="sidebar-panel-sub border sidebar-border p-2 rounded space-y-2">
                                    <div class="flex items-center justify-between">
                                        <span class="font-mono sidebar-text-muted flex items-center gap-2">
                                            <span class="material-icons-round text-[16px] sidebar-icon-muted">schedule</span>
                                            <span>Window</span>
                                        </span>
                                        <span class="font-mono sidebar-text-quiet">{gdeWindowHours}h</span>
                                    </div>
                                    <div class="flex flex-wrap gap-1">
                                        {#each gdeWindowOptions as hours (hours)}
                                            <button
                                                type="button"
                                                class={`px-2 py-0.5 rounded border sidebar-border text-[10px] font-mono tracking-widest ${gdeWindowHours === hours ? 'sidebar-active sidebar-text' : 'sidebar-panel-sub sidebar-text-muted'}`}
                                                on:click={() => setGdeWindow(hours)}
                                            >
                                                {hours}h
                                            </button>
                                        {/each}
                                    </div>
                                </div>
                                <div class="sidebar-panel-sub border sidebar-border p-2 rounded space-y-2">
                                    <div class="flex items-center justify-between">
                                        <span class="font-mono sidebar-text-muted flex items-center gap-2">
                                            <span class="material-icons-round text-[16px] sidebar-icon-muted">tune</span>
                                            <span>Alpha</span>
                                        </span>
                                        <span class="font-mono sidebar-text-quiet">{gdeAlpha.toFixed(2)}</span>
                                    </div>
                                    <div class="flex flex-wrap gap-1">
                                        {#each gdeAlphaOptions as alpha (alpha)}
                                            <button
                                                type="button"
                                                class={`px-2 py-0.5 rounded border sidebar-border text-[10px] font-mono tracking-widest ${gdeAlpha === alpha ? 'sidebar-active sidebar-text' : 'sidebar-panel-sub sidebar-text-muted'}`}
                                                on:click={() => setGdeAlpha(alpha)}
                                            >
                                                α {alpha.toFixed(1)}
                                            </button>
                                        {/each}
                                    </div>
                                </div>
                                <div class="sidebar-panel-sub border sidebar-border p-2 rounded flex items-center justify-between">
                                    <span class="font-mono sidebar-text-muted flex items-center gap-2">
                                        <span class="material-icons-round text-[16px] sidebar-icon-muted">public</span>
                                        <span>GDE</span>
                                    </span>
                                    <span class="font-mono sidebar-text-quiet">{formatMetric(gdeMetrics?.gde)}</span>
                                </div>
                                <div class="sidebar-panel-sub border sidebar-border p-2 rounded flex items-center justify-between">
                                    <span class="font-mono sidebar-text-muted flex items-center gap-2">
                                        <span class="material-icons-round text-[16px] sidebar-icon-muted">tag</span>
                                        <span>Entropy (H_norm)</span>
                                    </span>
                                    <span class="font-mono sidebar-text-quiet">{formatMetric(gdeMetrics?.normalized_shannon)}</span>
                                </div>
                                <div class="sidebar-panel-sub border sidebar-border p-2 rounded flex items-center justify-between">
                                    <span class="font-mono sidebar-text-muted flex items-center gap-2">
                                        <span class="material-icons-round text-[16px] sidebar-icon-muted">scatter_plot</span>
                                        <span>Dispersion (D_norm)</span>
                                    </span>
                                    <span class="font-mono sidebar-text-quiet">{formatMetric(gdeMetrics?.normalized_dispersion)}</span>
                                </div>
                                <div class="sidebar-panel-sub border sidebar-border p-2 rounded flex items-center justify-between">
                                    <span class="font-mono sidebar-text-muted flex items-center gap-2">
                                        <span class="material-icons-round text-[16px] sidebar-icon-muted">grid_view</span>
                                        <span>Coverage</span>
                                    </span>
                                    <span class="font-mono sidebar-text-quiet">{gdeMetrics ? `${gdeMetrics.country_count}/${gdeMetrics.total_visits}` : '—'}</span>
                                </div>
                                <div class="sidebar-panel-sub border sidebar-border p-2 rounded space-y-2">
                                    <div class="flex items-center justify-between">
                                        <span class="font-mono sidebar-text-muted flex items-center gap-2">
                                            <span class="material-icons-round text-[16px] sidebar-icon-muted">trending_up</span>
                                            <span>Net Growth</span>
                                        </span>
                                        <span class="font-mono sidebar-text-quiet">{growthLatest?.day || '—'}</span>
                                    </div>
                                    <div class="grid grid-cols-2 gap-2 text-[10px] font-mono sidebar-text-quiet">
                                        <div class="flex items-center justify-between rounded sidebar-panel-sub border sidebar-border px-2 py-1">
                                            <span>Media</span>
                                            <span>{growthLatest ? `${growthLatest.media_sources_net}` : '—'}</span>
                                        </div>
                                        <div class="flex items-center justify-between rounded sidebar-panel-sub border sidebar-border px-2 py-1">
                                            <span>Candidate</span>
                                            <span>{growthLatest ? formatPercent(growthLatest.candidate_sources_growth_rate) : '—'}</span>
                                        </div>
                                    </div>
                                </div>
                            </div>
                        </div>
                    {/if}

                    {#if !sidebarCollapsed}
                        <div class="h-px sidebar-divider mx-1 my-2"></div>
                        <button
                            type="button"
                            class="mx-1 px-2 py-1 rounded sidebar-panel border sidebar-border text-[10px] font-mono font-semibold tracking-widest sidebar-text-muted flex items-center gap-1.5"
                            on:click={() => { toolsExpanded = !toolsExpanded; registerSidebarActivity(); }}
                        >
                            <span class="material-icons-round text-[14px] sidebar-icon-muted">handyman</span><span>Tools</span>
                            <span class="ml-auto flex items-center gap-1.5">
                                <span class="px-1.5 py-0.5 rounded sidebar-panel-sub border sidebar-border text-[9px] font-mono tracking-widest sidebar-text-quiet">System</span>
                                {#if isSystemCritical}
                                    <span class={`px-1.5 py-0.5 rounded border sidebar-panel-sub text-[10px] font-mono tracking-widest ${getSystemSlotClass()}`}>{$systemStatus}</span>
                                {/if}
                                <span class="material-icons-round text-[16px] sidebar-icon-dim">{toolsExpanded ? 'expand_less' : 'expand_more'}</span>
                            </span>
                        </button>
                    {:else}
                        <div class="h-px sidebar-divider my-1 mx-1"></div>
                    {/if}

                    <button
                        class="relative h-10 rounded flex items-center gap-2 px-2 sidebar-hoverable border sidebar-border {activeView === 'health' ? 'sidebar-active' : 'bg-transparent'}"
                        class:justify-center={sidebarCollapsed}
                        on:click={() => togglePanel('health')}
                        title="Health"
                    >
                        {#if activeView === 'health'}
                            <span class="absolute left-0 top-1.5 bottom-1.5 w-[2px] rounded-full sidebar-indicator"></span>
                        {/if}
                        {#if sidebarCollapsed && activeView === 'health'}
                            <span class="absolute bottom-1 left-1/2 -translate-x-1/2 w-1.5 h-1.5 rounded-full sidebar-indicator"></span>
                        {/if}
                        <span class="material-icons-round text-[18px] {activeView === 'health' ? 'sidebar-text' : 'sidebar-text-muted'}">health_and_safety</span>
                        {#if !sidebarCollapsed}
                            <span class="text-[11px] font-mono tracking-widest sidebar-text">Health</span>
                            <span class="ml-auto text-[10px] font-mono sidebar-text-quiet flex items-center gap-1">
                                <span class="material-icons-round text-[16px] sidebar-icon-dim">{expandedPanel === 'health' ? 'expand_less' : 'expand_more'}</span>
                            </span>
                        {/if}
                    </button>

                    {#if !sidebarCollapsed && expandedPanel === 'health'}
                        <div class="mx-1 mb-1 rounded sidebar-panel-soft border sidebar-border overflow-hidden">
                            <div class="h-9 px-2 flex items-center gap-2 border-b sidebar-border">
                                <span class="material-icons-round text-[18px] sidebar-icon-muted">health_and_safety</span>
                                <div class="text-xs font-semibold">Health</div>
                                <div class="ml-auto flex items-center gap-2">
                                    <button
                                        type="button"
                                        class="px-2 py-0.5 rounded sidebar-panel-sub border sidebar-border text-[10px] font-mono tracking-widest sidebar-text-muted"
                                        on:click={() => { healthDetailExpanded = !healthDetailExpanded; }}
                                    >
                                        {healthDetailExpanded ? 'Detail' : 'Summary'}
                                    </button>
                                </div>
                            </div>
                            <div class="p-3 space-y-2 text-[11px]">
                                <div class="grid grid-cols-2 gap-2">
                                    <div class="grid grid-cols-[1fr_auto] items-center sidebar-panel-sub border sidebar-border p-2 rounded">
                                        <span class="sidebar-text-dim font-mono flex items-center gap-1">
                                            <span class="material-icons-round text-[14px] sidebar-icon-dim">storage</span>
                                            <span>POSTGRES</span>
                                        </span>
                                        <span class="font-mono {getStatusColor($serviceStatus.postgres)}">{$serviceStatus.postgres?.toUpperCase() || 'UNK'}</span>
                                    </div>
                                    <div class="grid grid-cols-[1fr_auto] items-center sidebar-panel-sub border sidebar-border p-2 rounded">
                                        <span class="sidebar-text-dim font-mono flex items-center gap-1">
                                            <span class="material-icons-round text-[14px] sidebar-icon-dim">memory</span>
                                            <span>REDIS</span>
                                        </span>
                                        <span class="font-mono {getStatusColor($serviceStatus.redis)}">{$serviceStatus.redis?.toUpperCase() || 'UNK'}</span>
                                    </div>
                                </div>
                                {#if healthDetailExpanded}
                                    <div>
                                        <div class="text-[10px] font-mono sidebar-text-dim tracking-widest mb-2 flex items-center gap-2">
                                            <span class="material-icons-round text-[14px] sidebar-icon-dim">route</span>
                                            <span>Threads</span>
                                        </div>
                                        <div class="grid grid-cols-3 gap-2">
                                            <div class="sidebar-panel-sub border sidebar-border p-2 rounded">
                                                <div class="text-[10px] sidebar-text-muted flex items-center gap-1">
                                                    <span class="material-icons-round text-[14px] sidebar-icon-muted">travel_explore</span>
                                                    <span>Crawler</span>
                                                </div>
                                                <div class="font-mono {getThreadStatusColor($backendThreadStatus.crawler)}">{$backendThreadStatus.crawler?.toUpperCase() || 'UNK'}</div>
                                            </div>
                                            <div class="sidebar-panel-sub border sidebar-border p-2 rounded">
                                                <div class="text-[10px] sidebar-text-muted flex items-center gap-1">
                                                    <span class="material-icons-round text-[14px] sidebar-icon-muted">analytics</span>
                                                    <span>Analyzer</span>
                                                </div>
                                                <div class="font-mono {getThreadStatusColor($backendThreadStatus.analyzer)}">{$backendThreadStatus.analyzer?.toUpperCase() || 'UNK'}</div>
                                            </div>
                                            <div class="sidebar-panel-sub border sidebar-border p-2 rounded">
                                                <div class="text-[10px] sidebar-text-muted flex items-center gap-1">
                                                    <span class="material-icons-round text-[14px] sidebar-icon-muted">delete_sweep</span>
                                                    <span>Cleanup</span>
                                                </div>
                                                <div class="font-mono {getThreadStatusColor($backendThreadStatus.cleanup)}">{$backendThreadStatus.cleanup?.toUpperCase() || 'UNK'}</div>
                                            </div>
                                        </div>
                                    </div>
                                {/if}
                            </div>
                        </div>
                    {/if}

                    <button
                        class="relative h-10 rounded flex items-center gap-2 px-2 sidebar-hoverable border sidebar-border {activeView === 'autoheal' ? 'sidebar-active' : 'bg-transparent'}"
                        class:justify-center={sidebarCollapsed}
                        on:click={() => togglePanel('autoheal')}
                        title="Autoheal"
                    >
                        {#if activeView === 'autoheal'}
                            <span class="absolute left-0 top-1.5 bottom-1.5 w-[2px] rounded-full sidebar-indicator"></span>
                        {/if}
                        {#if sidebarCollapsed && activeView === 'autoheal'}
                            <span class="absolute bottom-1 left-1/2 -translate-x-1/2 w-1.5 h-1.5 rounded-full sidebar-indicator"></span>
                        {/if}
                        <span class="material-icons-round text-[18px] {activeView === 'autoheal' ? 'sidebar-text' : 'sidebar-text-muted'}">auto_fix_high</span>
                        {#if !sidebarCollapsed}
                            <span class="text-[11px] font-mono tracking-widest sidebar-text">Autoheal</span>
                            <span class="ml-auto text-[10px] font-mono sidebar-text-quiet flex items-center gap-1">
                                <span class="material-icons-round text-[16px] sidebar-icon-dim">{expandedPanel === 'autoheal' ? 'expand_less' : 'expand_more'}</span>
                            </span>
                        {/if}
                    </button>

                    {#if !sidebarCollapsed && expandedPanel === 'autoheal'}
                        <div class="mx-1 mb-1 space-y-3">
                            <div class="rounded sidebar-panel-soft border sidebar-border p-3">
                                <div class="flex items-center justify-between">
                                    <div class="text-[10px] font-mono font-semibold tracking-widest sidebar-text-muted flex items-center gap-2">
                                        <span class="material-icons-round text-[16px] sidebar-icon-muted">shield</span>
                                        <span>Safety</span>
                                    </div>
                                    <div class="flex items-center gap-2">
                                        <button
                                            type="button"
                                            class="px-2 py-0.5 rounded sidebar-panel-sub border sidebar-border text-[10px] font-mono tracking-widest sidebar-text-muted"
                                            on:click={() => { autohealDetailExpanded = !autohealDetailExpanded; }}
                                        >
                                            {autohealDetailExpanded ? 'Detail' : 'Summary'}
                                        </button>
                                        {#if isDegraded}
                                            <span class="px-2 py-0.5 rounded border border-yellow-500/40 bg-yellow-500/10 text-yellow-200 text-[10px] font-mono tracking-widest flex items-center gap-1">
                                                <span class="material-icons-round text-[14px] text-yellow-200">warning_amber</span>
                                                <span>DEGRADED</span>
                                            </span>
                                        {/if}
                                        <button
                                            class="px-2 py-1 rounded border text-[10px] font-mono tracking-widest disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-1 {safetyArmed ? 'border-red-500/40 bg-red-500/10 text-red-200' : 'sidebar-panel-sub sidebar-border sidebar-text'}"
                                            on:click={toggleSafety}
                                            disabled={isOffline}
                                            aria-pressed={safetyArmed}
                                            title={isOffline ? 'Offline: Controls locked' : safetyArmed ? 'Disarm high-risk controls' : 'Arm high-risk controls'}
                                        >
                                            <span class="material-icons-round text-[14px]">{safetyArmed ? 'lock_open' : 'lock'}</span>
                                            {safetyArmed ? 'ARMED' : 'SAFE'}
                                        </button>
                                    </div>
                                </div>
                                <div class="mt-2 text-[11px] sidebar-text-dim font-mono">
                                    {#if isOffline}
                                        OFFLINE LOCK
                                    {:else if safetyArmed}
                                        High-risk actions enabled.
                                    {:else}
                                        High-risk actions blocked.
                                    {/if}
                                </div>
                            </div>

                            {#if autohealDetailExpanded}
                                <div class="rounded sidebar-panel-soft border sidebar-border p-3">
                                    <div class="text-[10px] font-mono font-semibold tracking-widest sidebar-text-muted mb-2 flex items-center gap-2">
                                        <span class="material-icons-round text-[16px] sidebar-icon-muted">travel_explore</span>
                                        <span>Crawler</span>
                                    </div>
                                    <div class="grid grid-cols-3 gap-2 mb-2">
                                        <button
                                            class="px-2 py-2 rounded border border-emerald-500/30 hover:bg-emerald-500/10 text-emerald-200 text-[10px] font-mono disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-1"
                                            on:click={() => runHighRisk('crawler START', () => controlCrawler('start'))}
                                            disabled={isCrawlerLoading || isOffline || !safetyArmed || $backendThreadStatus.crawler === 'running'}
                                        >
                                            <span class="material-icons-round text-[16px]">play_arrow</span>
                                            <span>Start</span>
                                        </button>
                                        <button
                                            class="px-2 py-2 rounded border border-red-500/30 hover:bg-red-500/10 text-red-200 text-[10px] font-mono disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-1"
                                            on:click={() => runHighRisk('crawler STOP', () => controlCrawler('stop'))}
                                            disabled={isCrawlerLoading || isOffline || !safetyArmed || $backendThreadStatus.crawler !== 'running'}
                                        >
                                            <span class="material-icons-round text-[16px]">stop</span>
                                            <span>Stop</span>
                                        </button>
                                        <button
                                            class="px-2 py-2 rounded border border-amber-500/30 hover:bg-amber-500/10 text-amber-200 text-[10px] font-mono disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-1"
                                            on:click={() => runHighRisk('crawler RESTART', () => controlCrawler('restart'))}
                                            disabled={isCrawlerLoading || isOffline || !safetyArmed}
                                        >
                                            <span class="material-icons-round text-[16px]">restart_alt</span>
                                            <span>Restart</span>
                                        </button>
                                    </div>
                                    <div class="text-[10px] font-mono sidebar-text-dim sidebar-panel-sub border sidebar-border p-2 rounded min-h-[32px]">
                                        {#if isCrawlerLoading}
                                            Processing…
                                        {:else}
                                            {crawlerMessage || 'Ready.'}
                                        {/if}
                                    </div>
                                </div>

                                <div class="rounded sidebar-panel-soft border sidebar-border p-3">
                                    <div class="flex items-center justify-between">
                                        <div class="text-[10px] font-mono font-semibold tracking-widest sidebar-text-muted flex items-center gap-2">
                                            <span class="material-icons-round text-[16px] sidebar-icon-muted">auto_fix_high</span>
                                            <span>Autoheal</span>
                                        </div>
                                        <button
                                            class="px-2 py-1 rounded border border-amber-500/30 hover:bg-amber-500/10 text-amber-200 text-[10px] font-mono disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-1"
                                            on:click={() => runHighRisk('autoheal FORCE', triggerHeal)}
                                            disabled={isCrawlerLoading || isOffline || !safetyArmed}
                                        >
                                            <span class="material-icons-round text-[14px]">bolt</span>
                                            Force
                                        </button>
                                    </div>
                                    <div class="mt-2 text-[11px] sidebar-text-dim">
                                        Crawler: <span class="{getThreadStatusColor($backendThreadStatus.crawler)}">{$backendThreadStatus.crawler?.toUpperCase() || 'UNK'}</span>
                                    </div>
                                </div>
                            {:else}
                                <div class="rounded sidebar-panel-sub border sidebar-border p-2 flex items-center justify-between text-[10px] font-mono">
                                    <span class="sidebar-text-muted flex items-center gap-2">
                                        <span class="material-icons-round text-[14px] sidebar-icon-muted">travel_explore</span>
                                        <span>Crawler</span>
                                    </span>
                                    <span class="{getThreadStatusColor($backendThreadStatus.crawler)}">{$backendThreadStatus.crawler?.toUpperCase() || 'UNK'}</span>
                                </div>
                            {/if}
                        </div>
                    {/if}

                    {#if toolsExpanded}
                        <div class="h-px sidebar-divider mx-1 my-2"></div>
                        <button
                            class="h-10 rounded flex items-center gap-2 px-2 sidebar-hoverable border sidebar-border sidebar-text-muted {disabledClass}"
                            class:justify-center={sidebarCollapsed}
                            on:click={() => emitMapCommandWithActivity('export_png_1200')}
                            title="Export PNG (1200 DPI)"
                        >
                            <span class="material-icons-round text-[18px]">image</span>
                            {#if !sidebarCollapsed}
                                <span class="text-[11px] font-mono tracking-widest">Export PNG</span>
                                <span class="ml-auto text-[10px] font-mono sidebar-text-quiet">1200 DPI</span>
                            {/if}
                        </button>

                        <button
                            class="h-10 rounded flex items-center gap-2 px-2 sidebar-hoverable border sidebar-border sidebar-text-muted {disabledClass}"
                            class:justify-center={sidebarCollapsed}
                            on:click={() => emitMapCommandWithActivity('export_svg_1200')}
                            title="Export SVG"
                        >
                            <span class="material-icons-round text-[18px]">schema</span>
                            {#if !sidebarCollapsed}
                                <span class="text-[11px] font-mono tracking-widest">Export SVG</span>
                                <span class="ml-auto text-[10px] font-mono sidebar-text-quiet">Vector</span>
                            {/if}
                        </button>

                        <button
                            class="h-10 rounded flex items-center gap-2 px-2 sidebar-hoverable border sidebar-border sidebar-text-muted {disabledClass}"
                            class:justify-center={sidebarCollapsed}
                            on:click={() => emitMapCommandWithActivity('reset_view')}
                            title="Reset View"
                        >
                            <span class="material-icons-round text-[18px]">my_location</span>
                            {#if !sidebarCollapsed}
                                <span class="text-[11px] font-mono tracking-widest">Reset View</span>
                            {/if}
                        </button>

                        <button
                            class="h-10 rounded flex items-center gap-2 px-2 sidebar-hoverable border sidebar-border sidebar-text-muted"
                            class:justify-center={sidebarCollapsed}
                            on:click={toggleSoundWithActivity}
                            title={$soundEnabled ? 'Sound: On' : 'Sound: Off'}
                            aria-pressed={$soundEnabled}
                        >
                            <span class="material-icons-round text-[18px]">{$soundEnabled ? 'volume_up' : 'volume_off'}</span>
                            {#if !sidebarCollapsed}
                                <span class="text-[11px] font-mono tracking-widest">Sound</span>
                                <span class="ml-auto text-[10px] font-mono sidebar-text-quiet">{$soundEnabled ? 'On' : 'Off'}</span>
                            {/if}
                        </button>
                    {/if}
                </nav>
            </div>
        </aside>
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
