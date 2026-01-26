<script lang="ts">
    import { onMount, onDestroy, getContext } from 'svelte';
    import { SvelteMap } from 'svelte/reactivity';
    import { latestNewsItem, mapMode, heatmapEnabled, newsEvents, systemLogs } from '../stores.js';
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
    let countriesByCode: SvelteMap<string, CountryRecord> = new SvelteMap();
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

    function createNewsCardElement(article: NewsItem) {
        const countryCode = article.country_code || article.country || 'UNK';
        const countryData = getCountryByCode(countryCode);
        const countryName = countryData?.name || countryCode;
        const flagCode = countryData?.code_alpha2 || (countryCode.length === 2 ? countryCode : null);
        const flagUrl = flagCode ? `https://flagcdn.com/w20/${flagCode.toLowerCase()}.png` : null;
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

        const root = document.createElement('div');
        root.className = 'pointer-events-none select-none relative group news-card-marker';

        const card = document.createElement('div');
        card.className = 'relative min-w-[220px] max-w-[280px] bg-[#0a0f1c]/90 backdrop-blur-md border border-white/10 rounded-sm shadow-[0_0_15px_rgba(0,243,255,0.15)] overflow-hidden flex flex-col';
        root.appendChild(card);

        const accent = document.createElement('div');
        accent.className = 'absolute top-0 left-0 w-full h-[2px] bg-gradient-to-r from-neon-blue via-neon-purple to-transparent';
        card.appendChild(accent);

        const header = document.createElement('div');
        header.className = 'flex items-center justify-between px-3 py-2 border-b border-white/5 bg-white/5';
        card.appendChild(header);

        const headerLeft = document.createElement('div');
        headerLeft.className = 'flex items-center gap-2';
        header.appendChild(headerLeft);

        if (flagUrl) {
            const flagImg = document.createElement('img');
            flagImg.src = flagUrl;
            flagImg.alt = countryCode;
            flagImg.className = 'w-4 h-auto rounded-[1px] opacity-80';
            headerLeft.appendChild(flagImg);
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
        body.className = 'p-3 flex items-center gap-3';
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

        if (article.title) {
            const titleEl = document.createElement('p');
            titleEl.className = 'text-[9px] text-gray-400 line-clamp-2 leading-snug';
            titleEl.textContent = article.title;
            info.appendChild(titleEl);
        }

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
    let currentMarker: maplibregl.Marker | null = null;
    let currentMarkerTimeout: ReturnType<typeof setTimeout> | null = null;
    let currentPopup: maplibregl.Popup | null = null;
    let scanMarker: maplibregl.Marker | null = null;
    let scanLabelMarker: maplibregl.Marker | null = null;
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

    function resolveCoordinates(article: NewsItem): [number, number] | null {
        const normalized = {
            ...article,
            country_code: getItemCountryCode(article) || undefined
        };
        return resolveLngLat(normalized);
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
        const mapRef = map;
        
        // Throttle Logic
        const now = Date.now();
        if (now - lastEventTime < EVENT_THROTTLE_MS) {
            return;
        }
        lastEventTime = now;
        
        // Play Sound
        soundManager.playDataChirp();

        const coords = resolveCoordinates(article);
        if (coords) {
            if (scanLabelMarker) scanLabelMarker.remove();

            const point = mapRef.project(coords);
            const width = mapRef.getCanvas().width;
            const height = mapRef.getCanvas().height;
            const { anchor, offset } = getSmartAnchor(point, width, height);

            const labelEl = createNewsCardElement(article);

            scanLabelMarker = new maplibregl.Marker({
                element: labelEl,
                anchor: anchor,
                offset: offset
            })
            .setLngLat(coords)
            .addTo(mapRef);

            setTimeout(() => {
                if (scanLabelMarker) {
                    scanLabelMarker.remove();
                    scanLabelMarker = null;
                }
            }, 6000);
            
            const feature: PointFeature = {
                type: 'Feature',
                geometry: { type: 'Point', coordinates: coords },
                properties: { ...article, timestamp: now }
            };
            
            pointFeatures.push(feature);
            if (pointFeatures.length > 2000) pointFeatures.shift(); // Keep buffer manageable
            
            ensureSource(SOURCES.points, pointFeatures);

            const countryCode = getItemCountryCode(article);
            if (countryCode) {
                bumpHeatCount(countryCode, 1, now);
                refreshHeatSource(now);
            }

        } else {
             console.warn(`[Visualization] Skipped article from ${article.country}: No coordinates.`);
        }

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
        if (isDev) {
            (window as Window & { map?: maplibregl.Map }).map = mapInstance;
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
        if (currentMarkerTimeout) clearTimeout(currentMarkerTimeout);
        if (scanMarker) scanMarker.remove();
        if (serverMarker) serverMarker.remove();
    });

    /**
     * Loads country GeoJSON boundaries for client-side geofencing.
     */
    async function loadCountries() {
        try {
            const apiBase =
                (import.meta as { env?: { VITE_API_URL?: string } }).env?.VITE_API_URL ||
                (window.location.hostname === 'localhost'
                    ? 'http://localhost:8000'
                    : 'https://spellatlas-backend-production.fly.dev');
            
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
                        1, 0.7,
                        4, 1.0,
                        7, 1.3,
                        10, 1.6
                    ],
                    'heatmap-radius': [
                        'interpolate',
                        ['linear'],
                        ['zoom'],
                        1, 8,
                        4, 16,
                        7, 28,
                        10, 40
                    ],
                    'heatmap-opacity': 0.7,
                    'heatmap-color': [
                        'interpolate',
                        ['linear'],
                        ['heatmap-density'],
                        0, 'rgba(0,0,0,0)',
                        0.2, '#440154',
                        0.4, '#3b528b',
                        0.6, '#21918c',
                        0.8, '#5ec962',
                        1.0, '#fde725'
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
        const next: SvelteMap<string, CountryRecord> = new SvelteMap();
        for (const entry of list) {
            if (!entry || !entry.code) continue;
            const code = String(entry.code).toUpperCase();
            next.set(code, {
                ...entry,
                code
            });
        }
        countriesByCode = next;
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
        const fromApi = countriesByCode.get(normalized);
        if (fromApi) return fromApi;
        return DATA.COUNTRIES.find((c) => c.code === normalized) || null;
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
    function resolveLngLat(item: NewsItem): [number, number] | null {
        const countryCode = getItemCountryCode(item);
        let position = toLngLat(item?.coordinates);
        if (!position) {
            position = toLngLat({ lng: item?.lng, lat: item?.lat });
        }
        if (!position && countryCode) {
            position = getCalibratedLngLat(countryCode);
        }
        if (!position) {
             return null;
        }
        const safePosition = position;

        const canValidateCountry =
            countryCode &&
            countryPolygonsByCode.size > 0 &&
            countryPolygonsByCode.has(countryCode);
        
        if (canValidateCountry && safePosition && !isPointInCountry(safePosition, countryCode)) {
            const fallback = getCalibratedLngLat(countryCode);
            if (fallback) position = fallback;
        }
        const finalPosition = position;
        if (!canValidateCountry && Math.abs(finalPosition[0]) < 1 && Math.abs(finalPosition[1]) < 1) {
            return null;
        }
        return finalPosition;
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
            const position = resolveLngLat(item);
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
                updateVisualEffects(position, item, isError);
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
    function updateVisualEffects(position: [number, number], item: NewsItem, isError: boolean) {
        // Scan Marker (Cyan Dot)
        if (!map) return;
        const mapRef = map;
        if (!scanMarker) {
            const el = document.createElement('div');
            el.className = 'scan-marker';
            scanMarker = new maplibregl.Marker({ element: el })
                .setLngLat(position)
                .addTo(mapRef);
        } else {
            scanMarker.setLngLat(position);
        }

        // Pulse / Popup for Errors
        if (isError) {
            if (currentMarker) currentMarker.remove();
            if (currentPopup) currentPopup.remove();
            if (currentMarkerTimeout) clearTimeout(currentMarkerTimeout);
            
            const el = document.createElement('div');
            el.className = 'pulse-marker';
            
            currentMarker = new maplibregl.Marker({ element: el })
                .setLngLat(position)
                .addTo(mapRef);

            // Format timestamp for popup (Full Date + Time)
            const dateObj = item.timestamp ? new Date(item.timestamp) : new Date();
            const timeStr = dateObj.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
            const dateStr = dateObj.toLocaleDateString([], { year: 'numeric', month: 'short', day: 'numeric' });
            const timestampDisplay = `${dateStr} ${timeStr}`;

            const headline = item.headline || 'No Headline';

            const popupContent = `
                <div class="font-tech p-2 min-w-[200px]">
                    <div class="flex justify-between items-center mb-2 border-b border-white/20 pb-1">
                        <span class="text-neon-blue font-bold">${item.country_name || ''}</span>
                        <span class="text-xs text-gray-400">${timestampDisplay}</span>
                    </div>
                    <div class="text-sm mb-2 text-white">"${headline}"</div>
                    <div class="bg-red-900/30 border border-red-500/50 p-2 rounded text-xs">
                        <div class="text-red-400 font-bold">DETECTED ERROR</div>
                        <div>Word: <span class="text-white">${item.error_details?.word || 'Unknown'}</span></div>
                        <div>Correct: <span class="text-green-400">${item.error_details?.suggestion || 'Unknown'}</span></div>
                    </div>
                </div>
            `;

            currentPopup = new maplibregl.Popup({
                closeButton: false,
                closeOnClick: false,
                className: 'neon-popup',
                maxWidth: '300px',
                offset: 25
            })
                .setLngLat(position)
                .setHTML(popupContent)
                .addTo(mapRef);

            currentMarkerTimeout = setTimeout(() => {
                if (currentMarker) currentMarker.remove();
                if (currentPopup) currentPopup.remove();
                currentMarker = null;
                currentPopup = null;
            }, 5000);
        }
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

    $: if ($latestNewsItem && map && isVisualizing) {
        const rawItem = $latestNewsItem as NewsItem;
        // Normalize item structure to ensure map compatibility
        const item = {
            ...rawItem,
            country_code: rawItem.country_code || rawItem.country || rawItem.countryCode || undefined,
            headline: rawItem.headline || rawItem.title,
            has_error: rawItem.has_error || (rawItem.errors && rawItem.errors.length > 0),
            error_details: rawItem.error_details || (rawItem.errors && rawItem.errors.length > 0 ? rawItem.errors[0] : null)
        };
        addItem(item);
    }

    // Toggle Live Layers visibility based on mode
    $: if (map && mapLoaded) {
        const liveVisibility = isVisualizing ? 'visible' : 'none';
        if (map.getLayer(LAYERS.points)) map.setLayoutProperty(LAYERS.points, 'visibility', liveVisibility);

        // Clear live markers when switching to historical mode
        if (!isVisualizing) {
            if (currentMarker) {
                currentMarker.remove();
                currentMarker = null;
            }
            if (currentPopup) {
                currentPopup.remove();
                currentPopup = null;
            }
            if (scanMarker) {
                scanMarker.remove();
                scanMarker = null;
            }
        }
    }

</script>

<div class="absolute top-0 left-0 w-full h-full" bind:this={mapElement}></div>



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

    :global(.pulse-marker) {
        width: 20px;
        height: 20px;
        background: rgba(255, 255, 0, 0.4); /* Yellow for Alert */
        border: 2px solid #ffff00;
        border-radius: 50%;
        box-shadow: 0 0 15px #ffff00, inset 0 0 10px #ffff00;
        cursor: pointer;
        animation: pulse 1.0s infinite; /* Faster pulse for urgency */
        position: relative;
        z-index: 1000;
    }
    
    :global(.scan-marker) {
        width: 12px;
        height: 12px;
        background: #00f3ff;
        border: 2px solid white;
        border-radius: 50%;
        box-shadow: 0 0 10px #00f3ff;
        transition: all 0.5s ease-out;
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

    :global(.neon-popup .maplibregl-popup-content) {
        background: rgba(5, 5, 10, 0.9);
        border: 1px solid #00f3ff;
        box-shadow: 0 0 10px rgba(0, 243, 255, 0.2);
        border-radius: 4px;
        padding: 0;
        color: white;
    }

    :global(.neon-popup .maplibregl-popup-tip) {
        border-top-color: #00f3ff;
    }

    :global(.pulse-marker:hover) {
        opacity: 1;
    }

    @keyframes pulse {
        0% { transform: scale(1); opacity: 1; }
        70% { transform: scale(3); opacity: 0; }
        100% { transform: scale(1); opacity: 0; }
    }
</style>
