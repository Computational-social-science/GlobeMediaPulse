<script>
    import { onMount, onDestroy } from 'svelte';
    import { latestNewsItem, countryStats, mapMode, heatmapEnabled, newsEvents, systemStatus } from '../stores.js';
    import { soundManager } from '../audio/SoundManager.js';
    import { DATA } from '../data.js';
    import maplibregl from 'maplibre-gl';

    /** @type {HTMLElement} */
    let mapElement;
    /** @type {maplibregl.Map} */
    let map;
    let mapLoaded = false;
    /** @type {any} */
    let countriesGeojson = null;
    let currentStyle = 'vector';
    
    /** @type {any[]} */
    let updateBuffer = [];
    $: isLiveMode = true; // Always live in this version
    // Allow visualization if Live, Simulating (Playing), or if we are just receiving data stream
    $: isVisualizing = true;

    const SOURCES = {
        heat: 'heat-errors',
        points: 'event-points',
        lines: 'threat-lines',
        countries: 'countries'
    };

    const LAYERS = {
        heat: 'heat-layer',
        points: 'point-layer',
        lines: 'line-layer',
        countries: 'country-layer'
    };

    const STYLE_URLS = {
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

    const INITIAL_VIEW = { center: [0, 20], zoom: 2 };

    /** @type {any[]} */
    let heatFeatures = [];
    /** @type {any[]} */
    let pointFeatures = [];
    /** @type {any[]} */
    let lineFeatures = [];
    /** @type {any[]} */
    let recentErrors = [];
    const THREAT_WINDOW = 5000;
    const THREAT_MAX_DIST = 2000000;
    const THREAT_MIN_DIST = 100000;

    /** @type {any} */
    let currentMarker = null; // For Errors (Red Pulse)
    /** @type {any} */
    let currentMarkerTimeout = null;
    /** @type {any} */
    let currentPopup = null;
    /** @type {any} */
    let scanMarker = null; // For News Stream (Cyan Dot)
    /** @type {any} */
    let scanLabelMarker = null; // For "Scanning [Country]" Label
    /** @type {any} */
    let serverMarker = null; // Server Location Marker (Los Angeles)
    const countryPolygonsByCode = new Map();

    // Reactive Map Controls
    $: if (map && mapLoaded) {
        try {
            // Register dependencies
            // @ts-ignore
            const _dependencies = [$heatmapEnabled];

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
        const style = map.getStyle();
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
                map.setPaintProperty(layer.id, 'background-color', COLORS.background);
                // @ts-ignore
                if (map.getPaintProperty(layer.id, 'background-opacity') !== undefined) {
                     map.setPaintProperty(layer.id, 'background-opacity', 1);
                }
            }
            
            // Water
            if (layer.id.includes('water')) {
                if (layer.type === 'fill') {
                    map.setPaintProperty(layer.id, 'fill-color', COLORS.water);
                } else if (layer.type === 'line') {
                    map.setPaintProperty(layer.id, 'line-color', COLORS.waterOutline);
                }
            }

            // Land
            if (layer.id.includes('land') || layer.id.includes('usage') || layer.id.includes('urban')) {
                 if (layer.type === 'fill') {
                    map.setPaintProperty(layer.id, 'fill-color', COLORS.land);
                }
            }

            // Boundaries (Admin)
            if (layer.id.includes('admin') || layer.id.includes('boundary')) {
                if (layer.type === 'line') {
                    map.setPaintProperty(layer.id, 'line-color', COLORS.boundary);
                    map.setPaintProperty(layer.id, 'line-width', 0.8);
                    map.setPaintProperty(layer.id, 'line-opacity', 0.6);
                }
            }

            // Roads
            if (layer.id.includes('road') || layer.id.includes('tunnel') || layer.id.includes('bridge')) {
                if (layer.type === 'line') {
                    map.setPaintProperty(layer.id, 'line-color', COLORS.road);
                }
            }
            
            // Labels
            if (layer.type === 'symbol') {
                 if (layer.layout && layer.layout['text-field']) {
                    map.setPaintProperty(layer.id, 'text-color', COLORS.text);
                    map.setPaintProperty(layer.id, 'text-halo-color', COLORS.textHalo);
                    map.setPaintProperty(layer.id, 'text-halo-width', 1);
                 }
            }
        });
    }

    // --- WebSocket & Real-time Visualization ---
    
    // Total Sources Counter
    let totalSources = 0;
    
    // Subscribe to global news events from store
    $: if ($newsEvents) {
        handleNewsEvent($newsEvents);
    }

    onMount(async () => {
        // Fetch Initial Stats
        try {
            // Fetch map data which includes total_articles and total_sources
            const res = await fetch('http://localhost:8002/api/map-data');
            if (res.ok) {
                const data = await res.json();
                if (data.total_sources) {
                    totalSources = data.total_sources;
                }
            }
        } catch (e) {
            console.error("Failed to fetch map stats:", e);
        }
    });

    /** @type {number} */
    let lastEventTime = 0;
    const EVENT_THROTTLE_MS = 200; // Limit to 5 events per second

    /**
     * @param {any} article
     */
    function handleNewsEvent(article) {
        // Logic Linkage: If system is OFFLINE, ignore incoming data events
        if ($systemStatus === 'OFFLINE') return;

        if (!mapLoaded || !map) return;
        
        // Throttle Logic
        const now = Date.now();
        if (now - lastEventTime < EVENT_THROTTLE_MS) {
            return;
        }
        lastEventTime = now;
        
        // Play Sound
        soundManager.playDataChirp();

        // Scanning Animation: Update Scan Label
        const coords = resolveCoordinates(article);
        if (coords) {
            // Remove previous label
            if (scanLabelMarker) scanLabelMarker.remove();

            // Create new label
            const labelEl = document.createElement('div');
            labelEl.className = 'scanning-label';
            
            // Visual Fingerprint Integration
            // If logo_url is present (from backend pipeline), display it.
            // Otherwise fallback to the pulsing dot.
            const iconHtml = article.logo_url 
                ? `<img src="${article.logo_url}" class="w-6 h-6 rounded-full border border-white/20 bg-white object-contain p-0.5" alt="logo" onerror="this.style.display='none'"/>` 
                : `<div class="w-2 h-2 bg-neon-blue rounded-full animate-ping"></div>`;

            labelEl.innerHTML = `
                <div class="flex items-center gap-2">
                    ${iconHtml}
                    <span class="text-[10px] font-mono font-bold text-neon-blue bg-white/90 px-2 py-1 rounded border border-neon-blue/30 shadow-sm flex flex-col">
                        <span>SCANNING: ${article.country || 'UNKNOWN'}</span>
                        ${article.source_domain ? `<span class="text-[8px] text-gray-500 font-normal">${article.source_domain}</span>` : ''}
                    </span>
                </div>
            `;
            
            scanLabelMarker = new maplibregl.Marker({
                element: labelEl,
                anchor: 'left',
                offset: [15, 0]
            })
            // @ts-ignore
            .setLngLat(coords)
            .addTo(map);

            // Auto-remove after 2 seconds
            setTimeout(() => {
                if (scanLabelMarker && scanLabelMarker.getElement() === labelEl) {
                    scanLabelMarker.remove();
                }
            }, 2000);
        }

        
        // Pulse Server Marker (Throughput Visualization)
        pulseServer();

        // Find Source Country
        const countryCode = article.country;
        // Lookup in DATA.COUNTRIES
        const country = DATA.COUNTRIES.find(c => c.code === countryCode);
        
        if (country) {
            const sourceCoords = [country.lng, country.lat];
            // Target: Server Location (Los Angeles, USA) - approx
            const targetCoords = [-118.24, 34.05]; 
            
            addBeam(sourceCoords, targetCoords, article.confidence);
        }
    }

    /**
     * @param {any} start
     * @param {any} end
     * @param {string} [confidence] - 'high' | 'medium' | 'low' | 'unknown'
     */
    function addBeam(start, end, confidence = 'unknown') {
        const id = Date.now() + Math.random();
        const feature = {
            type: 'Feature',
            id: id,
            geometry: {
                type: 'LineString',
                coordinates: [start, end]
            },
            properties: {
                timestamp: Date.now(),
                confidence: confidence
            }
        };
        
        lineFeatures = [...lineFeatures, feature];
        updateLinesSource();
        
        // Remove after 1.5 seconds (Flash effect)
        setTimeout(() => {
            lineFeatures = lineFeatures.filter(f => f.id !== id);
            updateLinesSource();
        }, 1500);
    }

    function updateLinesSource() {
        if (!map) return;
        const source = map.getSource(SOURCES.lines);
        if (source) {
            // @ts-ignore
            source.setData({
                type: 'FeatureCollection',
                features: lineFeatures
            });
        }
    }

    function setupServerMarker() {
        if (!map) return;
        
        const el = document.createElement('div');
        el.className = 'server-marker';
        
        // Server Location: Los Angeles
        serverMarker = new maplibregl.Marker({ element: el })
            .setLngLat([-118.24, 34.05])
            .addTo(map);
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
        map = new maplibregl.Map({
            container: mapElement,
            style: STYLE_URLS.vector, // Using Carto Dark Matter for Vector Tiles
            // @ts-ignore
            center: INITIAL_VIEW.center,
            zoom: INITIAL_VIEW.zoom,
            minZoom: 1, // Allow seeing whole world
            maxZoom: 18, // Standard OSM max zoom
            renderWorldCopies: true, // Infinite horizontal scroll
            // @ts-ignore
            attributionControl: true,
            projection: 'globe' // Enable Globe Projection (MapLibre GL JS v3+)
        });

        // @ts-ignore
        if (import.meta.env.DEV) {
            // @ts-ignore
            window.map = map;
        }

        // Ensure strict window adaptation
        const resizeObserver = new ResizeObserver(() => {
            map.resize();
        });
        resizeObserver.observe(mapElement);

        map.on('load', () => {
            mapLoaded = true;
            try {
                applyTechStyle(); // Apply Tech Style Override
                setupLayers();
                setupServerMarker(); // Initialize Server Marker
                // fetchInitialStats();
                loadCountries();
                // Initial heatmap load based on current state
                // fetchHeatmapData();
                requestAnimationFrame(processBatch);
            } catch (e) {
                console.error("Error during map load:", e);
            }
        });

        map.on('style.load', () => {
            if (mapLoaded) {
                try {
                    applyTechStyle(); // Apply Tech Style Override
                    setupLayers();
                    if (countriesGeojson) {
                        updateCountriesSource(countriesGeojson);
                    }
                    // Restore Heatmap Visibility
                    if (map.getLayer(LAYERS.heat)) {
                        map.setLayoutProperty(LAYERS.heat, 'visibility', $heatmapEnabled ? 'visible' : 'none');
                    }
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
     * Fetches initial map statistics and historical error data.
     */
    async function fetchInitialStats() {
        try {
            const apiBase =
                // @ts-ignore
                import.meta.env.VITE_API_URL ||
                (window.location.hostname === 'localhost'
                    ? 'http://localhost:8000'
                    : 'https://spellatlas-backend-production.fly.dev');
            const statsRes = await fetch(`${apiBase}/api/map-data`);
            if (statsRes.ok) {
                const statsData = await statsRes.json();
                countryStats.set(statsData);
            }

            // Fetch recent historical errors to populate map on load
            const historicalRes = await fetch(`${apiBase}/api/errors?limit=200`);
            if (historicalRes.ok) {
                const history = await historicalRes.json();
                // @ts-ignore
                history.reverse().forEach((item) => {
                    addItem({
                        ...item,
                        has_error: true,
                        error_details: { word: item.word, suggestion: item.suggestion }
                    }, false); // Pass false to skip popup/pulse for history
                });
            }
        } catch (e) {
            console.warn('Backend offline or stats unavailable', e);
        }
    }

    /**
     * Loads country GeoJSON boundaries for client-side geofencing.
     */
    async function loadCountries() {
        try {
            const apiBase =
                // @ts-ignore
                import.meta.env.VITE_API_URL ||
                (window.location.hostname === 'localhost'
                    ? 'http://localhost:8000'
                    : 'https://spellatlas-backend-production.fly.dev');
            
            const response = await fetch(`${apiBase}/api/metadata/geojson`);
            const geoData = await response.json();
            countriesGeojson = {
                ...geoData,
                // @ts-ignore
                features: geoData.features.map((feature) => ({
                    ...feature,
                    properties: { ...feature.properties, code: feature.id }
                }))
            };
            buildCountryPolygons(countriesGeojson);
            updateCountriesSource(countriesGeojson);
        } catch (e) {
            console.error('Failed to load GeoJSON', e);
        }
    }

    /**
     * Configures Mapbox/MapLibre layers and sources.
     */
    function setupLayers() {
        if (!map) return;

        ensureSource(SOURCES.heat, heatFeatures);
        ensureSource(SOURCES.points, pointFeatures);
        ensureSource(SOURCES.lines, lineFeatures);
        
        if (!map.getLayer(LAYERS.countries) && map.getSource(SOURCES.countries)) {
            map.addLayer({
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

        if (!map.getLayer(LAYERS.heat)) {
            map.addLayer({
                id: LAYERS.heat,
                type: 'heatmap',
                source: SOURCES.heat,
                paint: {
                    'heatmap-weight': ['coalesce', ['get', 'intensity'], 1],
                    'heatmap-intensity': 1.2,
                    'heatmap-radius': 15, // Reduced for sharper non-halo look
                    'heatmap-opacity': 0.85,
                    'heatmap-color': [
                        'interpolate',
                        ['linear'],
                        ['heatmap-density'],
                        0,
                        'rgba(0,0,0,0)',
                        0.1, // Start color earlier to reduce blurry edges
                        '#2A004E',
                        0.3,
                        '#00F3FF',
                        0.5,
                        '#00FF00',
                        0.7,
                        '#FFFF00',
                        1,
                        '#FF0000'
                    ]
                }
            });
        }

        if (!map.getLayer(LAYERS.points)) {
            map.addLayer({
                id: LAYERS.points,
                type: 'circle',
                source: SOURCES.points,
                paint: {
                    'circle-radius': 0, // Hidden as per user request (only Heatmap + Active Scan Marker visible)
                    'circle-opacity': 0,
                    'circle-stroke-width': 0
                }
            });
        }

        if (!map.getLayer(LAYERS.lines)) {
            map.addLayer({
                id: LAYERS.lines,
                type: 'line',
                source: SOURCES.lines,
                paint: {
                    'line-color': '#00F3FF', // Neon Blue
                    'line-width': 2,
                    'line-opacity': 0.8,
                    'line-dasharray': [
                        'match',
                        ['get', 'confidence'],
                        'high', ['literal', [1, 0]],   // Solid for High Confidence (Seed)
                        ['literal', [2, 1]]            // Dashed for Inferred (Medium/Low/Unknown)
                    ]
                }
            });
        }

        // @ts-ignore
        if (!map.__spellatlasEventsBound) {
            map.on('click', LAYERS.points, (event) => {
                // @ts-ignore
                const feature = event.features?.[0];
                if (!feature) return;
                // @ts-ignore
                const coordinates = feature.geometry.coordinates.slice();
                const props = feature.properties || {};
                const hasError = props.has_error === 'true' || props.has_error === true;
                const popupContent = `
                    <div class="font-tech p-2 min-w-[200px]">
                        <div class="flex justify-between items-center mb-2 border-b border-white/20 pb-1">
                            <span class="text-neon-blue font-bold">${props.country_name || ''}</span>
                            <span class="text-xs text-gray-400">${new Date(
                                Number(props.timestamp || Date.now())
                            ).toLocaleTimeString()}</span>
                        </div>
                        <div class="text-sm mb-2 text-white">"${props.headline || ''}"</div>
                        ${
                            hasError
                                ? `
                            <div class="bg-red-900/30 border border-red-500/50 p-2 rounded text-xs">
                                <div class="text-red-400 font-bold">DETECTED ERROR</div>
                                <div>Word: <span class="text-white">${props.error_word || 'Unknown'}</span></div>
                                <div>Correct: <span class="text-green-400">${props.error_suggestion || 'Unknown'}</span></div>
                            </div>
                        `
                                : '<div class="text-green-400 text-xs">✓ Verified Authentic</div>'
                        }
                    </div>
                `;
                new maplibregl.Popup({ closeButton: false, offset: 12 })
                    // @ts-ignore
                    .setLngLat(coordinates)
                    .setHTML(popupContent)
                    .addTo(map);
            });

            map.on('mouseenter', LAYERS.points, () => {
                map.getCanvas().style.cursor = 'pointer';
            });
            map.on('mouseleave', LAYERS.points, () => {
                map.getCanvas().style.cursor = '';
            });
            // @ts-ignore
            map.__spellatlasEventsBound = true;
        }
    }

    /**
     * Ensures a GeoJSON source exists on the map; if not, creates it.
     * @param {string} id - Source ID.
     * @param {any[]} features - Initial features.
     */
    function ensureSource(id, features) {
        if (!map.getSource(id)) {
            map.addSource(id, {
                type: 'geojson',
                data: { type: 'FeatureCollection', features }
            });
        } else {
            updateSource(id, features);
        }
    }

    /**
     * Updates the data of an existing GeoJSON source.
     * @param {string} id - Source ID.
     * @param {any[]} features - New features list.
     */
    function updateSource(id, features) {
        const source = map.getSource(id);
        // @ts-ignore
        if (source && source.setData) {
            // @ts-ignore
            source.setData({ type: 'FeatureCollection', features });
        }
    }

    /**
     * Updates the countries source with new GeoJSON data.
     * @param {any} geojson - The GeoJSON object.
     */
    function updateCountriesSource(geojson) {
        if (!map) return;
        if (!map.getSource(SOURCES.countries)) {
            map.addSource(SOURCES.countries, { type: 'geojson', data: geojson });
        } else {
            const source = map.getSource(SOURCES.countries);
            // @ts-ignore
            if (source && source.setData) {
                // @ts-ignore
                source.setData(geojson);
            }
        }
    }

    /**
     * Pre-processes country polygons for fast client-side point-in-polygon checks.
     * @param {any} geojson - The countries GeoJSON.
     */
    function buildCountryPolygons(geojson) {
        countryPolygonsByCode.clear();
        geojson.features.forEach((/** @type {any} */ feature) => {
            const code = feature.id;
            const geometry = feature.geometry;
            if (!code || !geometry) return;
            if (geometry.type === 'Polygon') {
                const rings = geometry.coordinates.map((/** @type {any} */ ring) => ring.slice());
                countryPolygonsByCode.set(code, rings.map((/** @type {any} */ ring) => ring.slice()));
            } else if (geometry.type === 'MultiPolygon') {
                const polygons = geometry.coordinates.map((/** @type {any} */ poly) => poly[0]);
                countryPolygonsByCode.set(code, polygons);
            }
        });
    }

    /**
     * Determines if a point is inside a polygon using ray-casting algorithm.
     * @param {any} point - [lng, lat]
     * @param {any} polygon - Array of rings.
     */
    function isPointInPolygon(point, polygon) {
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
     */
    function toLngLat(value) {
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
            if (typeof value.lng === 'number' && typeof value.lat === 'number') {
                return [value.lng, value.lat];
            }
            if (typeof value.lon === 'number' && typeof value.lat === 'number') {
                return [value.lon, value.lat];
            }
            if (typeof value.longitude === 'number' && typeof value.latitude === 'number') {
                return [value.longitude, value.latitude];
            }
        }
        return null;
    }

    /** 
     * Retrieves the calibrated center coordinates for a country code.
     * @param {string} code - ISO 3166-1 alpha-3 code.
     */
    function getCalibratedLngLat(code) {
        if (!code) return null;
        const calibrated = DATA.COUNTRIES.find((c) => c.code === code);
        if (!calibrated) return null;
        return [calibrated.lng, calibrated.lat];
    }

    /**
     * Checks if a point lies within the boundaries of a specific country.
     * @param {any} point - [lng, lat]
     * @param {any} code - Country code.
     */
    function isPointInCountry(point, code) {
        const polygons = countryPolygonsByCode.get(code);
        if (!polygons) return false;
        return polygons.some((/** @type {any} */ polygon) => isPointInPolygon(point, polygon));
    }

    /**
     * Resolves the best available coordinates for an item.
     * Validates against country boundaries and falls back to country center or random ocean point if invalid.
     * @param {any} item - The data item.
     */
    function resolveLngLat(item) {
        let position = toLngLat(item?.coordinates);
        if (!position && item?.country_code) {
            position = getCalibratedLngLat(item.country_code);
        }
        
        // Fallback for UNK or missing position to ensure visualization
        if (!position) {
             // Assign a random position in the ocean/world map to ensure visibility of the error event
             // This ensures "UNK" events (often simulated or parsed without country) still trigger Neon Popups
             position = [(Math.random() * 360) - 180, (Math.random() * 120) - 60];
        }

        const canValidateCountry =
            item?.country_code &&
            countryPolygonsByCode.size > 0 &&
            countryPolygonsByCode.has(item.country_code);
        
        if (canValidateCountry && position && !isPointInCountry(position, item.country_code)) {
            const fallback = getCalibratedLngLat(item.country_code);
            if (fallback) position = fallback;
        }
        return position;
    }

    /**
     * Calculates the Great Circle distance between two points in meters (Haversine formula).
     * @param {any} a - Point A [lng, lat]
     * @param {any} b - Point B [lng, lat]
     */
    function distanceMeters(a, b) {
        const R = 6371e3;
        const lat1 = (a[1] * Math.PI) / 180;
        const lat2 = (b[1] * Math.PI) / 180;
        const dLat = ((b[1] - a[1]) * Math.PI) / 180;
        const dLng = ((b[0] - a[0]) * Math.PI) / 180;
        const sinLat = Math.sin(dLat / 2);
        const sinLng = Math.sin(dLng / 2);
        const h = sinLat * sinLat + Math.cos(lat1) * Math.cos(lat2) * sinLng * sinLng;
        return 2 * R * Math.atan2(Math.sqrt(h), Math.sqrt(1 - h));
    }

    /**
     * Adds an item to the update buffer for batch processing.
     * @param {any} item - The data item.
     * @param {boolean} [showEffects=true] - Whether to trigger visual effects (popup/lines).
     */
    function addItem(item, showEffects = true) {
        if (!map || !mapLoaded) return;
        updateBuffer.push({ item, showEffects });
    }

    let heatmapAbortController = new AbortController();

    /**
     * Fetches aggregated heatmap data from the backend.
     * @param {string|null} startStr - Optional start date string (YYYY-MM-DD).
     * @param {string|null} endStr - Optional end date string (YYYY-MM-DD).
     */
    async function fetchHeatmapData(startStr = null, endStr = null) {
        if (!map || !mapLoaded) return;
        
        // Abort previous request
        heatmapAbortController.abort();
        heatmapAbortController = new AbortController();
        const signal = heatmapAbortController.signal;

        try {
            // @ts-ignore
            const apiBase = import.meta.env.VITE_API_URL || 
                           (window.location.hostname === 'localhost' ? 'http://localhost:8000' : 'https://spellatlas-backend-production.fly.dev');
            
            let url = `${apiBase}/api/events/heatmap`;
            const params = new URLSearchParams();
            
            if (startStr && endStr) {
                params.append('start_date', startStr);
                params.append('end_date', endStr);
            }
            // Historical simulation logic removed as per new live-only architecture


            if (params.toString()) {
                url += `?${params.toString()}`;
            }

            const res = await fetch(url, { signal });
            if (res.ok) {
                const points = await res.json();
                // points is [[lat, lng, intensity], ...]
                
                // Convert to GeoJSON features
                const features = points.map((/** @type {any[]} */ p) => ({
                    type: 'Feature',
                    geometry: { type: 'Point', coordinates: [p[1], p[0]] }, // lng, lat
                    properties: { intensity: p[2] || 1 }
                }));
                
                heatFeatures = features;
                updateSource(SOURCES.heat, heatFeatures);
            }
        } catch (e) {
            // @ts-ignore
            if (e.name !== 'AbortError') {
                console.error("Failed to fetch heatmap data", e);
            }
        }
    }

    // Reactive Heatmap Update on Date/Scale Change
    // Removed legacy simulation watchers ($simulationDate, $timeScale, $isPlaying)
    // as the system is now Live-Only.

    /**
     * Main Animation Loop.
     * Processes buffered updates and renders them to the map.
     * @param {any} _timestamp
     */
    function processBatch(_timestamp) {
        requestAnimationFrame(processBatch);
        
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

            // Heatmap
            heatFeatures.push({
                type: 'Feature',
                geometry: { type: 'Point', coordinates: position },
                properties: { intensity: 1 }
            });

            // Lines (only if effects enabled)
            if (showEffects) {
                const now = Date.now();
                
                // Add new error to recent list
                recentErrors.push({ position, timestamp: now });
                
                // Create lines to nearby recent errors
                // Optimization: Don't check against ALL recent errors, maybe just last 50
                const recentSubset = recentErrors.slice(-50); 
                recentSubset.forEach((prev) => {
                    if (prev === recentErrors[recentErrors.length - 1]) return; // Skip self
                    
                    const dist = distanceMeters(position, prev.position);
                    if (dist > THREAT_MIN_DIST && dist < THREAT_MAX_DIST) {
                        lineFeatures.push({
                            type: 'Feature',
                            geometry: { type: 'LineString', coordinates: [prev.position, position] },
                            properties: { timestamp: now }
                        });
                    }
                });
            }

            // Visual Effects (Markers) - Only for the last item or specific conditions
            const isLast = index === lastItemIndex;
            
            if (showEffects && isLast) {
                updateVisualEffects(position, item, isError);
            }

            hasUpdates = true;
        });

        if (hasUpdates) {
            // Prune Arrays (Batch Pruning to maintain performance)
            if (pointFeatures.length > 500) pointFeatures = pointFeatures.slice(pointFeatures.length - 500);
            if (heatFeatures.length > 1000) heatFeatures = heatFeatures.slice(heatFeatures.length - 1000);
            
            // Clean up old lines
            const now = Date.now();
            lineFeatures = lineFeatures.filter(f => now - f.properties.timestamp < THREAT_WINDOW);
            if (lineFeatures.length > 500) lineFeatures = lineFeatures.slice(lineFeatures.length - 500);
            
            // Clean up recentErrors for next iteration
            recentErrors = recentErrors.filter(e => now - e.timestamp < THREAT_WINDOW);

            // Update Sources ONCE per frame
            updateSource(SOURCES.points, pointFeatures);
            updateSource(SOURCES.heat, heatFeatures);
            updateSource(SOURCES.lines, lineFeatures);
        }
    }

    /**
     * Renders transient visual effects (scan marker, pulse, popup) on the map.
     * @param {any} position
     * @param {any} item
     * @param {any} isError
     */
    function updateVisualEffects(position, item, isError) {
        // Scan Marker (Cyan Dot)
        if (!scanMarker) {
            const el = document.createElement('div');
            el.className = 'scan-marker';
            scanMarker = new maplibregl.Marker({ element: el })
                .setLngLat(position)
                .addTo(map);
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
                .addTo(map);

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
                offset: 25,
                // @ts-ignore
                autoPan: true,
                autoPanPadding: { top: 100, bottom: 100, left: 100, right: 100 }
            })
                .setLngLat(position)
                .setHTML(popupContent)
                .addTo(map);

            currentMarkerTimeout = setTimeout(() => {
                if (currentMarker) currentMarker.remove();
                if (currentPopup) currentPopup.remove();
                currentMarker = null;
                currentPopup = null;
            }, 5000);
        }
    }

    $: if (map && $mapMode && $mapMode !== currentStyle) {
        // @ts-ignore
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
        /** @type {any} */
        const rawItem = $latestNewsItem;
        // Normalize item structure to ensure map compatibility
        const item = {
            ...rawItem,
            country_code: rawItem.country_code || rawItem.country,
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
        if (map.getLayer(LAYERS.lines)) map.setLayoutProperty(LAYERS.lines, 'visibility', liveVisibility);

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
    /**
     * Resolves coordinates for a news event article.
     * @param {any} article
     */
    function resolveCoordinates(article) {
        let coords = null;
        if (article && article.country && article.country !== 'UNK') {
            coords = getCalibratedLngLat(article.country);
        }
        
        // Fallback for UNK or missing position to ensure visualization
        if (!coords) {
             // Assign a random position in the ocean/world map to ensure visibility of the event
             coords = [(Math.random() * 360) - 180, (Math.random() * 120) - 60];
        }
        return coords;
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
