<script lang="ts">
    import { onMount, onDestroy, getContext } from 'svelte';
    import { SvelteMap } from 'svelte/reactivity';
    import { mapMode, heatmapEnabled, newsEvents, systemLogs } from '../stores.js';
    import { DATA } from '../data.js';
    import maplibregl from 'maplibre-gl';

    type SoundManager = {
        init: () => void;
        playDataChirp: () => void;
    };
    type NewsItem = {
        [key: string]: unknown;
        country_code?: string;
        country?: string;
        countryCode?: string;
        country_name?: string;
        headline?: string;
        title?: string;
        has_error?: boolean;
        error_details?: { word?: string; suggestion?: string } | null;
        errors?: Array<{ word?: string; suggestion?: string }>;
        timestamp?: number;
        id?: string | number;
        coordinates?: unknown;
        lng?: number;
        lat?: number;
        source_domain?: string;
        source_name?: string;
        logo_url?: string;
        tier?: string;
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
    type PointFeature = {
        type: 'Feature';
        geometry: { type: 'Point'; coordinates: [number, number] };
        properties: Record<string, unknown>;
    };
    type SpellAtlasMap = maplibregl.Map & { __spellatlasEventsBound?: boolean };
    type HeatDatum = { code?: string; count?: number };
    type SystemLog = {
        sub_type?: string;
        data?: { result?: string; domain?: string; method?: string };
    };

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
    
    let updateBuffer: Array<{ item: NewsItem; showEffects: boolean }> = [];
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
    // Allow visualization if Live, Simulating (Playing), or if we are just receiving data stream
    const isVisualizing = true;

    const SOURCES = {
        heat: 'heat-errors',
        points: 'event-points',
        countries: 'countries'
    };

    const LAYERS = {
        heat: 'heat-layer',
        points: 'point-layer',
        countries: 'country-layer'
    };

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

    function computeLocalizationSignal(article: NewsItem, meta: LngLatMeta | null): LocalizationSignal {
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

    function createNewsCardElement(article: NewsItem, meta: LngLatMeta | null = null) {
        const countryCode = article.country_code || article.country || 'UNK';
        const countryData = getCountryByCode(countryCode);
        const countryName = countryData?.name || countryCode;
        const flagCode = countryData?.code_alpha2 || (countryCode.length === 2 ? countryCode : null);
        const domain = String(article.source_domain ?? 'Unknown Source');
        const domainKey = domain ? domain.toLowerCase() : null;
        const mediaProfile = domainKey ? mediaSourcesByDomain.get(domainKey) : null;
        const mediaName =
            typeof mediaProfile?.name === 'string'
                ? mediaProfile.name
                : article.source_name || domain;
        const logo =
            typeof mediaProfile?.logo_url === 'string'
                ? mediaProfile.logo_url
                : article.logo_url;
        const tier = article.tier ? article.tier.replace('Tier-', 'T') : 'T2';
        const tierColor = tier === 'T0' ? 'text-neon-pink border-neon-pink'
            : tier === 'T1' ? 'text-neon-blue border-neon-blue'
                : 'text-emerald-400 border-emerald-400';
        const tierBg = tier === 'T0' ? 'bg-neon-pink/10'
            : tier === 'T1' ? 'bg-neon-blue/10'
                : 'bg-emerald-400/10';
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
        siteEl.className = 'text-[9px] font-mono text-neon-blue/80 underline-offset-2 hover:underline';
        siteEl.href = String(article.url || `https://${domain}`);
        siteEl.target = '_blank';
        siteEl.rel = 'noreferrer';
        siteEl.textContent = domain;
        identityRow.appendChild(siteEl);

        const footer = document.createElement('div');
        footer.className = 'absolute bottom-0 right-0 p-1 opacity-30';
        footer.innerHTML = '<svg width="20" height="20" viewBox="0 0 20 20" fill="none"><path d="M19 19H10L19 10V19Z" fill="#00F3FF"/></svg>';
        card.appendChild(footer);

        return root;
    }

    let baseHeatCounts: SvelteMap<string, number> = new SvelteMap();
    let liveHeatCounts: SvelteMap<string, { count: number; lastUpdated: number }> = new SvelteMap();
    let heatFeatures: PointFeature[] = [];
    let pointFeatures: PointFeature[] = [];
    let scanMarker: maplibregl.Marker | null = null;
    let scanLabelMarker: maplibregl.Marker | null = null;
    let scanLabelMarkerTimeout: ReturnType<typeof setTimeout> | null = null;
    let serverMarker: maplibregl.Marker | null = null;
    const countryPolygonsByCode: SvelteMap<string, Array<Array<[number, number]>>> = new SvelteMap();

    // Reactive Map Controls
    $: if (map && mapLoaded) {
        try {
            // Toggle Heatmap
            if (map.getLayer(LAYERS.heat)) {
                map.setLayoutProperty(LAYERS.heat, 'visibility', $heatmapEnabled ? 'visible' : 'none');
            }
        } catch (e) {
            console.error("Error in reactive map controls:", e);
        }
    }

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
            boundary: '#64748b',   // Slate 500 (Visible but not neon)
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

    onMount(async () => {
        try {
            const apiBase =
                (import.meta as { env?: { VITE_API_URL?: string } }).env?.VITE_API_URL ||
                'http://localhost:8002';
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
            
            // Persistent Heatmap Data
            const heatRes = await fetch(`${apiBase}/api/stats/heatmap`);
            if (heatRes.ok) {
                const heatData = (await heatRes.json()) as HeatDatum[];
                baseHeatCounts = new SvelteMap();
                heatData.forEach((item) => {
                    if (!item?.code) return;
                    const count = Number(item.count || 0);
                    if (!Number.isFinite(count) || count <= 0) return;
                    baseHeatCounts.set(String(item.code).toUpperCase(), count);
                });
                refreshHeatSource();
            }

        } catch (e) {
            console.error("Failed to fetch map stats:", e);
        }
    });

    let lastEventTime = 0;
    const EVENT_THROTTLE_MS = 200; // Limit to 5 events per second
    const HEAT_HALF_LIFE_MS = 20 * 60 * 1000;

    function getItemCountryCode(article: NewsItem): string | null {
        const raw = article?.country_code || article?.country || article?.countryCode;
        if (!raw) return null;
        return String(raw).toUpperCase();
    }

    function getSmartAnchor(
        point: { x: number; y: number },
        width: number,
        height: number
    ): { anchor: maplibregl.PositionAnchor; offset: [number, number] } {
        const padding = 140;
        const nearLeft = point.x < padding;
        const nearRight = point.x > width - padding;
        const nearTop = point.y < padding;
        const nearBottom = point.y > height - padding;
        if (nearRight && nearBottom) return { anchor: 'bottom-right', offset: [-12, -12] };
        if (nearRight && nearTop) return { anchor: 'top-right', offset: [-12, 12] };
        if (nearLeft && nearBottom) return { anchor: 'bottom-left', offset: [12, -12] };
        if (nearLeft && nearTop) return { anchor: 'top-left', offset: [12, 12] };
        if (point.x > width / 2) return { anchor: point.y > height / 2 ? 'bottom-right' : 'top-right', offset: [-12, point.y > height / 2 ? -12 : 12] };
        return { anchor: point.y > height / 2 ? 'bottom-left' : 'top-left', offset: [12, point.y > height / 2 ? -12 : 12] };
    }

    function handleNewsEvent(article: NewsItem) {
        // Logic Linkage: Even if health check failed, if we receive WS events, we are effectively online.
        // if ($systemStatus === 'OFFLINE') return; // DISABLED for robustness

        // Handle System Logs / Geoparsing Events
        const type = (article as Record<string, unknown>).type;
        if (type === 'log') {
            handleLogEvent(article as SystemLog);
            return;
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
        addItem(article);
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

    onMount(() => {
        if (!mapElement) return;
        
        // OSM Desktop Experience: Flexible bounds, standard OSM look
        const mapInstance = new maplibregl.Map({
            container: mapElement,
            style: STYLE_URLS.vector,
            center: INITIAL_VIEW.center,
            zoom: INITIAL_VIEW.zoom,
            minZoom: 1, // Allow seeing whole world
            maxZoom: 18, // Standard OSM max zoom
            renderWorldCopies: true, // Infinite horizontal scroll
            attributionControl: { compact: true }
        });
        map = mapInstance;

        const isDev = Boolean((import.meta as { env?: { DEV?: boolean } }).env?.DEV);
        const shouldExposeMap =
            isDev ||
            (typeof navigator !== 'undefined' &&
                Boolean((navigator as Navigator & { webdriver?: boolean }).webdriver)) ||
            window.location.hostname === 'localhost';
        if (shouldExposeMap) {
            type SpellAtlasWindow = Window & {
                map?: maplibregl.Map;
                __createNewsCardElement?: (article: NewsItem) => HTMLElement;
                __emitNewsEvent?: (article: NewsItem) => void;
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
                applyTechStyle(); // Apply Tech Style Override
                setupLayers();
                setupServerMarker(); // Initialize Server Marker
                loadCountries();
                requestAnimationFrame(processBatch);
            } catch (e) {
                console.error("Error during map load:", e);
            }
        });

        mapInstance.on('style.load', () => {
            if (mapLoaded) {
                try {
                    applyTechStyle(); // Apply Tech Style Override
                    setupLayers();
                    if (countriesGeojson) {
                        updateCountriesSource(countriesGeojson);
                    }
                    // Restore Heatmap Visibility
                    if (mapInstance.getLayer(LAYERS.heat)) {
                        mapInstance.setLayoutProperty(LAYERS.heat, 'visibility', $heatmapEnabled ? 'visible' : 'none');
                    }
                    refreshHeatSource();
                } catch (e) {
                    console.error("Error restoring state after style load:", e);
                }
            }
        });
    });

    onDestroy(() => {
        if (map) map.remove();
        if (scanMarker) scanMarker.remove();
        if (scanLabelMarker) scanLabelMarker.remove();
        if (scanLabelMarkerTimeout) clearTimeout(scanLabelMarkerTimeout);
        if (serverMarker) serverMarker.remove();
    });

    /**
     * Loads country GeoJSON boundaries for client-side geofencing.
     */
    async function loadCountries() {
        try {
            const apiBase =
                (import.meta as { env?: { VITE_API_URL?: string; VITE_API_BASE_URL?: string } }).env?.VITE_API_URL ||
                (import.meta as { env?: { VITE_API_URL?: string; VITE_API_BASE_URL?: string } }).env?.VITE_API_BASE_URL ||
                (window.location.hostname === 'localhost'
                    ? 'http://localhost:8002'
                    : 'https://globe-media-pulse.fly.dev');
            
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

        ensureSource(SOURCES.heat, heatFeatures);
        ensureSource(SOURCES.points, pointFeatures);
        
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

        if (!mapRef.getLayer(LAYERS.heat)) {
            mapRef.addLayer({
                id: LAYERS.heat,
                type: 'heatmap',
                source: SOURCES.heat,
                paint: {
                    'heatmap-weight': ['coalesce', ['get', 'intensity'], 1],
                    'heatmap-intensity': [
                        'interpolate',
                        ['linear'],
                        ['zoom'],
                        1, 0.55,
                        4, 0.8,
                        7, 1.05,
                        10, 1.25
                    ],
                    'heatmap-radius': [
                        'interpolate',
                        ['linear'],
                        ['zoom'],
                        1, 10,
                        4, 18,
                        7, 30,
                        10, 42
                    ],
                    'heatmap-opacity': [
                        'interpolate',
                        ['linear'],
                        ['zoom'],
                        1, 0.55,
                        4, 0.65,
                        7, 0.72,
                        10, 0.78
                    ],
                    'heatmap-color': [
                        'interpolate',
                        ['linear'],
                        ['heatmap-density'],
                        0, 'rgba(0,0,0,0)',
                        0.2, 'rgba(68, 1, 84, 0.35)',
                        0.4, 'rgba(59, 82, 139, 0.55)',
                        0.6, 'rgba(33, 145, 140, 0.65)',
                        0.8, 'rgba(94, 201, 98, 0.75)',
                        1.0, 'rgba(253, 231, 37, 0.9)'
                    ]
                }
            });
        }

        if (!mapRef.getLayer(LAYERS.points)) {
            // 1. Unclustered Points (Individual Events)
            mapRef.addLayer({
                id: LAYERS.points,
                type: 'circle',
                source: SOURCES.points,
                filter: ['!', ['has', 'point_count']],
                paint: {
                    'circle-radius': 0, // Hidden as per user request (only Heatmap + Active Scan Marker visible)
                    'circle-opacity': 0,
                    'circle-stroke-width': 0
                }
            });
            
            // 2. Clusters (Aggregated Events)
            mapRef.addLayer({
                id: 'clusters',
                type: 'circle',
                source: SOURCES.points,
                filter: ['has', 'point_count'],
                paint: {
                    'circle-color': [
                        'step',
                        ['get', 'point_count'],
                        '#00F3FF', // Cyan for low count
                        10,
                        '#00FF00', // Green for medium
                        50,
                        '#FFFF00', // Yellow
                        100,
                        '#FF0000'  // Red for high
                    ],
                    'circle-radius': [
                        'step',
                        ['get', 'point_count'],
                        15, // Radius 15px
                        10,
                        20, // Radius 20px
                        50,
                        25,
                        100,
                        30
                    ],
                    'circle-opacity': 0.8,
                    'circle-stroke-width': 1,
                    'circle-stroke-color': '#fff'
                }
            });
            
            // 3. Cluster Counts (Text)
            mapRef.addLayer({
                id: 'cluster-count',
                type: 'symbol',
                source: SOURCES.points,
                filter: ['has', 'point_count'],
                layout: {
                    'text-field': '{point_count_abbreviated}',
                    'text-font': ['DIN Offc Pro Medium', 'Arial Unicode MS Bold'],
                    'text-size': 12
                },
                paint: {
                    'text-color': '#000000'
                }
            });
        }

        if (!map.__spellatlasEventsBound) {
            mapRef.on('click', LAYERS.points, (event: maplibregl.MapLayerMouseEvent) => {
                const feature = event.features?.[0];
                if (!feature) return;
                const geometry = feature.geometry;
                if (!geometry || geometry.type !== 'Point' || !Array.isArray(geometry.coordinates)) return;
                const coordinates = geometry.coordinates.slice(0, 2) as [number, number];
                const props = (feature.properties || {}) as Record<string, unknown>;
                const hasError = props.has_error === 'true' || props.has_error === true;
                const popupContent = `
                    <div class="font-tech p-2 min-w-[200px]">
                        <div class="flex justify-between items-center mb-2 border-b border-white/20 pb-1">
                            <span class="text-neon-blue font-bold">${String(props.country_name || '')}</span>
                            <span class="text-xs text-gray-400">${new Date(
                                Number(props.timestamp || Date.now())
                            ).toLocaleTimeString()}</span>
                        </div>
                        <div class="text-sm mb-2 text-white">"${String(props.headline || '')}"</div>
                        ${
                            hasError
                                ? `
                            <div class="bg-red-900/30 border border-red-500/50 p-2 rounded text-xs">
                                <div class="text-red-400 font-bold">DETECTED ERROR</div>
                                <div>Word: <span class="text-white">${String(props.error_word || 'Unknown')}</span></div>
                                <div>Correct: <span class="text-green-400">${String(props.error_suggestion || 'Unknown')}</span></div>
                            </div>
                        `
                                : '<div class="text-green-400 text-xs">✓ Verified Authentic</div>'
                        }
                    </div>
                `;
                new maplibregl.Popup({ closeButton: false, offset: 12 })
                    .setLngLat(coordinates)
                    .setHTML(popupContent)
                    .addTo(mapRef);
            });

            mapRef.on('mouseenter', LAYERS.points, () => {
                mapRef.getCanvas().style.cursor = 'pointer';
            });
            mapRef.on('mouseleave', LAYERS.points, () => {
                mapRef.getCanvas().style.cursor = '';
            });
            mapRef.__spellatlasEventsBound = true;
        }
    }

    /**
     * Ensures a GeoJSON source exists on the map; if not, creates it.
     * @param {string} id - Source ID.
     * @param {any[]} features - Initial features.
     */
    function ensureSource(id: string, features: PointFeature[]) {
        if (!map) return;
        const mapRef = map;
        if (!mapRef.getSource(id)) {
            const options: maplibregl.GeoJSONSourceSpecification = {
                type: 'geojson',
                data: { type: 'FeatureCollection', features }
            };
            
            // Enable Clustering for Points Source
            if (id === SOURCES.points) {
                options.cluster = true;
                options.clusterMaxZoom = 14; // Max zoom to cluster points
                options.clusterRadius = 50; // Radius of each cluster when clustering points (defaults to 50)
            }
            
            mapRef.addSource(id, options);
        } else {
            updateSource(id, features);
        }
    }

    /**
     * Updates the data of an existing GeoJSON source.
     * @param {string} id - Source ID.
     * @param {any[]} features - New features list.
     */
    function updateSource(id: string, features: PointFeature[]) {
        if (!map) return;
        const source = map.getSource(id) as maplibregl.GeoJSONSource | undefined;
        if (source) {
            source.setData({ type: 'FeatureCollection', features });
        }
    }

    function bumpHeatCount(code: string, inc: number, now: number) {
        const key = String(code).toUpperCase();
        const cur = liveHeatCounts.get(key);
        let nextCount = inc;
        if (cur) {
            const age = now - (cur.lastUpdated || now);
            const factor = Math.exp(-age / HEAT_HALF_LIFE_MS);
            nextCount = cur.count * factor + inc;
        }
        const next = { count: nextCount, lastUpdated: now };
        liveHeatCounts.set(key, next);
    }

    function decayLiveHeat(now: number) {
        const entries = Array.from(liveHeatCounts.entries());
        const survived: SvelteMap<string, { count: number; lastUpdated: number }> = new SvelteMap();
        for (const [code, val] of entries) {
            const age = now - (val.lastUpdated || now);
            const factor = Math.exp(-age / HEAT_HALF_LIFE_MS);
            const decayed = val.count * factor;
            if (decayed > 0.1) {
                survived.set(code, { count: decayed, lastUpdated: val.lastUpdated });
            }
        }
        liveHeatCounts = survived;
    }

    function refreshHeatSource(now: number = Date.now()) {
        decayLiveHeat(now);
        const features: PointFeature[] = [];
        let maxIntensity = 1;
        const merged: SvelteMap<string, number> = new SvelteMap();
        // Base counts
        for (const [code, count] of baseHeatCounts.entries()) {
            merged.set(code, count);
            if (count > maxIntensity) maxIntensity = count;
        }
        // Live counts
        for (const [code, val] of liveHeatCounts.entries()) {
            const next = (merged.get(code) || 0) + (val.count || 0);
            merged.set(code, next);
            if (next > maxIntensity) maxIntensity = next;
        }
        // Build feature collection using country centers
        for (const [code, count] of merged.entries()) {
            const country = getCountryByCode(code);
            if (!country) continue;
            const normalized = Math.log1p(count) / Math.log1p(maxIntensity || 1);
            features.push({
                type: 'Feature',
                geometry: { type: 'Point', coordinates: [country.lng, country.lat] },
                properties: { intensity: normalized }
            });
        }
        heatFeatures = features;
        if (map && mapLoaded) ensureSource(SOURCES.heat, heatFeatures);
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
                const domain = String(itemObj.domain).toLowerCase();
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
    function resolveLngLatWithMeta(item: NewsItem): { position: [number, number] | null; meta: LngLatMeta | null } {
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
     * Adds an item to the update buffer for batch processing.
     * @param {any} item - The data item.
     * @param {boolean} [showEffects=true] - Whether to trigger visual effects (popup/lines).
     */
    function addItem(item: NewsItem, showEffects = true) {
        if (!map || !mapLoaded) return;
        updateBuffer.push({ item, showEffects });
    }

    // Reactive Heatmap Update on Date/Scale Change
    // Removed legacy simulation watchers ($simulationDate, $timeScale, $isPlaying)
    // as the system is now Live-Only.

    /**
     * Main Animation Loop.
     * Processes buffered updates and renders them to the map.
     * @param {number} timestamp
     */
    function processBatch(timestamp: number) {
        requestAnimationFrame(processBatch);
        void timestamp;
        
        if (updateBuffer.length === 0) return;
        if (!map || !mapLoaded) return;

        // Process all items in buffer
        const batch = updateBuffer;
        updateBuffer = []; // Clear buffer immediately

        let hasUpdates = false;
        
        // Only trigger heavy effects (popup/pulse) for the LATEST item in the batch
        // to prevent UI chaos during high throughput
        const lastItemIndex = batch.length - 1;

        batch.forEach(({ item, showEffects }, index) => {
            const resolved = resolveLngLatWithMeta(item);
            const position = resolved.position;
            if (!position) return;

            const featureId = `${item.id || item.timestamp || Date.now()}-${Math.random()}`;
            const isError = !!item.has_error;

            pointFeatures.push({
                type: 'Feature',
                geometry: { type: 'Point', coordinates: position },
                properties: {
                    id: featureId,
                    has_error: isError,
                    country_name: item.country_name || '',
                    headline: item.headline || '',
                    timestamp: item.timestamp || Date.now(),
                    error_word: item.error_details?.word || '',
                    error_suggestion: item.error_details?.suggestion || ''
                }
            });

            const countryCode = getItemCountryCode(item);
            if (countryCode) {
                bumpHeatCount(countryCode, 1, Date.now());
            }

            // Lines logic REMOVED

            // Visual Effects (Markers) - Only for the last item or specific conditions
            const isLast = index === lastItemIndex;
            
            if (showEffects && isLast) {
                updateVisualEffects(position, item, resolved.meta);
            }

            hasUpdates = true;
        });

        if (hasUpdates) {
            if (pointFeatures.length > 500) pointFeatures = pointFeatures.slice(pointFeatures.length - 500);

            updateSource(SOURCES.points, pointFeatures);
            refreshHeatSource();
        }
    }

    /**
     * Renders transient visual effects (scan marker, pulse, popup) on the map.
     * @param {any} position
     * @param {any} item
     * @param {any} isError
     */
    function updateVisualEffects(position: [number, number], item: NewsItem, meta: LngLatMeta | null) {
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

        if (scanLabelMarker) {
            scanLabelMarker.remove();
            scanLabelMarker = null;
        }
        if (scanLabelMarkerTimeout) {
            clearTimeout(scanLabelMarkerTimeout);
            scanLabelMarkerTimeout = null;
        }

        const point = mapRef.project(position);
        const width = mapRef.getCanvas().width;
        const height = mapRef.getCanvas().height;
        const { anchor, offset } = getSmartAnchor(point, width, height);
        const labelEl = createNewsCardElement(item, meta);

        scanLabelMarker = new maplibregl.Marker({
            element: labelEl,
            anchor: anchor,
            offset: offset
        })
            .setLngLat(position)
            .addTo(mapRef);

        scanLabelMarkerTimeout = setTimeout(() => {
            if (scanLabelMarker) {
                scanLabelMarker.remove();
                scanLabelMarker = null;
            }
            scanLabelMarkerTimeout = null;
        }, 6000);
    }

    $: if (map && $mapMode && $mapMode !== currentStyle) {
        const nextStyle = STYLE_URLS[$mapMode];
        if (nextStyle) {
            currentStyle = $mapMode;
            map.setStyle(nextStyle);
            // No CSS filters needed for standard OSM/Satellite modes
            if (mapElement) {
                mapElement.style.filter = 'none';
            }
        }
    }

    // Toggle Live Layers visibility based on mode
    $: if (map && mapLoaded) {
        const liveVisibility = isVisualizing ? 'visible' : 'none';
        if (map.getLayer(LAYERS.points)) map.setLayoutProperty(LAYERS.points, 'visibility', liveVisibility);

        // Clear live markers when switching to historical mode
        if (!isVisualizing) {
            if (scanMarker) {
                scanMarker.remove();
                scanMarker = null;
            }
            if (scanLabelMarker) {
                scanLabelMarker.remove();
                scanLabelMarker = null;
            }
            if (scanLabelMarkerTimeout) {
                clearTimeout(scanLabelMarkerTimeout);
                scanLabelMarkerTimeout = null;
            }
        }
    }

</script>

<div class="absolute top-0 left-0 w-full h-full" bind:this={mapElement}></div>
{#if $heatmapEnabled}
    <div class="absolute bottom-4 left-4 z-[60] pointer-events-none">
        <div class="bg-black/60 backdrop-blur-md border border-white/10 rounded px-3 py-2 text-white max-w-[320px]">
            <div class="flex items-center justify-between gap-3">
                <div class="text-[10px] font-semibold tracking-wide">Heatmap: Activity Intensity</div>
                <div class="text-[9px] text-gray-300 font-mono">I = log(1 + c) / log(1 + c_max)</div>
            </div>
            <div class="mt-2 h-2 rounded heatmap-legend-gradient"></div>
            <div class="mt-1 flex justify-between text-[9px] text-gray-300 font-mono">
                <span>Low</span>
                <span>High</span>
            </div>
            <div class="mt-1 text-[9px] text-gray-400 leading-snug">
                Country-level kernel density from merged baseline + live stream; logarithmic normalization preserves rank under heavy-tailed counts.
            </div>
        </div>
    </div>
{/if}



<style>
    :global(.maplibregl-popup-content) {
        background: rgba(10, 10, 31, 0.9);
        backdrop-filter: blur(10px);
        border: 1px solid #00f3ff;
        color: white;
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
        box-shadow: 0 0 10px rgba(34, 197, 94, 0.85);
        transition: background 180ms ease-out, box-shadow 180ms ease-out, transform 180ms ease-out;
        position: relative;
        z-index: 80;
    }

    :global(.scan-marker.scan-marker--high) {
        background: #22c55e;
        box-shadow: 0 0 10px rgba(34, 197, 94, 0.85);
        transform: scale(1);
    }
    :global(.scan-marker.scan-marker--medium) {
        background: #f59e0b;
        box-shadow: 0 0 10px rgba(245, 158, 11, 0.8);
        transform: scale(1.05);
    }
    :global(.scan-marker.scan-marker--low) {
        background: #ef4444;
        box-shadow: 0 0 12px rgba(239, 68, 68, 0.85);
        transform: scale(1.1);
    }

    :global(.news-card-accent) {
        background: linear-gradient(90deg, var(--gmp-accent, #00f3ff) 0%, rgba(0, 0, 0, 0) 100%);
        opacity: 0.95;
    }

    :global(.heatmap-legend-gradient) {
        background: linear-gradient(
            90deg,
            rgba(68, 1, 84, 0.35) 0%,
            rgba(59, 82, 139, 0.55) 25%,
            rgba(33, 145, 140, 0.65) 50%,
            rgba(94, 201, 98, 0.75) 75%,
            rgba(253, 231, 37, 0.9) 100%
        );
    }

    :global(.server-marker) {
        width: 20px;
        height: 20px;
        background: radial-gradient(circle, #22d3ee 40%, rgba(34, 211, 238, 0.2) 70%);
        border: 2px solid #22d3ee;
        border-radius: 50%;
        box-shadow: 0 0 15px #22d3ee;
        z-index: 50;
    }
    
    :global(.server-marker.pulse) {
        animation: server-pulse 0.5s ease-out;
    }

    @keyframes server-pulse {
        0% { transform: scale(1); box-shadow: 0 0 15px #22d3ee; filter: brightness(1); }
        50% { transform: scale(1.5); box-shadow: 0 0 30px #22d3ee; filter: brightness(2); background: #fff; }
        100% { transform: scale(1); box-shadow: 0 0 15px #22d3ee; filter: brightness(1); }
    }

</style>
