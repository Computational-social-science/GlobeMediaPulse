<script lang="ts">
    import { onMount, onDestroy, setContext } from 'svelte';
    import { get, type Writable } from 'svelte/store';
    import {
        statusStore,
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
        sidebarConfig,
        loadSidebarConfig,
        saveSidebarConfig,
        clearSidebarConfig,
        getDefaultSidebarConfig,
        moveSidebarItem,
        addSidebarGroup,
        setSidebarGroupCollapsed,
        tidySidebarConfig
    } from '@stores';
    import MapContainer from '@components/MapContainer.svelte';
    import Sidebar from '@components/Sidebar.svelte';
    import FloatingWindow from '@components/FloatingWindow.svelte';
    import { DATA } from '@lib/data.js';
    import { fetchRemoteSidebarConfig, saveRemoteSidebarConfig } from '@lib/sidebarSync';
    import {
        getStatusColor,
        getThreadStatusColor
    } from '@/utils/statusHelpers.js';

    type StatusHealth = {
        updatedAt: number;
        apiOk: boolean;
        apiLatencyMs: number | null;
        services: {
            postgres: string;
            redis: string;
        };
        threads: {
            crawler: string;
            analyzer: string;
            cleanup: string;
        };
    };
    type SidebarItemId = 'status' | 'gde' | 'autoheal';
    type SidebarGroup = { id: string; title: string; items: SidebarItemId[]; collapsed?: boolean };
    type SidebarConfig = { version: number; groups: SidebarGroup[] };
    type SidebarMovePayload = {
        itemId: SidebarItemId;
        fromGroupId: string;
        toGroupId: string;
        toIndex: number;
    };

    const statusStoreTyped = statusStore as Writable<{ health: StatusHealth }>;
    let staticMode = false;

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

    const HEALTH_REDIRECT_KEY = 'gmp_health_redirect_v1';
    let toastMessage: string | null = null;
    let toastTimer: ReturnType<typeof setTimeout> | null = null;

    function showToast(message: string, duration = 4000) {
        toastMessage = message;
        if (toastTimer) clearTimeout(toastTimer);
        toastTimer = setTimeout(() => {
            toastMessage = null;
        }, duration);
    }

    function handleLegacyHealthRedirect() {
        const path = window.location.pathname || '/';
        const rawSearch = window.location.search || '';
        const hash = window.location.hash || '';
        const rawParts = rawSearch.startsWith('?') ? rawSearch.slice(1).split('&').filter(Boolean) : [];
        const nextParts: string[] = [];
        let shouldToast = false;
        let needsReplace = false;
        for (const part of rawParts) {
            const [rawKey, ...rest] = part.split('=');
            const key = decodeURIComponent(rawKey || '');
            const value = decodeURIComponent(rest.join('=') || '');
            if (key === 'legacy' && value === 'health') {
                shouldToast = true;
                needsReplace = true;
                continue;
            }
            nextParts.push(part);
        }
        let nextPath = path;
        if (path === '/health' || path.startsWith('/health/')) {
            nextPath = path.replace(/^\/health/, '/status');
            sessionStorage.setItem(HEALTH_REDIRECT_KEY, '1');
            activeWindow = 'status';
            activeView = null;
            expandedPanel = null;
            shouldToast = true;
            needsReplace = true;
        }
        if (needsReplace) {
            const nextSearch = nextParts.length ? `?${nextParts.join('&')}` : '';
            const nextUrl = `${nextPath}${nextSearch}${hash}`;
            window.history.replaceState(null, '', nextUrl);
        }
        if (sessionStorage.getItem(HEALTH_REDIRECT_KEY)) {
            sessionStorage.removeItem(HEALTH_REDIRECT_KEY);
            shouldToast = true;
        }
        if (shouldToast) {
            showToast('Health已合并至Status');
        }
    }

    function updateHealthState(patch: Partial<StatusHealth>) {
        statusStoreTyped.update((current) => {
            const currentHealth = current.health;
            return {
                ...current,
                health: {
                    ...currentHealth,
                    ...patch,
                    services: patch.services ? { ...currentHealth.services, ...patch.services } : currentHealth.services,
                    threads: patch.threads ? { ...currentHealth.threads, ...patch.threads } : currentHealth.threads
                }
            };
        });
    }

    function getViteEnv(): {
        VITE_API_URL?: string;
        VITE_API_BASE_URL?: string;
        VITE_WS_URL?: string;
        VITE_STATIC_MODE?: string;
        VITE_SYNC_TOKEN?: string;
    } {
        return (
            (import.meta as {
                env?: {
                    VITE_API_URL?: string;
                    VITE_API_BASE_URL?: string;
                    VITE_WS_URL?: string;
                    VITE_STATIC_MODE?: string;
                    VITE_SYNC_TOKEN?: string;
                };
            }).env || {}
        );
    }

    function resolveSyncToken(): string {
        const env = getViteEnv();
        return String(env.VITE_SYNC_TOKEN || '').trim();
    }

    function isStaticMode(): boolean {
        const env = getViteEnv();
        const forced = String(env.VITE_STATIC_MODE || '').trim().toLowerCase();
        if (forced === '1' || forced === 'true' || forced === 'yes' || forced === 'on') return true;
        if (forced === '0' || forced === 'false' || forced === 'no' || forced === 'off') return false;
        if (env.VITE_API_URL || env.VITE_API_BASE_URL) return false;
        return true;
    }

    function resolveApiBase(): string {
        if (isStaticMode()) return '';
        const env = getViteEnv();
        return (
            env.VITE_API_URL ||
            env.VITE_API_BASE_URL ||
            (window.location.hostname === 'localhost' ? 'http://localhost:8000' : '')
        );
    }

    function resolveWsBase(apiBase: string): string {
        const env = getViteEnv();
        return env.VITE_WS_URL || apiBase.replace(/^http/, 'ws');
    }

    function stripAutohealFromConfig(config: SidebarConfig): SidebarConfig {
        const base = tidySidebarConfig(config);
        const groups = base.groups.map((group) => ({
            ...group,
            items: group.items.filter((item) => item !== 'autoheal')
        }));
        const normalizedGroups = groups.filter((group, index) => group.items.length > 0 || index === 0);
        return { ...base, groups: normalizedGroups };
    }

    let totalSources = 0;
    let healthCheckTimer: ReturnType<typeof setTimeout>;
    let retryCount = 0;
    let isLoading = true;
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

    let activeView: 'autoheal' | 'gde' | null = null;
    let expandedPanel: 'autoheal' | 'gde' | null = 'gde';
    let sidebarCollapsed = false;
    let lastExpandedPanel: 'autoheal' | 'gde' | null = 'gde';
    let activeWindow: 'status' | 'gde' | null = 'status';
    let statusAutohealTab: 'status' | 'autoheal' = 'status';
    let statusTabs: Array<{ key: 'status' | 'autoheal'; label: string }> = [
        { key: 'status', label: 'Status' },
        { key: 'autoheal', label: 'Autoheal' }
    ];
    let autohealDetailExpanded = false;
    let safetyArmed = false;
    let safetyAutoDisarmTimer: ReturnType<typeof setTimeout> | null = null;
    const SIDEBAR_IDLE_MS = 12000;
    let sidebarIdleTimer: ReturnType<typeof setTimeout> | null = null;
    let sidebarScrollTimer: ReturnType<typeof setTimeout> | null = null;
    let isSidebarHovered = false;
    let isSidebarScrolling = false;
    let sidebarConfigPersistTimer: ReturnType<typeof setTimeout> | null = null;
    let sidebarConfigRemotePersistTimer: ReturnType<typeof setTimeout> | null = null;
    let sidebarConfigRemoteAbort: AbortController | null = null;
    let sidebarConfigTyped = getDefaultSidebarConfig() as SidebarConfig;
    const SIDEBAR_LOCAL_UPDATED_KEY = 'sidebarConfigUpdatedAtMs';
    const SIDEBAR_REMOTE_UPDATED_KEY = 'sidebarConfigRemoteUpdatedAtMs';

    function scheduleRemoteSidebarConfigSave(config: unknown) {
        if (typeof window === 'undefined') return;
        if (sidebarConfigRemotePersistTimer) clearTimeout(sidebarConfigRemotePersistTimer);
        sidebarConfigRemotePersistTimer = setTimeout(async () => {
            const apiBase = resolveApiBase();
            if (!apiBase || isStaticMode()) return;
            if (sidebarConfigRemoteAbort) sidebarConfigRemoteAbort.abort();
            const abort = new AbortController();
            sidebarConfigRemoteAbort = abort;
            const token = resolveSyncToken();
            const saved = await saveRemoteSidebarConfig(apiBase, config, token || null, fetch, abort.signal);
            if (saved?.updatedAtMs != null) {
                try {
                    window.localStorage.setItem(SIDEBAR_REMOTE_UPDATED_KEY, String(saved.updatedAtMs));
                } catch {
                    void 0;
                }
            }
        }, 900);
    }

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

    $: apiOk = $statusStore.health.apiOk;
    $: apiLatencyMs = $statusStore.health.apiLatencyMs;
    $: healthUpdatedAt = $statusStore.health.updatedAt;
    $: statusTabs = staticMode
        ? [{ key: 'status', label: 'Status' }]
        : [
              { key: 'status', label: 'Status' },
              { key: 'autoheal', label: 'Autoheal' }
          ];
    $: if (staticMode && statusAutohealTab !== 'status') statusAutohealTab = 'status';

    $: growthLatest = growthMetrics.length ? growthMetrics[0] : null;
    $: sidebarConfigTyped = $sidebarConfig as SidebarConfig;
    $: if (typeof window !== 'undefined' && $sidebarConfig) {
        if (sidebarConfigPersistTimer) clearTimeout(sidebarConfigPersistTimer);
        sidebarConfigPersistTimer = setTimeout(() => {
            saveSidebarConfig(window.localStorage, $sidebarConfig);
            try {
                window.localStorage.setItem(SIDEBAR_LOCAL_UPDATED_KEY, String(Date.now()));
            } catch {
                void 0;
            }
        }, 300);
        scheduleRemoteSidebarConfigSave($sidebarConfig);
    }

    function handleMoveSidebarItem(payload: SidebarMovePayload) {
        sidebarConfig.update((current) => moveSidebarItem(current, payload));
    }

    function handleCreateSidebarGroup(payload: { itemId: SidebarItemId; fromGroupId: string; title?: string }) {
        sidebarConfig.update((current) => {
            const { config, groupId } = addSidebarGroup(current, payload.title || '');
            return moveSidebarItem(config, {
                itemId: payload.itemId,
                fromGroupId: payload.fromGroupId,
                toGroupId: groupId,
                toIndex: config.groups.find((group) => group.id === groupId)?.items.length ?? 0
            });
        });
    }

    function handleToggleSidebarGroup(groupId: string) {
        sidebarConfig.update((current) => {
            const currentGroup = current.groups.find((group) => group.id === groupId);
            const nextCollapsed = currentGroup ? !currentGroup.collapsed : false;
            return setSidebarGroupCollapsed(current, groupId, nextCollapsed);
        });
    }

    function handleResetSidebarConfig() {
        if (typeof window !== 'undefined') clearSidebarConfig(window.localStorage);
        const baseConfig = getDefaultSidebarConfig();
        const nextConfig = staticMode ? stripAutohealFromConfig(baseConfig) : baseConfig;
        sidebarConfig.set(nextConfig);
    }

    function handleTidySidebarConfig() {
        sidebarConfig.update((current) => {
            const next = tidySidebarConfig(current);
            return staticMode ? stripAutohealFromConfig(next) : next;
        });
    }

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
        if (activeWindow == null) expandedPanel = null;
        if (!isAuto) registerSidebarActivity();
    }

    function openViewWindow(view: 'autoheal' | 'gde') {
        if (staticMode && view === 'autoheal') return;
        if (sidebarCollapsed) expandSidebar();
        activeView = view;
        expandedPanel = view;
        if (view === 'autoheal') {
            activeWindow = 'status';
            statusAutohealTab = 'autoheal';
        } else {
            activeWindow = view;
        }
        registerSidebarActivity();
    }

    function openStatusWindow() {
        if (sidebarCollapsed) expandSidebar();
        activeWindow = 'status';
        activeView = null;
        statusAutohealTab = 'status';
        registerSidebarActivity();
    }

    function closeActiveWindow() {
        activeWindow = null;
        expandedPanel = null;
        activeView = null;
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

    /**
     * Health check with exponential backoff $\Delta t_n=\min(\Delta t_0 2^{n-1}, \Delta t_{max})$.
     * Parameters: $\Delta t_0=5000$ ms, $\Delta t_{max}=60000$ ms.
     */
    function setOfflineTelemetry() {
        updateHealthState({
            apiOk: false,
            apiLatencyMs: null,
            services: { postgres: 'unknown', redis: 'unknown' },
            threads: { crawler: 'unknown', analyzer: 'unknown', cleanup: 'unknown' }
        });
        backendThreadStatus.set({ crawler: 'unknown', analyzer: 'unknown', cleanup: 'unknown' });
    }

    async function checkSystemHealth() {
        if (isStaticMode()) {
            updateHealthState({
                apiOk: false,
                apiLatencyMs: null,
                updatedAt: Date.now(),
                services: { postgres: 'unknown', redis: 'unknown' },
                threads: { crawler: 'unknown', analyzer: 'unknown', cleanup: 'unknown' }
            });
            systemStatus.set('STATIC');
            return;
        }
        const startedAt = Date.now();
        const controller = new AbortController();
        const abortTimer = setTimeout(() => controller.abort(), 4000);
        try {
            const apiBase = resolveApiBase();
            const response = await fetch(`${apiBase}/health/full`, { signal: controller.signal });
            const nextApiOk = response.ok;
            const nextApiLatencyMs = Math.max(0, Date.now() - startedAt);
            if (response.ok) {
                const data = await response.json();
                if (data.services) {
                    updateHealthState({ services: data.services });
                }
                if (data.threads) {
                    updateHealthState({ threads: data.threads });
                    backendThreadStatus.set(data.threads);
                }

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
            updateHealthState({
                apiOk: nextApiOk,
                apiLatencyMs: nextApiLatencyMs
            });
        } catch (error) {
            console.warn('Health check failed:', error);
            setOfflineTelemetry();
            systemStatus.set('OFFLINE');
            retryCount++;
        } finally {
            clearTimeout(abortTimer);
            updateHealthState({ updatedAt: Date.now() });
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
                    updateHealthState({ threads: data.threads });
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
        staticMode = isStaticMode();
        if (typeof window !== 'undefined') {
            const storedSidebarConfig = loadSidebarConfig(window.localStorage);
            const initialConfig = storedSidebarConfig || getDefaultSidebarConfig();
            const nextConfig = staticMode ? stripAutohealFromConfig(initialConfig) : initialConfig;
            sidebarConfig.set(nextConfig);
            if (!staticMode) {
                const localUpdated = Number(window.localStorage.getItem(SIDEBAR_LOCAL_UPDATED_KEY) || '0') || 0;
                const remoteUpdated = Number(window.localStorage.getItem(SIDEBAR_REMOTE_UPDATED_KEY) || '0') || 0;
                const baseline = Math.max(localUpdated, remoteUpdated);
                const abort = new AbortController();
                sidebarConfigRemoteAbort = abort;
                fetchRemoteSidebarConfig(resolveApiBase(), fetch, abort.signal)
                    .then((remote) => {
                        if (!remote || !remote.config || remote.updatedAtMs == null) return;
                        if (remote.updatedAtMs <= baseline) return;
                        sidebarConfig.set(tidySidebarConfig(remote.config));
                        try {
                            window.localStorage.setItem(SIDEBAR_REMOTE_UPDATED_KEY, String(remote.updatedAtMs));
                        } catch {
                            void 0;
                        }
                    })
                    .catch(() => void 0);
            }
        }
        handleLegacyHealthRedirect();
        if (staticMode) {
            const sources = (DATA as unknown as { MEDIA_SOURCES?: unknown }).MEDIA_SOURCES;
            totalSources = Array.isArray(sources) ? sources.length : 0;
            systemStatus.set('STATIC');
            updateHealthState({
                apiOk: false,
                apiLatencyMs: null,
                updatedAt: Date.now()
            });
        }
        checkSystemHealth();
        if (!staticMode) webSocketService.connect();
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
                openStatusWindow();
                e.preventDefault();
                return;
            }
            if (key === 'a') {
                if (!staticMode) openViewWindow('autoheal');
                e.preventDefault();
                return;
            }
            if (key === 'g') {
                openViewWindow('gde');
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

        let statsInterval: ReturnType<typeof setInterval> | null = null;
        let gdeInterval: ReturnType<typeof setInterval> | null = null;
        let growthInterval: ReturnType<typeof setInterval> | null = null;
        if (!staticMode) {
            fetchHeaderStats();
            statsInterval = setInterval(fetchHeaderStats, 60000);
            fetchGdeMetrics();
            fetchGrowthMetrics();
            gdeInterval = setInterval(fetchGdeMetrics, 60000);
            growthInterval = setInterval(fetchGrowthMetrics, 300000);
        }

        return () => {
            clearTimeout(healthCheckTimer);
            if (statsInterval) clearInterval(statsInterval);
            if (gdeInterval) clearInterval(gdeInterval);
            if (growthInterval) clearInterval(growthInterval);
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
        if (sidebarConfigPersistTimer) clearTimeout(sidebarConfigPersistTimer);
        if (sidebarConfigRemotePersistTimer) clearTimeout(sidebarConfigRemotePersistTimer);
        if (sidebarConfigRemoteAbort) sidebarConfigRemoteAbort.abort();
    });
</script>

<main class="w-full h-screen bg-slate-950 text-slate-100 selection:bg-slate-600/40">
    {#if isLoading}
        <div class="fixed inset-0 z-[10000] bg-slate-950 flex items-center justify-center">
            <div class="text-xs font-mono tracking-widest text-slate-300">Initializing…</div>
        </div>
    {/if}

    {#if toastMessage}
        <div class="fixed right-6 bottom-6 z-[10001]">
            <div class="sidebar-panel-sub border sidebar-border px-3 py-2 rounded text-[11px] font-mono tracking-widest text-slate-200 shadow-lg">
                {toastMessage}
            </div>
        </div>
    {/if}

    <div class="h-full min-h-0 flex flex-col">
        <header class="h-12 shrink-0 flex items-center gap-3 px-3 border-b sidebar-border sidebar-theme sidebar-panel">
            <div class="flex items-center gap-2 min-w-0">
                <div class="h-8 w-8 rounded-[6px] border sidebar-border sidebar-panel-sub flex items-center justify-center">
                    <span class="material-icons-round text-[18px] sidebar-icon-muted">public</span>
                </div>
                <div class="min-w-0 leading-tight">
                    <div class="text-[11px] font-semibold tracking-widest sidebar-text">GMP</div>
                    <div class="text-[10px] sidebar-text-dim">World Map Console</div>
                </div>
            </div>

            <div class="flex-1 min-w-0 flex items-center justify-center gap-2">
                <div class="px-2 py-1 rounded sidebar-panel-sub border sidebar-border text-[10px] font-mono sidebar-text-muted flex items-center gap-2">
                    <span class="material-icons-round text-[14px] sidebar-icon-muted">public</span>
                    <span>SRC</span>
                    <span class="sidebar-text-quiet">{formatBigNumber(totalSources)}</span>
                </div>
                <div class="px-2 py-1 rounded sidebar-panel-sub border sidebar-border text-[10px] font-mono sidebar-text-muted flex items-center gap-2">
                    <span class="material-icons-round text-[14px] sidebar-icon-muted">monitor_heart</span>
                    <span>{$systemStatus}</span>
                </div>
                <div class="px-2 py-1 rounded sidebar-panel-sub border sidebar-border text-[10px] font-mono sidebar-text-muted flex items-center gap-2">
                    <span class="material-icons-round text-[14px] sidebar-icon-muted">bolt</span>
                    <span>{apiOk ? `OK${apiLatencyMs != null ? ` ${apiLatencyMs}ms` : ''}` : 'DOWN'}</span>
                </div>
                <div class="px-2 py-1 rounded sidebar-panel-sub border sidebar-border text-[10px] font-mono sidebar-text-muted flex items-center gap-2">
                    <span class="material-icons-round text-[14px] sidebar-icon-muted">wifi</span>
                    <span>{$isConnected ? 'CONNECTED' : 'DISCONNECTED'}</span>
                </div>
                <div class="px-2 py-1 rounded sidebar-panel-sub border sidebar-border text-[10px] font-mono sidebar-text-muted flex items-center gap-2">
                    <span class="material-icons-round text-[14px] sidebar-icon-muted">schedule</span>
                    <span>{formatAgeSeconds(healthUpdatedAt, uiNow)}</span>
                </div>
            </div>

            <div class="flex items-center gap-2">
                <button
                    class="h-8 px-2 rounded-[6px] border sidebar-border sidebar-panel-sub flex items-center gap-1 text-[10px] font-mono sidebar-text-muted sidebar-hoverable sidebar-focusable"
                    on:click={openStatusWindow}
                    title="Status & Autoheal"
                >
                    <span class="material-icons-round text-[14px]">monitor_heart</span>
                    <span>Status</span>
                </button>
                <button
                    class="h-8 px-2 rounded-[6px] border sidebar-border sidebar-panel-sub flex items-center gap-1 text-[10px] font-mono sidebar-text-muted sidebar-hoverable sidebar-focusable"
                    on:click={() => openViewWindow('autoheal')}
                    title="Autoheal"
                >
                    <span class="material-icons-round text-[14px]">shield</span>
                    <span>Autoheal</span>
                </button>
                <button
                    class="h-8 px-2 rounded-[6px] border sidebar-border sidebar-panel-sub flex items-center gap-1 text-[10px] font-mono sidebar-text-muted sidebar-hoverable sidebar-focusable"
                    on:click={() => openViewWindow('gde')}
                    title="GDE Metrics"
                >
                    <span class="material-icons-round text-[14px]">insights</span>
                    <span>GDE</span>
                </button>
                <button
                    class="h-8 px-2 rounded-[6px] border sidebar-border sidebar-panel-sub flex items-center gap-1 text-[10px] font-mono sidebar-text-muted sidebar-hoverable sidebar-focusable"
                    on:click={() => emitMapCommand('reset_view')}
                    title="Reset Map View"
                >
                    <span class="material-icons-round text-[14px]">my_location</span>
                    <span>Reset</span>
                </button>
            </div>
        </header>

        <div class="flex-1 min-h-0 relative">
            <section class="absolute inset-0 bg-slate-950">
                <MapContainer />
            </section>

            <Sidebar
                bind:sidebarCollapsed
                bind:expandedPanel
                bind:activeView
                statusPanelExpanded={activeWindow === 'status'}
                sidebarConfig={sidebarConfigTyped}
                {totalSources}
                {healthUpdatedAt}
                {uiNow}
                {apiOk}
                {apiLatencyMs}
                {isSystemCritical}
                {isOffline}
                onExpand={expandSidebar}
                onCollapse={() => collapseSidebar(false)}
                onTogglePanel={openViewWindow}
                onToggleStatusPanel={openStatusWindow}
                onHover={setSidebarHovering}
                onScroll={handleSidebarScroll}
                onActivity={registerSidebarActivity}
                onMoveSidebarItem={handleMoveSidebarItem}
                onCreateSidebarGroup={handleCreateSidebarGroup}
                onToggleSidebarGroup={handleToggleSidebarGroup}
                onResetSidebarConfig={handleResetSidebarConfig}
                onTidySidebarConfig={handleTidySidebarConfig}
            />

            {#if activeWindow === 'status'}
                <FloatingWindow
                    windowKey="status"
                    title={staticMode ? 'Status' : 'Status & Autoheal'}
                    subtitle="Health, safety & recovery"
                    icon="monitor_heart"
                    onClose={closeActiveWindow}
                    windowActions={[{ key: 'close', label: 'Close', onClick: closeActiveWindow }]}
                    tabs={statusTabs}
                    initialActiveTab={statusAutohealTab}
                    bind:activeTabKey={statusAutohealTab}
                    let:activeTab
                >
                    {#if activeTab === 'status'}
                    <div class="space-y-3">
                        <div class="grid grid-cols-2 gap-2">
                            <div class="sidebar-panel-sub border sidebar-border p-2 rounded flex items-center justify-between">
                                <span class="font-mono sidebar-text-muted flex items-center gap-2">
                                    <span class="material-icons-round text-[16px] sidebar-icon-muted">public</span>
                                    <span>SRC</span>
                                </span>
                                <span class="font-mono sidebar-text-quiet">{formatBigNumber(totalSources)}</span>
                            </div>
                            <div class="sidebar-panel-sub border sidebar-border p-2 rounded flex items-center justify-between">
                                <span class="font-mono sidebar-text-muted flex items-center gap-2">
                                    <span class="material-icons-round text-[16px] sidebar-icon-muted">wifi</span>
                                    <span>WS</span>
                                </span>
                                <span class="font-mono {$isConnected ? 'status-text-ok' : 'status-text-error'}">{$isConnected ? 'CONNECTED' : 'DISCONNECTED'}</span>
                            </div>
                            <div class="sidebar-panel-sub border sidebar-border p-2 rounded flex items-center justify-between">
                                <span class="font-mono sidebar-text-muted flex items-center gap-2">
                                    <span class="material-icons-round text-[16px] sidebar-icon-muted">monitor_heart</span>
                                    <span>System</span>
                                </span>
                                <span class="font-mono {getStatusColor($systemStatus)}">{$systemStatus}</span>
                            </div>
                            <div class="sidebar-panel-sub border sidebar-border p-2 rounded flex items-center justify-between">
                                <span class="font-mono sidebar-text-muted flex items-center gap-2">
                                    <span class="material-icons-round text-[16px] sidebar-icon-muted">bolt</span>
                                    <span>API</span>
                                </span>
                                <span class="font-mono {apiOk ? 'status-text-ok' : 'status-text-error'}">{apiOk ? `OK${apiLatencyMs != null ? ` ${apiLatencyMs}ms` : ''}` : 'DOWN'}</span>
                            </div>
                        </div>

                        <div class="sidebar-panel-sub border sidebar-border p-2 rounded flex items-center justify-between">
                            <span class="font-mono sidebar-text-muted flex items-center gap-2">
                                <span class="material-icons-round text-[16px] sidebar-icon-muted">schedule</span>
                                <span>Health Age</span>
                            </span>
                            <span class="font-mono sidebar-text-quiet">{formatAgeSeconds(healthUpdatedAt, uiNow)}</span>
                        </div>

                        <div class="sidebar-panel-sub border sidebar-border rounded overflow-hidden">
                            <div class="px-2 py-1 border-b sidebar-border text-[10px] font-mono tracking-widest sidebar-text-muted flex items-center gap-2">
                                <span class="material-icons-round text-[14px] sidebar-icon-muted">terminal</span>
                                <span>Logs</span>
                            </div>
                            <div class="p-2 max-h-[360px] overflow-auto text-[10px] font-mono sidebar-text-quiet space-y-1">
                                {#if !$systemLogs?.length}
                                    <div class="sidebar-text-muted">No logs yet.</div>
                                {:else}
                                    {#each $systemLogs.slice(0, 50) as entry, idx (idx)}
                                        <div class="whitespace-pre-wrap break-words">{typeof entry === 'string' ? entry : JSON.stringify(entry)}</div>
                                    {/each}
                                {/if}
                            </div>
                        </div>

                        <div class="sidebar-panel-sub border sidebar-border rounded overflow-hidden">
                            <div class="px-2 py-1 border-b sidebar-border text-[10px] font-mono tracking-widest sidebar-text-muted flex items-center gap-2">
                                <span class="material-icons-round text-[14px] sidebar-icon-muted">storage</span>
                                <span>Services</span>
                            </div>
                            <div class="p-2 grid grid-cols-2 gap-2">
                                <div class="grid grid-cols-[1fr_auto] items-center sidebar-panel-sub border sidebar-border p-2 rounded">
                                    <span class="sidebar-text-dim font-mono flex items-center gap-1">
                                        <span class="material-icons-round text-[14px] sidebar-icon-dim">storage</span>
                                        <span>POSTGRES</span>
                                    </span>
                                    <span class="font-mono {getStatusColor($statusStore.health.services.postgres)}">{$statusStore.health.services.postgres?.toUpperCase() || 'UNK'}</span>
                                </div>
                                <div class="grid grid-cols-[1fr_auto] items-center sidebar-panel-sub border sidebar-border p-2 rounded">
                                    <span class="sidebar-text-dim font-mono flex items-center gap-1">
                                        <span class="material-icons-round text-[14px] sidebar-icon-dim">memory</span>
                                        <span>REDIS</span>
                                    </span>
                                    <span class="font-mono {getStatusColor($statusStore.health.services.redis)}">{$statusStore.health.services.redis?.toUpperCase() || 'UNK'}</span>
                                </div>
                            </div>
                        </div>

                        <div class="sidebar-panel-sub border sidebar-border rounded overflow-hidden">
                            <div class="px-2 py-1 border-b sidebar-border text-[10px] font-mono tracking-widest sidebar-text-muted flex items-center gap-2">
                                <span class="material-icons-round text-[14px] sidebar-icon-muted">route</span>
                                <span>Threads</span>
                            </div>
                            <div class="p-2 grid grid-cols-3 gap-2">
                                <div class="sidebar-panel-sub border sidebar-border p-2 rounded">
                                    <div class="text-[10px] sidebar-text-muted flex items-center gap-1">
                                        <span class="material-icons-round text-[14px] sidebar-icon-muted">travel_explore</span>
                                        <span>Crawler</span>
                                    </div>
                                    <div class="font-mono {getThreadStatusColor($statusStore.health.threads.crawler)}">{$statusStore.health.threads.crawler?.toUpperCase() || 'UNK'}</div>
                                </div>
                                <div class="sidebar-panel-sub border sidebar-border p-2 rounded">
                                    <div class="text-[10px] sidebar-text-muted flex items-center gap-1">
                                        <span class="material-icons-round text-[14px] sidebar-icon-muted">analytics</span>
                                        <span>Analyzer</span>
                                    </div>
                                    <div class="font-mono {getThreadStatusColor($statusStore.health.threads.analyzer)}">{$statusStore.health.threads.analyzer?.toUpperCase() || 'UNK'}</div>
                                </div>
                                <div class="sidebar-panel-sub border sidebar-border p-2 rounded">
                                    <div class="text-[10px] sidebar-text-muted flex items-center gap-1">
                                        <span class="material-icons-round text-[14px] sidebar-icon-muted">delete_sweep</span>
                                        <span>Cleanup</span>
                                    </div>
                                    <div class="font-mono {getThreadStatusColor($statusStore.health.threads.cleanup)}">{$statusStore.health.threads.cleanup?.toUpperCase() || 'UNK'}</div>
                                </div>
                            </div>
                        </div>
                    </div>
                {:else if activeTab === 'autoheal'}
                    <div class="space-y-3">
                        <div class="rounded sidebar-panel-soft border sidebar-border p-3">
                            <div class="flex items-center justify-between">
                                <div class="text-[10px] font-mono font-semibold tracking-widest sidebar-text-muted flex items-center gap-2">
                                    <span class="material-icons-round text-[16px] sidebar-icon-muted">shield</span>
                                    <span>Safety</span>
                                </div>
                                <div class="flex items-center gap-2">
                                    <button
                                        type="button"
                                        class="px-2 py-0.5 rounded sidebar-panel-sub border sidebar-border text-[10px] font-mono tracking-widest sidebar-text-muted sidebar-focusable"
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
                                        class="px-2 py-1 rounded border text-[10px] font-mono tracking-widest disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-1 sidebar-focusable {safetyArmed ? 'border-red-500/40 bg-red-500/10 text-red-200' : 'sidebar-panel-sub sidebar-border sidebar-text'}"
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
                                        class="px-2 py-2 rounded border border-emerald-500/30 hover:bg-emerald-500/10 text-emerald-200 text-[10px] font-mono disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-1 sidebar-focusable"
                                        on:click={() => runHighRisk('crawler START', () => controlCrawler('start'))}
                                        disabled={isCrawlerLoading || isOffline || !safetyArmed || $backendThreadStatus.crawler === 'running'}
                                    >
                                        <span class="material-icons-round text-[16px]">play_arrow</span>
                                        <span>Start</span>
                                    </button>
                                    <button
                                        class="px-2 py-2 rounded border border-red-500/30 hover:bg-red-500/10 text-red-200 text-[10px] font-mono disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-1 sidebar-focusable"
                                        on:click={() => runHighRisk('crawler STOP', () => controlCrawler('stop'))}
                                        disabled={isCrawlerLoading || isOffline || !safetyArmed || $backendThreadStatus.crawler !== 'running'}
                                    >
                                        <span class="material-icons-round text-[16px]">stop</span>
                                        <span>Stop</span>
                                    </button>
                                    <button
                                        class="px-2 py-2 rounded border border-amber-500/30 hover:bg-amber-500/10 text-amber-200 text-[10px] font-mono disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-1 sidebar-focusable"
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
                                        class="px-2 py-1 rounded border border-amber-500/30 hover:bg-amber-500/10 text-amber-200 text-[10px] font-mono disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-1 sidebar-focusable"
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
            </FloatingWindow>
        {/if}

        {#if activeWindow === 'gde'}
            <FloatingWindow
                windowKey="gde"
                title="Geographic Diversity Entropy"
                subtitle="Metrics & tuning"
                icon="diversity_3"
                onClose={closeActiveWindow}
                windowActions={[{ key: 'close', label: 'Close', onClick: closeActiveWindow }]}
            >
                <div class="space-y-2">
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
                </FloatingWindow>
            {/if}
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
