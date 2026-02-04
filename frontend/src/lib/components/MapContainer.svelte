<script lang="ts">
    import { onMount, onDestroy, getContext } from 'svelte';
    import { get } from 'svelte/store';
    import { SvelteMap } from 'svelte/reactivity';
    import {
        mapMode,
        newsEvents,
        systemLogs,
        mapCommand,
        mapState,
        mapIdleTimeout,
        mediaProfileStats
    } from '@stores';
    import type { NewsEvent, SystemLog } from '@stores';
    import { DATA } from '@lib/data.js';
    import maplibregl from 'maplibre-gl';

    type SoundManager = {
        init: () => void;
        playDataChirp: () => void;
    };
    type GeoGeometry = { type: string; coordinates: unknown };
    type GeoFeature = {
        type: 'Feature';
        id?: string | number;
        properties?: Record<string, unknown>;
        geometry: GeoGeometry;
    };
    type CountryRecord = {
        code: string;
        name?: string;
        lat: number;
        lng: number;
        code_alpha2?: string;
        [key: string]: unknown;
    };
    type CountriesGeoJSON = {
        type: 'FeatureCollection';
        features: GeoFeature[];
    };
    type SpellAtlasMap = maplibregl.Map & { __spellatlasEventsBound?: boolean };

    const soundManager =
        getContext<SoundManager>('soundManager') || {
            init: () => {},
            playDataChirp: () => {}
        };

    let mapElement: HTMLDivElement | null = null;
    let map: SpellAtlasMap | null = null;
    let mapLoaded = false;
    let countriesGeojson: CountriesGeoJSON | null = null;
    let currentStyle = 'vector';

    
    const baseCountriesList: CountryRecord[] = Array.isArray((DATA as unknown as { COUNTRIES?: unknown }).COUNTRIES)
        ? ((DATA as unknown as { COUNTRIES: CountryRecord[] }).COUNTRIES ?? [])
        : [];

    function cloneCountryMap(source: Map<string, CountryRecord>) {
        const next: SvelteMap<string, CountryRecord> = new SvelteMap();
        for (const [k, v] of source) next.set(k, v);
        return next;
    }

    const baseCountriesByCode: SvelteMap<string, CountryRecord> = new SvelteMap();
    const baseCountriesByAlpha2: SvelteMap<string, CountryRecord> = new SvelteMap();
    for (const entry of baseCountriesList) {
        if (!entry || !entry.code) continue;
        const code = String(entry.code).toUpperCase();
        const normalizedEntry: CountryRecord = { ...entry, code };
        baseCountriesByCode.set(code, normalizedEntry);
        if (normalizedEntry.code_alpha2) {
            const alpha2 = String(normalizedEntry.code_alpha2).toUpperCase();
            if (alpha2.length === 2) baseCountriesByAlpha2.set(alpha2, normalizedEntry);
        }
    }

    let countriesByCode: SvelteMap<string, CountryRecord> = cloneCountryMap(baseCountriesByCode);
    let countriesByAlpha2: SvelteMap<string, CountryRecord> = cloneCountryMap(baseCountriesByAlpha2);
    let mediaSourcesByDomain: SvelteMap<string, Record<string, unknown>> = new SvelteMap();
    const SOURCES = {
        countries: 'countries'
    };

    const LAYERS = {
        countries: 'country-layer'
    };

    const LEGACY_SOURCE_IDS = ['heat-errors', 'event-points'] as const;
    const LEGACY_LAYER_IDS = ['heat-layer', 'point-layer', 'clusters', 'cluster-count'] as const;

    const STYLE_URLS: Record<string, string | maplibregl.StyleSpecification> = {
        osm: {
            version: 8,
            sources: {
                'osm': {
                    type: 'raster',
                    tiles: ['https://tile.openstreetmap.org/{z}/{x}/{y}.png'],
                    tileSize: 256,
                    attribution: '&copy; OpenStreetMap Contributors'
                }
            },
            layers: [
                {
                    id: 'background',
                    type: 'background',
                    paint: { 'background-color': '#f1f5f9' }
                },
                {
                    id: 'osm',
                    type: 'raster',
                    source: 'osm',
                    paint: { 
                        'raster-saturation': -1,
                        'raster-contrast': 0.1,
                        'raster-opacity': 0.6,
                        'raster-brightness-min': 0,
                        'raster-brightness-max': 0.8
                    } 
                }
            ]
        },
        vector: 'https://basemaps.cartocdn.com/gl/positron-gl-style/style.json'
    };

    const INITIAL_VIEW: { center: maplibregl.LngLatLike; zoom: number } = { center: [0, 20], zoom: 2 };

    let vectorStyleEnglishCache: maplibregl.StyleSpecification | null = null;
    let styleLoadNonce = 0;
    let idleResetTimer: number | null = null;
    let lastInteractionTs = Date.now();
    let lastMapCommandNonce = 0;

    async function getVectorEnglishStyle(): Promise<maplibregl.StyleSpecification> {
        if (vectorStyleEnglishCache) return vectorStyleEnglishCache;

        const response = await fetch(String(STYLE_URLS.vector));
        const style = (await response.json()) as maplibregl.StyleSpecification;
        const layers = Array.isArray(style.layers) ? style.layers : [];

        const englishTextField = [
            'coalesce',
            ['get', 'name:en'],
            ['get', 'name_en'],
            ['get', 'name:latin'],
            ['get', 'name'],
            ['get', 'ref']
        ] as unknown as maplibregl.ExpressionSpecification;

        const nextLayers = layers.map((layer) => {
            if (layer.type !== 'symbol') return layer;
            if (!layer.layout) return layer;
            if ((layer.layout as Record<string, unknown>)['text-field'] == null) return layer;

            return {
                ...layer,
                layout: {
                    ...(layer.layout as Record<string, unknown>),
                    'text-field': englishTextField
                }
            };
        });

        vectorStyleEnglishCache = { ...style, layers: nextLayers };
        return vectorStyleEnglishCache;
    }

    function updateViewStateFromMap(mapRef: maplibregl.Map) {
        const c = mapRef.getCenter();
        mapState.update((prev) => ({
            ...prev,
            center: [c.lng, c.lat],
            zoom: mapRef.getZoom()
        }));
    }

    function clearLegacyHeatAndPointArtifacts(mapRef: maplibregl.Map) {
        for (const layerId of LEGACY_LAYER_IDS) {
            if (mapRef.getLayer(layerId)) mapRef.removeLayer(layerId);
        }
        for (const sourceId of LEGACY_SOURCE_IDS) {
            if (mapRef.getSource(sourceId)) mapRef.removeSource(sourceId);
        }
    }

    function resetToInitialView(durationMs = 1200, clearArtifacts = false) {
        if (!map) return;
        const mapRef = map;
        if (clearArtifacts) {
            clearLegacyHeatAndPointArtifacts(mapRef);
            mapRef.triggerRepaint();
        }
        mapRef.easeTo({ center: INITIAL_VIEW.center, zoom: INITIAL_VIEW.zoom, duration: durationMs });
    }

    function scheduleIdleReset() {
        if (idleResetTimer != null) {
            window.clearTimeout(idleResetTimer);
            idleResetTimer = null;
        }

        if (!map || !mapLoaded) return;

        const timeoutMs = Number($mapIdleTimeout || 0);
        if (!Number.isFinite(timeoutMs) || timeoutMs <= 0) return;

        const elapsed = Date.now() - lastInteractionTs;
        const delay = Math.max(0, timeoutMs - elapsed);

        idleResetTimer = window.setTimeout(() => {
            const now = Date.now();
            if (now - lastInteractionTs >= timeoutMs) {
                if (!map) return;
                const c = map.getCenter();
                const z = map.getZoom();
                const initCenter = maplibregl.LngLat.convert(INITIAL_VIEW.center);
                const dist = Math.hypot(c.lng - initCenter.lng, c.lat - initCenter.lat);
                const zDiff = Math.abs(z - INITIAL_VIEW.zoom);
                if (dist < 1e-4 && zDiff < 1e-3) return;
                resetToInitialView();
            } else {
                scheduleIdleReset();
            }
        }, delay + 50);
    }

    function recordInteraction() {
        const now = Date.now();
        lastInteractionTs = now;
        mapState.update((prev) => ({ ...prev, lastInteraction: now }));
        scheduleIdleReset();
    }

    function downloadBlob(blob: Blob, filename: string) {
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = filename;
        document.body.appendChild(a);
        a.click();
        a.remove();
        URL.revokeObjectURL(url);
    }

    function waitForIdle(mapRef: maplibregl.Map, timeoutMs = 2500): Promise<void> {
        return new Promise((resolve) => {
            let done = false;
            const finish = () => {
                if (done) return;
                done = true;
                mapRef.off('idle', onIdle);
                resolve();
            };
            const onIdle = () => finish();
            mapRef.on('idle', onIdle);
            window.setTimeout(finish, timeoutMs);
        });
    }

    async function capturePngDataUrl(targetPixelRatio?: number): Promise<{ dataUrl: string; width: number; height: number }> {
        if (!map) throw new Error('Map not ready');
        const mapRef = map;
        const anyMap = mapRef as unknown as {
            setPixelRatio?: (ratio: number) => void;
            getPixelRatio?: () => number;
            _pixelRatio?: number;
        };

        const desired = Number(targetPixelRatio);
        const shouldTryPixelRatio = Number.isFinite(desired) && desired > 0 && typeof anyMap.setPixelRatio === 'function';
        const originalPixelRatio =
            typeof anyMap.getPixelRatio === 'function'
                ? anyMap.getPixelRatio()
                : Number.isFinite(anyMap._pixelRatio)
                    ? Number(anyMap._pixelRatio)
                    : Number(window.devicePixelRatio || 1);

        if (shouldTryPixelRatio) {
            try {
                anyMap.setPixelRatio?.(desired);
                mapRef.resize();
                await waitForIdle(mapRef);
                const canvas = mapRef.getCanvas();
                return { dataUrl: canvas.toDataURL('image/png'), width: canvas.width, height: canvas.height };
            } finally {
                anyMap.setPixelRatio?.(originalPixelRatio);
                mapRef.resize();
            }
        }

        const srcCanvas = mapRef.getCanvas();
        const scale = Number.isFinite(desired) && desired > 1 ? desired / Math.max(1, originalPixelRatio) : 1;
        if (scale <= 1) {
            return { dataUrl: srcCanvas.toDataURL('image/png'), width: srcCanvas.width, height: srcCanvas.height };
        }

        const dstCanvas = document.createElement('canvas');
        dstCanvas.width = Math.round(srcCanvas.width * scale);
        dstCanvas.height = Math.round(srcCanvas.height * scale);
        const ctx = dstCanvas.getContext('2d');
        if (!ctx) throw new Error('Canvas context not available');
        ctx.imageSmoothingEnabled = true;
        ctx.imageSmoothingQuality = 'high';
        ctx.drawImage(srcCanvas, 0, 0, dstCanvas.width, dstCanvas.height);
        return { dataUrl: dstCanvas.toDataURL('image/png'), width: dstCanvas.width, height: dstCanvas.height };
    }

    async function exportPng1200() {
        const stamp = new Date().toISOString().replace(/[:.]/g, '-');
        const { dataUrl } = await capturePngDataUrl(6);
        const blob = await (await fetch(dataUrl)).blob();
        downloadBlob(blob, `globe-media-pulse-map-${stamp}-1200dpi.png`);
    }

    async function exportSvg1200() {
        const stamp = new Date().toISOString().replace(/[:.]/g, '-');
        const { dataUrl, width, height } = await capturePngDataUrl(6);
        const svg = `<?xml version="1.0" encoding="UTF-8"?>\n<svg xmlns="http://www.w3.org/2000/svg" width="${width}" height="${height}" viewBox="0 0 ${width} ${height}">\n  <image href="${dataUrl}" width="${width}" height="${height}" preserveAspectRatio="none"/>\n</svg>\n`;
        const blob = new Blob([svg], { type: 'image/svg+xml;charset=utf-8' });
        downloadBlob(blob, `globe-media-pulse-map-${stamp}-1200dpi.svg`);
    }

    type LngLatMeta = {
        countryCode: string | null;
        source: 'coordinates' | 'latlng' | 'country_center';
        validationAttempted: boolean;
        inCountryInitial: boolean;
        inCountryFinal: boolean;
        usedFallback: boolean;
    };
    type LocalizationSignal = {
        level: 'high' | 'medium' | 'low';
        score: number;
        label: string;
        accent: string;
    };

    function normalizeDomain(value: unknown): string | null {
        if (value === null || value === undefined) return null;
        const raw = String(value).trim().toLowerCase();
        if (!raw) return null;
        let host = raw;
        if (raw.includes('://')) {
            try {
                host = new URL(raw).hostname || raw;
            } catch {
                host = raw;
            }
        } else if (raw.includes('/')) {
            host = raw.split('/')[0];
        }
        if (host.startsWith('www.')) {
            host = host.slice(4);
        }
        return host || null;
    }

    function computeLocalizationSignal(article: NewsEvent, meta: LngLatMeta | null): LocalizationSignal {
        const rawConfidence = String(
            (article as Record<string, unknown>).country_confidence ??
                (article as Record<string, unknown>).confidence ??
                ''
        ).toLowerCase();

        const confidenceScore =
            rawConfidence === 'high' ? 0.9 : rawConfidence === 'medium' ? 0.65 : rawConfidence === 'low' ? 0.35 : 0.5;

        let score = confidenceScore;
        if (meta?.source === 'country_center') score -= 0.2;
        if (meta?.usedFallback) score -= 0.25;
        score = Math.max(0, Math.min(1, score));

        const level: LocalizationSignal['level'] = score >= 0.75 ? 'high' : score >= 0.5 ? 'medium' : 'low';
        const accent = level === 'high' ? '#22c55e' : level === 'medium' ? '#f59e0b' : '#ef4444';
        const label = level === 'high' ? 'High' : level === 'medium' ? 'Medium' : 'Low';

        return { level, score, label, accent };
    }

    function createNewsCardElement(article: NewsEvent, meta: LngLatMeta | null = null) {
        const countryCode = article.country_code || article.country || 'UNK';
        const countryData = getCountryByCode(countryCode);
        const countryName = countryData?.name || countryCode;
        const flagCode = countryData?.code_alpha2 || (countryCode.length === 2 ? countryCode : null);
        const rawDomain =
            article.source_domain_norm ?? article.source_domain ?? (article as Record<string, unknown>)?.domain ?? 'Unknown Source';
        const domainKey = normalizeDomain(rawDomain);
        const mediaProfile = domainKey ? mediaSourcesByDomain.get(domainKey) : null;
        const domain = domainKey || String(rawDomain ?? 'Unknown Source');
        const mediaName =
            typeof mediaProfile?.name === 'string'
                ? mediaProfile.name
                : article.source_name || domain;
        const logo =
            typeof mediaProfile?.logo_url === 'string'
                ? mediaProfile.logo_url
                : article.logo_url;
        const tier = article.tier ? article.tier.replace('Tier-', 'T') : 'T2';
        const tierColor =
            tier === 'T0'
                ? 'text-rose-300 border-rose-300'
                : tier === 'T1'
                    ? 'text-sky-300 border-sky-300'
                    : 'text-emerald-300 border-emerald-300';
        const tierBg =
            tier === 'T0' ? 'bg-rose-400/10' : tier === 'T1' ? 'bg-sky-400/10' : 'bg-emerald-400/10';
        const signal = computeLocalizationSignal(article, meta);
        const language =
            typeof (mediaProfile as Record<string, unknown> | null)?.language === 'string'
                ? String((mediaProfile as Record<string, unknown>).language)
                : typeof (article as Record<string, unknown>).language === 'string'
                    ? String((article as Record<string, unknown>).language)
                    : null;
        const shortName =
            typeof (mediaProfile as Record<string, unknown> | null)?.short_name === 'string'
                ? String((mediaProfile as Record<string, unknown>).short_name)
                : typeof (mediaProfile as Record<string, unknown> | null)?.abbr === 'string'
                    ? String((mediaProfile as Record<string, unknown>).abbr)
                    : null;

        const root = document.createElement('div');
        root.className = `pointer-events-none select-none relative group news-card-marker news-card-marker--${signal.level}`;
        root.style.setProperty('--gmp-accent', signal.accent);

        const card = document.createElement('div');
        card.className =
            'relative min-w-[240px] max-w-[320px] bg-[#0a0f1c]/90 backdrop-blur-md border border-white/10 rounded-sm shadow-[0_0_18px_rgba(0,0,0,0.35)] overflow-hidden flex flex-col';
        root.appendChild(card);

        const accent = document.createElement('div');
        accent.className = 'absolute top-0 left-0 w-full h-[2px] news-card-accent';
        card.appendChild(accent);

        const header = document.createElement('div');
        header.className = 'flex items-center justify-between px-3 py-2 border-b border-white/5 bg-white/5';
        card.appendChild(header);

        const headerLeft = document.createElement('div');
        headerLeft.className = 'flex items-center gap-2';
        header.appendChild(headerLeft);

        if (flagCode && String(flagCode).length === 2) {
            const alpha2 = String(flagCode).toLowerCase();
            const flagEl = document.createElement('span');
            flagEl.className = `fi fi-${alpha2} gmp-flag opacity-80`;
            flagEl.setAttribute('aria-label', alpha2.toUpperCase());
            headerLeft.appendChild(flagEl);
        }

        const countrySpan = document.createElement('span');
        countrySpan.className = 'text-[10px] font-mono tracking-wider text-gray-300 uppercase truncate max-w-[100px]';
        countrySpan.textContent = countryName;
        headerLeft.appendChild(countrySpan);

        const headerRight = document.createElement('div');
        headerRight.className = 'flex items-center gap-1';
        header.appendChild(headerRight);

        const tierBadge = document.createElement('span');
        tierBadge.className = `text-[9px] font-bold px-1.5 py-0.5 rounded-[2px] border ${tierColor} ${tierBg}`;
        tierBadge.textContent = tier;
        headerRight.appendChild(tierBadge);

        const body = document.createElement('div');
        body.className = 'p-3 flex items-start gap-3';
        card.appendChild(body);

        const logoWrap = document.createElement('div');
        logoWrap.className = 'w-10 h-10 shrink-0 rounded bg-black/50 border border-white/10 flex items-center justify-center overflow-hidden';
        body.appendChild(logoWrap);

        if (logo) {
            const logoImg = document.createElement('img');
            logoImg.src = logo;
            logoImg.alt = 'Logo';
            logoImg.className = 'w-full h-full object-contain p-1';
            logoWrap.appendChild(logoImg);
        } else {
            const logoEmoji = document.createElement('span');
            logoEmoji.className = 'text-lg';
            logoEmoji.textContent = '📰';
            logoWrap.appendChild(logoEmoji);
        }

        const info = document.createElement('div');
        info.className = 'flex flex-col min-w-0';
        body.appendChild(info);

        const domainEl = document.createElement('h4');
        domainEl.className = 'text-xs font-bold text-white truncate leading-tight mb-0.5';
        domainEl.textContent = mediaName;
        info.appendChild(domainEl);

        const domainSub = document.createElement('div');
        domainSub.className = 'text-[9px] text-gray-500 uppercase tracking-wide truncate';
        domainSub.textContent = domain;
        info.appendChild(domainSub);

        const identityRow = document.createElement('div');
        identityRow.className = 'mt-2 flex items-center gap-2 flex-wrap';
        info.appendChild(identityRow);

        if (shortName) {
            const shortEl = document.createElement('span');
            shortEl.className =
                'text-[9px] font-bold tracking-wide px-1.5 py-0.5 rounded-[2px] border border-white/10 bg-white/5 text-gray-100';
            shortEl.textContent = shortName.toUpperCase();
            identityRow.appendChild(shortEl);
        }

        if (language) {
            const langEl = document.createElement('span');
            langEl.className = 'text-[9px] font-mono tracking-wide px-1.5 py-0.5 rounded-[2px] border border-white/10 bg-white/5 text-gray-300';
            langEl.textContent = language.toUpperCase();
            identityRow.appendChild(langEl);
        }

        const siteEl = document.createElement('a');
        siteEl.className =
            'text-[9px] font-mono text-sky-200/90 underline-offset-2 hover:underline hover:text-sky-100';
        siteEl.href = String(article.url || `https://${domain}`);
        siteEl.target = '_blank';
        siteEl.rel = 'noreferrer';
        siteEl.textContent = domain;
        identityRow.appendChild(siteEl);

        const footer = document.createElement('div');
        footer.className = 'absolute bottom-0 right-0 p-1 opacity-30 text-slate-400';
        footer.innerHTML =
            '<svg width="20" height="20" viewBox="0 0 20 20" fill="none" xmlns="http://www.w3.org/2000/svg"><path d="M19 19H10L19 10V19Z" fill="currentColor"/></svg>';
        card.appendChild(footer);

        return root;
    }

    let scanMarker: maplibregl.Marker | null = null;
    let serverMarker: maplibregl.Marker | null = null;
    let newsCardMarker: maplibregl.Marker | null = null;
    let newsCardRemoveTimer: ReturnType<typeof setTimeout> | null = null;
    const countryPolygonsByCode: SvelteMap<string, Array<Array<[number, number]>>> = new SvelteMap();

    /**
     * Applies a Tech/Commercial Game style override to the current map style.
     * PROFESSIONAL VERSION: Muted Slate/Grey palette, not too bright.
     */
    function applyTechStyle() {
        if (!map) return;
        const mapRef = map;
        const style = mapRef.getStyle();
        if (!style || !style.layers) return;

        // Professional Muted Palette
        const COLORS = {
            background: '#f1f5f9', // Slate 100 (Softer than white)
            water: '#cbd5e1',      // Slate 300 (Muted Blue-Grey)
            waterOutline: '#94a3b8', // Slate 400
            land: '#e2e8f0',       // Slate 200 (Soft Grey)
            boundary: '#64748b',   // Slate 500
            road: '#cbd5e1',       // Slate 300
            roadMajor: '#94a3b8',  // Slate 400
            text: '#334155',       // Slate 700
            textHalo: '#f1f5f9'    // Slate 100 Halo
        };

        style.layers.forEach(layer => {
            // Background
            if (layer.type === 'background') {
                mapRef.setPaintProperty(layer.id, 'background-color', COLORS.background);
                if (mapRef.getPaintProperty(layer.id, 'background-opacity') !== undefined) {
                     mapRef.setPaintProperty(layer.id, 'background-opacity', 1);
                }
            }
            
            // Water
            if (layer.id.includes('water')) {
                if (layer.type === 'fill') {
                    mapRef.setPaintProperty(layer.id, 'fill-color', COLORS.water);
                } else if (layer.type === 'line') {
                    mapRef.setPaintProperty(layer.id, 'line-color', COLORS.waterOutline);
                }
            }

            // Land
            if (layer.id.includes('land') || layer.id.includes('usage') || layer.id.includes('urban')) {
                 if (layer.type === 'fill') {
                    mapRef.setPaintProperty(layer.id, 'fill-color', COLORS.land);
                }
            }

            // Boundaries (Admin)
            if (layer.id.includes('admin') || layer.id.includes('boundary')) {
                if (layer.type === 'line') {
                    mapRef.setPaintProperty(layer.id, 'line-color', COLORS.boundary);
                    mapRef.setPaintProperty(layer.id, 'line-width', 0.8);
                    mapRef.setPaintProperty(layer.id, 'line-opacity', 0.6);
                }
            }

            // Roads
            if (layer.id.includes('road') || layer.id.includes('tunnel') || layer.id.includes('bridge')) {
                if (layer.type === 'line') {
                    mapRef.setPaintProperty(layer.id, 'line-color', COLORS.road);
                }
            }
            
            // Labels
            if (layer.type === 'symbol') {
                 if (layer.layout && layer.layout['text-field']) {
                    mapRef.setPaintProperty(layer.id, 'text-color', COLORS.text);
                    mapRef.setPaintProperty(layer.id, 'text-halo-color', COLORS.textHalo);
                    mapRef.setPaintProperty(layer.id, 'text-halo-width', 1);
                 }
            }
        });
    }

    // --- WebSocket & Real-time Visualization ---
    
    // Subscribe to global news events from store
    $: if ($newsEvents) {
        handleNewsEvent($newsEvents);
    }

    // Subscribe to system logs for Geoparsing visualization
    $: if ($systemLogs && $systemLogs.length > 0) {
        handleLogEvent($systemLogs[0]);
    }

    function getViteEnv(): { VITE_API_URL?: string; VITE_API_BASE_URL?: string; VITE_STATIC_MODE?: string } {
        return (
            (import.meta as { env?: { VITE_API_URL?: string; VITE_API_BASE_URL?: string; VITE_STATIC_MODE?: string } }).env || {}
        );
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
        return env.VITE_API_URL || env.VITE_API_BASE_URL || (window.location.hostname === 'localhost' ? 'http://localhost:8000' : '');
    }

    onMount(async () => {
        try {
            if (isStaticMode()) {
                applyCountriesPayload({ COUNTRIES: DATA.COUNTRIES });
                applyMediaSourcesPayload(DATA.MEDIA_SOURCES);
                return;
            }

            const apiBase = resolveApiBase();
            const countriesRes = await fetch(`${apiBase}/api/metadata/countries`);
            if (countriesRes.ok) {
                const payload = await countriesRes.json();
                applyCountriesPayload(payload);
            }

            const sourcesRes = await fetch(`${apiBase}/api/media/sources`);
            if (sourcesRes.ok) {
                const sourcesPayload = await sourcesRes.json();
                applyMediaSourcesPayload(sourcesPayload);
            }

        } catch (e) {
            console.error("Failed to fetch map stats:", e);
        }
    });

    let lastEventTime = 0;
    const EVENT_THROTTLE_MS = 200; // Limit to 5 events per second

    function getItemCountryCode(article: NewsEvent): string | null {
        const raw = article?.country_code || article?.country || article?.countryCode;
        if (!raw) return null;
        return String(raw).toUpperCase();
    }

    function handleNewsEvent(article: NewsEvent) {
        // Logic Linkage: Even if health check failed, if we receive WS events, we are effectively online.
        // if ($systemStatus === 'OFFLINE') return; // DISABLED for robustness

        // Handle System Logs / Geoparsing Events
        const type = (article as Record<string, unknown>).type;
        if (type === 'log') {
            handleLogEvent(article as SystemLog);
            return;
        }

        const rawDomain =
            article.source_domain_norm ?? article.source_domain ?? (article as Record<string, unknown>)?.domain ?? article.url;
        const domainKey = normalizeDomain(rawDomain);
        if (domainKey) {
            const hasProfile = mediaSourcesByDomain.has(domainKey);
            mediaProfileStats.update((current) => {
                const total = (current?.total ?? 0) + 1;
                const hit = (current?.hit ?? 0) + (hasProfile ? 1 : 0);
                const rate = total > 0 ? hit / total : 0;
                return { total, hit, rate };
            });
        }

        if (!mapLoaded || !map) return;
        
        // Throttle Logic
        const now = Date.now();
        if (now - lastEventTime < EVENT_THROTTLE_MS) {
            return;
        }
        lastEventTime = now;
        
        // Play Sound
        soundManager.playDataChirp();

        pulseServer();
        const resolved = resolveLngLatWithMeta(article);
        if (!resolved.position) return;
        updateVisualEffects(resolved.position, article, resolved.meta);

        if (newsCardRemoveTimer) {
            clearTimeout(newsCardRemoveTimer);
            newsCardRemoveTimer = null;
        }
        if (newsCardMarker) {
            newsCardMarker.remove();
            newsCardMarker = null;
        }
        const mapRef = map;
        if (!mapRef) return;
        const cardEl = createNewsCardElement(article, resolved.meta);
        newsCardMarker = new maplibregl.Marker({ element: cardEl, anchor: 'bottom', offset: [0, -12] })
            .setLngLat(resolved.position)
            .addTo(mapRef);
        newsCardRemoveTimer = setTimeout(() => {
            newsCardMarker?.remove();
            newsCardMarker = null;
            newsCardRemoveTimer = null;
        }, 8000);
    }

    function handleLogEvent(log: SystemLog) {
        if (!mapLoaded || !map) return;
        const mapRef = map;

        if (log.sub_type === 'geoparsing_complete') {
            const data = log.data;
            if (!data) return;
            const countryCode = data.result;
            if (!countryCode || countryCode === 'UNK') return;

            // Visualize "Resolution"
            const country = getCountryByCode(countryCode);
            if (country) {
                const coords: [number, number] = [country.lng, country.lat];
                
                // Create "RESOLVED" Label
                const labelEl = document.createElement('div');
                labelEl.className = 'scanning-label'; // Reuse style
                
                labelEl.innerHTML = `
                    <div class="flex items-center gap-2">
                        <div class="w-2 h-2 bg-green-500 rounded-full animate-pulse"></div>
                        <span class="text-[10px] font-mono font-bold text-green-400 bg-slate-900/90 px-2 py-1 rounded border border-green-500/30 shadow-sm flex flex-col">
                            <span>RESOLVED: ${country.name}</span>
                            <span class="text-[8px] text-gray-400 font-normal">${data.domain ?? ''}</span>
                            <span class="text-[8px] text-gray-500 font-normal">${data.method || 'consensus'}</span>
                        </span>
                    </div>
                `;
                
                const marker = new maplibregl.Marker({
                    element: labelEl,
                    anchor: 'bottom',
                    offset: [0, -10]
                })
                .setLngLat(coords)
                .addTo(mapRef);

                // Auto-remove
                setTimeout(() => marker.remove(), 3000);
                
                // Also trigger server pulse to show activity
                pulseServer();
            }
        }
    }


    function setupServerMarker() {
        if (!map) return;
        const mapRef = map;
        
        const el = document.createElement('div');
        el.className = 'server-marker';
        
        // Server Location: Los Angeles
        serverMarker = new maplibregl.Marker({ element: el })
            .setLngLat([-118.24, 34.05])
            .addTo(mapRef);
    }

    function pulseServer() {
        if (!serverMarker) return;
        const el = serverMarker.getElement();
        el.classList.add('pulse');
        setTimeout(() => {
            el.classList.remove('pulse');
        }, 500);
    }

    onMount(async () => {
        if (!mapElement) return;
        
        const initialMode = String(get(mapMode) || 'osm');
        const initialStyle =
            initialMode === 'vector' ? await getVectorEnglishStyle() : (STYLE_URLS[initialMode] || STYLE_URLS.osm);

        // OSM Desktop Experience: single world, no continuous copies
        const mapInstance = new maplibregl.Map({
            container: mapElement,
            style: initialStyle,
            center: INITIAL_VIEW.center,
            zoom: INITIAL_VIEW.zoom,
            minZoom: 1, // Allow seeing whole world
            maxZoom: 18, // Standard OSM max zoom
            renderWorldCopies: false,
            dragRotate: false,
            pitchWithRotate: false,
            attributionControl: { compact: true }
        });
        map = mapInstance;
        recordInteraction();
        mapInstance.on('movestart', recordInteraction);
        mapInstance.on('dragstart', recordInteraction);
        mapInstance.on('zoomstart', recordInteraction);
        mapInstance.on('rotatestart', recordInteraction);
        mapInstance.on('pitchstart', recordInteraction);
        mapInstance.on('touchstart', recordInteraction);
        mapInstance.on('mousedown', recordInteraction);
        mapInstance.on('click', recordInteraction);
        mapInstance.on('moveend', () => {
            updateViewStateFromMap(mapInstance);
        });

        const isDev = Boolean((import.meta as { env?: { DEV?: boolean } }).env?.DEV);
        const shouldExposeMap =
            isDev ||
            (typeof navigator !== 'undefined' &&
                Boolean((navigator as Navigator & { webdriver?: boolean }).webdriver)) ||
            window.location.hostname === 'localhost';
        if (shouldExposeMap) {
            type SpellAtlasWindow = Window & {
                map?: maplibregl.Map;
                __createNewsCardElement?: (article: NewsEvent) => HTMLElement;
                __emitNewsEvent?: (article: NewsEvent) => void;
            };
            const w = window as SpellAtlasWindow;
            w.map = mapInstance;
            w.__createNewsCardElement = (article) => createNewsCardElement(article);
            w.__emitNewsEvent = (article) => {
                lastEventTime = 0;
                handleNewsEvent(article);
            };
        }

        // Ensure strict window adaptation
        const resizeObserver = new ResizeObserver(() => {
            mapInstance.resize();
        });
        resizeObserver.observe(mapElement);

        mapInstance.on('load', () => {
            mapLoaded = true;
            try {
                updateViewStateFromMap(mapInstance);
                scheduleIdleReset();
                mapInstance.addControl(new maplibregl.ScaleControl({ maxWidth: 120, unit: 'metric' }), 'bottom-right');
                applyTechStyle(); // Apply Tech Style Override
                clearLegacyHeatAndPointArtifacts(mapInstance);
                setupLayers();
                setupServerMarker(); // Initialize Server Marker
                loadCountries();
            } catch (e) {
                console.error("Error during map load:", e);
            }
        });

        mapInstance.on('style.load', () => {
            if (mapLoaded) {
                try {
                    clearLegacyHeatAndPointArtifacts(mapInstance);
                    applyTechStyle(); // Apply Tech Style Override
                    setupLayers();
                    if (countriesGeojson) {
                        updateCountriesSource(countriesGeojson);
                    }
                } catch (e) {
                    console.error("Error restoring state after style load:", e);
                }
            }
        });
    });

    onDestroy(() => {
        if (idleResetTimer != null) window.clearTimeout(idleResetTimer);
        if (map) map.remove();
        if (scanMarker) scanMarker.remove();
        if (serverMarker) serverMarker.remove();
        if (newsCardMarker) newsCardMarker.remove();
        if (newsCardRemoveTimer) clearTimeout(newsCardRemoveTimer);
    });

    /**
     * Loads country GeoJSON boundaries for client-side geofencing.
     */
    async function loadCountries() {
        try {
            if (isStaticMode()) return;

            const apiBase = resolveApiBase();
            
            const response = await fetch(`${apiBase}/api/metadata/geojson`);
            const geoData = await response.json();
            const nextGeojson = {
                ...geoData,
                features: geoData.features.map((feature: GeoFeature) => ({
                    ...feature,
                    properties: { ...(feature.properties || {}), code: feature.id }
                }))
            } as CountriesGeoJSON;
            countriesGeojson = nextGeojson;
            buildCountryPolygons(nextGeojson);
            updateCountriesSource(nextGeojson);
        } catch (e) {
            console.error('Failed to load GeoJSON', e);
        }
    }

    /**
     * Configures Mapbox/MapLibre layers and sources.
     */
    function setupLayers() {
        if (!map) return;
        const mapRef = map;
        
        if (!mapRef.getLayer(LAYERS.countries) && mapRef.getSource(SOURCES.countries)) {
            mapRef.addLayer({
                id: LAYERS.countries,
                type: 'fill',
                source: SOURCES.countries,
                paint: {
                    'fill-color': '#e2e8f0', // Slate 200 (Matches Land)
                    'fill-outline-color': '#94a3b8', // Slate 400 (Subtle Border)
                    'fill-opacity': 0.5 // Subtle overlay
                }
            });
        }
    }

    /**
     * Updates the countries source with new GeoJSON data.
     * @param {any} geojson - The GeoJSON object.
     */
    function updateCountriesSource(geojson: CountriesGeoJSON) {
        if (!map) return;
        const mapRef = map;
        const geojsonData = geojson as unknown as maplibregl.GeoJSONSourceSpecification['data'];
        if (!mapRef.getSource(SOURCES.countries)) {
            mapRef.addSource(SOURCES.countries, { type: 'geojson', data: geojsonData });
        } else {
            const source = mapRef.getSource(SOURCES.countries) as maplibregl.GeoJSONSource | undefined;
            if (source) source.setData(geojsonData);
        }

        if (!mapRef.getLayer(LAYERS.countries) && mapRef.getSource(SOURCES.countries)) {
            mapRef.addLayer({
                id: LAYERS.countries,
                type: 'fill',
                source: SOURCES.countries,
                paint: {
                    'fill-color': '#e2e8f0',
                    'fill-outline-color': '#94a3b8',
                    'fill-opacity': 0.5
                }
            });
        }
    }

    /**
     * Pre-processes country polygons for fast client-side point-in-polygon checks.
     * @param {any} geojson - The countries GeoJSON.
     */
    function buildCountryPolygons(geojson: CountriesGeoJSON) {
        countryPolygonsByCode.clear();
        geojson.features.forEach((feature) => {
            const code = feature.id;
            const geometry = feature.geometry;
            if (!code || !geometry) return;
            if (geometry.type === 'Polygon' && Array.isArray(geometry.coordinates)) {
                const rings = geometry.coordinates
                    .filter((ring) => Array.isArray(ring))
                    .map((ring) =>
                        ring
                            .filter((coord) => Array.isArray(coord) && coord.length >= 2)
                            .map((coord) => [Number(coord[0]), Number(coord[1])] as [number, number])
                    )
                    .filter((ring) => ring.length > 2);
                if (rings.length > 0) {
                    countryPolygonsByCode.set(String(code), rings);
                }
            } else if (geometry.type === 'MultiPolygon' && Array.isArray(geometry.coordinates)) {
                const polygons = geometry.coordinates
                    .filter((poly) => Array.isArray(poly) && poly.length > 0)
                    .map((poly) => poly[0])
                    .filter((ring) => Array.isArray(ring))
                    .map((ring) =>
                        ring
                            .filter((coord) => Array.isArray(coord) && coord.length >= 2)
                            .map((coord) => [Number(coord[0]), Number(coord[1])] as [number, number])
                    )
                    .filter((ring) => ring.length > 2);
                if (polygons.length > 0) {
                    countryPolygonsByCode.set(String(code), polygons);
                }
            }
        });
    }

    /**
     * Determines if a point is inside a polygon using ray-casting algorithm.
     * @param {any} point - [lng, lat]
     * @param {any} polygon - Array of rings.
     */
    function isPointInPolygon(point: [number, number], polygon: Array<[number, number]>) {
        // ray-casting algorithm based on
        // https://github.com/substack/point-in-polygon
        const x = point[0], y = point[1];
        let inside = false;
        for (let i = 0, j = polygon.length - 1; i < polygon.length; j = i++) {
            const xi = polygon[i][0], yi = polygon[i][1];
            const xj = polygon[j][0], yj = polygon[j][1];
            
            const intersect = ((yi > y) !== (yj > y))
                && (x < (xj - xi) * (y - yi) / (yj - yi) + xi);
            if (intersect) inside = !inside;
        }
        return inside;
    }

    /**
     * Normalizes coordinate input into [lng, lat] format.
     * Handles objects {lat, lng}, {lon, lat}, arrays [lat, lng] or [lng, lat].
     * @param {any} value - The coordinate value to normalize.
     * @returns {[number, number] | null}
     */
    function toLngLat(value: unknown): [number, number] | null {
        if (!value) return null;
        if (Array.isArray(value) && value.length >= 2) {
            const a = Number(value[0]);
            const b = Number(value[1]);
            if (Number.isNaN(a) || Number.isNaN(b)) return null;
            if (Math.abs(a) <= 90 && Math.abs(b) > 90) return [b, a];
            if (Math.abs(a) > 90 && Math.abs(b) <= 90) return [a, b];
            if (Math.abs(a) <= 90 && Math.abs(b) <= 90) return [b, a];
            return [a, b];
        }
        if (typeof value === 'object') {
            const valueObj = value as Record<string, unknown>;
            const lng = valueObj.lng ?? valueObj.lon ?? valueObj.longitude;
            const lat = valueObj.lat ?? valueObj.latitude;
            if (lng !== undefined && lat !== undefined) {
                const lngNum = Number(lng);
                const latNum = Number(lat);
                if (Number.isNaN(lngNum) || Number.isNaN(latNum)) return null;
                return [lngNum, latNum];
            }
        }
        return null;
    }

    /** 
     * Retrieves the calibrated center coordinates for a country code.
     * @param {string} code - ISO 3166-1 alpha-3 code.
     * @returns {[number, number] | null}
     */
    function getCalibratedLngLat(code: string) {
        if (!code) return null;
        const calibrated = getCountryByCode(code);
        if (!calibrated) return null;
        return [Number(calibrated.lng), Number(calibrated.lat)] as [number, number];
    }

    function applyCountriesPayload(payload: unknown) {
        let list: CountryRecord[] = [];
        if (Array.isArray(payload)) {
            list = payload as CountryRecord[];
        } else if (payload && typeof payload === 'object') {
            const payloadObj = payload as Record<string, unknown>;
            if (Array.isArray(payloadObj.COUNTRIES)) {
                list = payloadObj.COUNTRIES as CountryRecord[];
            } else {
                list = Object.values(payloadObj) as CountryRecord[];
            }
        }
        const next: SvelteMap<string, CountryRecord> = cloneCountryMap(baseCountriesByCode);
        const nextAlpha2: SvelteMap<string, CountryRecord> = cloneCountryMap(baseCountriesByAlpha2);
        for (const entry of list) {
            if (!entry || !entry.code) continue;
            const code = String(entry.code).toUpperCase();
            const existing = next.get(code);
            const normalizedEntry: CountryRecord = { ...entry, code };
            if (!normalizedEntry.code_alpha2 && existing?.code_alpha2) {
                normalizedEntry.code_alpha2 = existing.code_alpha2;
            }
            next.set(code, normalizedEntry);
            if (normalizedEntry.code_alpha2) {
                const alpha2 = String(normalizedEntry.code_alpha2).toUpperCase();
                if (alpha2.length === 2) nextAlpha2.set(alpha2, normalizedEntry);
            }
        }
        countriesByCode = next;
        countriesByAlpha2 = nextAlpha2;
    }

    function applyMediaSourcesPayload(payload: unknown) {
        const next: SvelteMap<string, Record<string, unknown>> = new SvelteMap();
        if (Array.isArray(payload)) {
            payload.forEach((item) => {
                const itemObj = item as Record<string, unknown>;
                if (!itemObj?.domain) return;
                const domain = normalizeDomain(itemObj.domain);
                if (!domain) return;
                next.set(domain, itemObj);
            });
        }
        mediaSourcesByDomain = next;
    }

    function getCountryByCode(code: string): CountryRecord | null {
        if (!code) return null;
        const normalized = String(code).toUpperCase();
        if (normalized.length === 2) {
            return countriesByAlpha2.get(normalized) || null;
        }
        return countriesByCode.get(normalized) || null;
    }

    /**
     * Checks if a point lies within the boundaries of a specific country.
     * @param {any} point - [lng, lat]
     * @param {any} code - Country code.
     */
    function isPointInCountry(point: [number, number], code: string) {
        const polygons = countryPolygonsByCode.get(code);
        if (!polygons) return false;
        return polygons.some((polygon) => isPointInPolygon(point, polygon));
    }

    /**
     * Resolves the best available coordinates for an item.
     * Validates against country boundaries and falls back to country center.
     * @param {any} item - The data item.
     */
    function resolveLngLatWithMeta(item: NewsEvent): { position: [number, number] | null; meta: LngLatMeta | null } {
        const countryCode = getItemCountryCode(item);
        const fromCoordinates = toLngLat(item?.coordinates);
        const fromLatLng = fromCoordinates ? null : toLngLat({ lng: item?.lng, lat: item?.lat });
        const fromCenter = fromCoordinates || fromLatLng ? null : countryCode ? getCalibratedLngLat(countryCode) : null;

        const source: LngLatMeta['source'] = fromCoordinates
            ? 'coordinates'
            : fromLatLng
                ? 'latlng'
                : 'country_center';

        let position = fromCoordinates ?? fromLatLng ?? fromCenter;
        if (!position) return { position: null, meta: null };

        const canValidateCountry =
            Boolean(countryCode) &&
            countryPolygonsByCode.size > 0 &&
            (countryCode ? countryPolygonsByCode.has(countryCode) : false);

        const inCountryInitial = canValidateCountry && countryCode ? isPointInCountry(position, countryCode) : false;
        let usedFallback = false;
        if (canValidateCountry && countryCode && !inCountryInitial) {
            const fallback = getCalibratedLngLat(countryCode);
            if (fallback) {
                position = fallback;
                usedFallback = true;
            }
        }
        const inCountryFinal = canValidateCountry && countryCode ? isPointInCountry(position, countryCode) : false;

        if (!canValidateCountry && Math.abs(position[0]) < 1 && Math.abs(position[1]) < 1) {
            return { position: null, meta: null };
        }

        return {
            position,
            meta: {
                countryCode,
                source,
                validationAttempted: canValidateCountry,
                inCountryInitial,
                inCountryFinal,
                usedFallback
            }
        };
    }

    /**
     * Renders transient visual effects (scan marker, pulse, popup) on the map.
     * @param {any} position
     * @param {any} item
     * @param {any} isError
     */
    function updateVisualEffects(position: [number, number], item: NewsEvent, meta: LngLatMeta | null) {
        if (!map) return;
        const mapRef = map;
        const signal = computeLocalizationSignal(item, meta);
        if (!scanMarker) {
            const el = document.createElement('div');
            el.className = `scan-marker scan-marker--${signal.level}`;
            scanMarker = new maplibregl.Marker({ element: el })
                .setLngLat(position)
                .addTo(mapRef);
        } else {
            scanMarker.setLngLat(position);
            const el = scanMarker.getElement();
            el.classList.remove('scan-marker--high', 'scan-marker--medium', 'scan-marker--low');
            el.classList.add(`scan-marker--${signal.level}`);
        }
    }

    $: if (map && mapLoaded) {
        void $mapIdleTimeout;
        scheduleIdleReset();
    }

    $: if ($mapCommand && typeof $mapCommand.nonce === 'number' && $mapCommand.nonce !== lastMapCommandNonce) {
        lastMapCommandNonce = $mapCommand.nonce;
        const type = String($mapCommand.type || '');
        if (type === 'reset_view') {
            resetToInitialView(1200, true);
            recordInteraction();
        } else if (type === 'export_png_1200') {
            void exportPng1200().catch((e) => console.error('Export PNG failed', e));
        } else if (type === 'export_svg_1200') {
            void exportSvg1200().catch((e) => console.error('Export SVG failed', e));
        }
    }

    $: if (map && $mapMode && $mapMode !== currentStyle) {
        const nextMode = String($mapMode);
        currentStyle = nextMode;
        const nonce = (styleLoadNonce += 1);

        if (nextMode === 'vector') {
            void (async () => {
                try {
                    const nextStyle = await getVectorEnglishStyle();
                    if (!map || styleLoadNonce !== nonce) return;
                    map.setStyle(nextStyle);
                    if (mapElement) mapElement.style.filter = 'none';
                } catch (e) {
                    console.error('Failed to set vector style', e);
                }
            })();
        } else {
            const nextStyle = STYLE_URLS[nextMode];
            if (nextStyle && map) {
                map.setStyle(nextStyle);
                if (mapElement) mapElement.style.filter = 'none';
            }
        }
    }

</script>

<div class="w-full h-full" bind:this={mapElement}></div>



<style>
    :global(.maplibregl-popup-content) {
        background: rgba(15, 23, 42, 0.92);
        backdrop-filter: blur(10px);
        border: 1px solid rgba(148, 163, 184, 0.35);
        color: #e2e8f0;
        border-radius: 8px;
        box-shadow: 0 0 20px rgba(0, 0, 0, 0.4);
    }
    :global(.maplibregl-popup-tip) {
        border-top-color: rgba(10, 10, 31, 0.9);
    }

    :global(.scan-marker) {
        width: 12px;
        height: 12px;
        background: #22c55e;
        border: 2px solid rgba(255, 255, 255, 0.95);
        border-radius: 50%;
        box-shadow: 0 0 6px rgba(34, 197, 94, 0.45);
        transition: background 180ms ease-out, box-shadow 180ms ease-out, transform 180ms ease-out;
        position: relative;
        z-index: 80;
    }

    :global(.scan-marker.scan-marker--high) {
        background: #22c55e;
        box-shadow: 0 0 6px rgba(34, 197, 94, 0.45);
        transform: scale(1);
    }
    :global(.scan-marker.scan-marker--medium) {
        background: #f59e0b;
        box-shadow: 0 0 6px rgba(245, 158, 11, 0.42);
        transform: scale(1.05);
    }
    :global(.scan-marker.scan-marker--low) {
        background: #ef4444;
        box-shadow: 0 0 6px rgba(239, 68, 68, 0.45);
        transform: scale(1.1);
    }

    :global(.news-card-accent) {
        background: linear-gradient(90deg, var(--gmp-accent, #60a5fa) 0%, rgba(0, 0, 0, 0) 100%);
        opacity: 0.95;
    }

    :global(.server-marker) {
        width: 20px;
        height: 20px;
        background: radial-gradient(circle, rgba(96, 165, 250, 0.9) 38%, rgba(96, 165, 250, 0.15) 74%);
        border: 2px solid rgba(96, 165, 250, 0.9);
        border-radius: 50%;
        box-shadow: 0 0 0 2px rgba(15, 23, 42, 0.75);
        z-index: 50;
    }
    
    :global(.server-marker.pulse) {
        animation: server-pulse 0.5s ease-out;
    }

    @keyframes server-pulse {
        0% { transform: scale(1); box-shadow: 0 0 0 2px rgba(15, 23, 42, 0.75); }
        50% { transform: scale(1.25); box-shadow: 0 0 0 8px rgba(96, 165, 250, 0.22); }
        100% { transform: scale(1); box-shadow: 0 0 0 2px rgba(15, 23, 42, 0.75); }
    }

</style>
