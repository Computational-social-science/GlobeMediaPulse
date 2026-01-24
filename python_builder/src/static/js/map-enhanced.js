const AppMap = {
    map: null,
    markers: [],
    countryLayers: {},
    heatmapLayer: null,
    heatmapData: [],
    mapReady: false,
    init: function() {
        if (typeof maplibregl === 'undefined') {
            return;
        }
        this.map = new maplibregl.Map({
            container: 'map',
            style: 'https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json',
            center: [0, 20],
            zoom: 2.5,
            minZoom: 1.5,
            maxZoom: 5.5,
            maxBounds: [[-180, -85], [180, 85]],
            attributionControl: false
        });
        this.map.setView = (center, zoom) => {
            if (Array.isArray(center)) {
                this.map.setCenter([center[1], center[0]]);
            }
            if (typeof zoom === 'number') {
                this.map.setZoom(zoom);
            }
            return this.map;
        };
        this.map.on('load', () => {
            this.mapReady = true;
            this.initializeHeatmapLayer();
            this.initializeCountryLayers();
            this.updateHeatmapPositions();
        });
        const updatePositions = () => this.updateHeatmapPositions();
        this.map.on('move', updatePositions);
        this.map.on('zoom', updatePositions);
        this.map.on('resize', updatePositions);
    },
    initializeHeatmapLayer: function() {
        const mapContainer = this.map && this.map.getContainer ? this.map.getContainer() : document.getElementById('map');
        if (!mapContainer) {
            return;
        }
        const heatmapContainer = document.createElement('div');
        heatmapContainer.id = 'heatmap-layer';
        heatmapContainer.className = 'heatmap-layer';
        mapContainer.appendChild(heatmapContainer);
        this.heatmapLayer = heatmapContainer;
    },
    initializeCountryLayers: function() {
        if (!this.mapReady) {
            return;
        }
        DATA.COUNTRIES.forEach(country => {
            const element = this.createCountryMarkerElement({
                radius: 3,
                color: 'rgba(0, 243, 255, 0.2)',
                fillColor: 'rgba(0, 243, 255, 0.1)',
                opacity: 0.2,
                weight: 1,
                className: 'country-base-marker'
            });
            const marker = new maplibregl.Marker({ element, anchor: 'center' })
                .setLngLat([country.lng, country.lat])
                .addTo(this.map);
            const tooltip = new maplibregl.Popup({
                closeButton: false,
                closeOnClick: false,
                offset: 8
            }).setHTML(`
                <div class="country-tooltip">
                    <strong>${country.name}</strong><br>
                    <span class="country-code">${country.code}</span><br>
                    <span class="country-region">${country.region}</span>
                </div>
            `);
            element.addEventListener('mouseenter', () => {
                tooltip.setLngLat([country.lng, country.lat]).addTo(this.map);
            });
            element.addEventListener('mouseleave', () => {
                tooltip.remove();
            });
            this.countryLayers[country.code] = {
                marker: marker,
                element: element,
                tooltip: tooltip,
                country: country,
                errorCount: 0,
                totalCount: 0,
                lastErrorTime: 0
            };
        });
    },
    createCountryMarkerElement: function(options) {
        const element = document.createElement('div');
        const size = options.radius * 2;
        element.style.width = `${size}px`;
        element.style.height = `${size}px`;
        element.style.borderRadius = '50%';
        element.style.background = options.fillColor;
        element.style.border = options.weight ? `${options.weight}px solid ${options.color}` : 'none';
        element.style.opacity = options.opacity;
        element.style.cursor = 'pointer';
        element.className = ['country-marker', options.className].filter(Boolean).join(' ');
        return element;
    },
    applyCountryMarkerStyle: function(layer, options) {
        const size = options.radius * 2;
        layer.element.style.width = `${size}px`;
        layer.element.style.height = `${size}px`;
        layer.element.style.background = options.fillColor;
        layer.element.style.border = options.weight ? `${options.weight}px solid ${options.color}` : 'none';
        layer.element.style.opacity = options.opacity;
        layer.element.className = ['country-marker', options.className].filter(Boolean).join(' ');
    },
    addHeatmapPoint: function(lat, lng, intensity, type = 'error') {
        if (!this.mapReady || !this.heatmapLayer) {
            return;
        }
        const point = document.createElement('div');
        point.className = `heatmap-point ${type}`;
        if (intensity < 0.3) {
            point.classList.add('low');
        } else if (intensity < 0.6) {
            point.classList.add('medium');
        } else if (intensity < 0.8) {
            point.classList.add('high');
        } else {
            point.classList.add('critical');
        }
        this.heatmapLayer.appendChild(point);
        const projected = this.map.project([lng, lat]);
        const size = point.offsetWidth || 0;
        point.style.left = `${projected.x - size / 2}px`;
        point.style.top = `${projected.y - size / 2}px`;
        this.heatmapData.push({
            element: point,
            lat: lat,
            lng: lng,
            intensity: intensity,
            timestamp: Date.now(),
            size: size
        });
        setTimeout(() => {
            if (point.parentNode) {
                point.parentNode.removeChild(point);
            }
        }, 5000);
    },
    updateHeatmapPositions: function() {
        if (!this.mapReady || !this.heatmapLayer) {
            return;
        }
        this.heatmapData.forEach(data => {
            const projected = this.map.project([data.lng, data.lat]);
            const size = data.size || data.element.offsetWidth || 0;
            data.element.style.left = `${projected.x - size / 2}px`;
            data.element.style.top = `${projected.y - size / 2}px`;
        });
    },
    updateHeatmapForCountry: function(countryCode, errorRate) {
        const layer = this.countryLayers[countryCode];
        if (layer) {
            const intensity = Math.min(errorRate / 50, 1);
            for (let i = 0; i < Math.floor(intensity * 5) + 1; i++) {
                const offsetLat = (Math.random() - 0.5) * 2;
                const offsetLng = (Math.random() - 0.5) * 2;
                this.addHeatmapPoint(
                    layer.country.lat + offsetLat,
                    layer.country.lng + offsetLng,
                    intensity,
                    'error'
                );
            }
            this.updateCountryMarkerAppearance(layer, errorRate);
        }
    },
    updateCountryMarkerAppearance: function(layer, errorRate) {
        if (errorRate > 20) {
            this.applyCountryMarkerStyle(layer, {
                radius: 8,
                color: '#FF0000',
                fillColor: '#FF4500',
                opacity: 0.9,
                weight: 3,
                className: 'country-critical-marker pulse-critical'
            });
        } else if (errorRate > 10) {
            this.applyCountryMarkerStyle(layer, {
                radius: 6,
                color: '#FF4500',
                fillColor: '#FF8C00',
                opacity: 0.8,
                weight: 2,
                className: 'country-high-marker pulse-high'
            });
        } else if (errorRate > 5) {
            this.applyCountryMarkerStyle(layer, {
                radius: 5,
                color: '#FFA500',
                fillColor: '#FFD700',
                opacity: 0.6,
                weight: 2,
                className: 'country-medium-marker pulse-medium'
            });
        } else if (errorRate > 1) {
            this.applyCountryMarkerStyle(layer, {
                radius: 4,
                color: '#00F3FF',
                fillColor: '#40E0D0',
                opacity: 0.4,
                weight: 1,
                className: 'country-low-marker pulse-low'
            });
        } else {
            this.applyCountryMarkerStyle(layer, {
                radius: 3,
                color: 'rgba(0, 243, 255, 0.2)',
                fillColor: 'rgba(0, 243, 255, 0.1)',
                opacity: 0.2,
                weight: 1,
                className: 'country-base-marker'
            });
        }
    },
    createEventMarkerElement: function(radius, color, className, hasError) {
        const element = document.createElement('div');
        const size = radius * 2;
        element.style.width = `${size}px`;
        element.style.height = `${size}px`;
        element.style.borderRadius = '50%';
        element.style.background = color;
        element.style.opacity = hasError ? '0.85' : '0.5';
        element.style.boxShadow = `0 0 ${hasError ? 12 : 6}px ${color}`;
        element.className = ['event-marker', className].filter(Boolean).join(' ');
        return element;
    },
    addMarker: function(item) {
        if (!this.mapReady) {
            return;
        }
        if (item.has_error) {
            this.addHeatmapPoint(
                item.coordinates.lat,
                item.coordinates.lng,
                0.8,
                'error'
            );
            const countryCode = item.country_name.substring(0, 3).toUpperCase();
            if (this.countryLayers[countryCode]) {
                this.countryLayers[countryCode].errorCount++;
                this.countryLayers[countryCode].totalCount++;
                this.countryLayers[countryCode].lastErrorTime = Date.now();
                const errorRate = (this.countryLayers[countryCode].errorCount / this.countryLayers[countryCode].totalCount) * 100;
                this.updateHeatmapForCountry(countryCode, errorRate);
            }
        } else {
            this.addHeatmapPoint(
                item.coordinates.lat,
                item.coordinates.lng,
                0.2,
                'valid'
            );
        }
        const color = item.has_error ? '#FF4500' : '#00F3FF';
        const radius = item.has_error ? 8 : 4;
        const className = item.has_error ? 'pulse-marker' : '';
        const markerElement = this.createEventMarkerElement(radius, color, className, item.has_error);
        const marker = new maplibregl.Marker({ element: markerElement, anchor: 'center' })
            .setLngLat([item.coordinates.lng, item.coordinates.lat])
            .addTo(this.map);
        const popupContent = `
            <div class="popup-content">
                <div class="popup-header">
                    <span class="popup-country">${item.country_name}</span>
                    <span class="popup-timestamp">${item.timestamp.split('T')[1].split('.')[0]}</span>
                </div>
                <div class="popup-headline">"${item.headline}"</div>
                ${item.has_error ? `
                    <div class="popup-error-section">
                        <div class="popup-error">
                            <span class="error-label">DETECTED ERROR:</span>
                            <span class="error-word">${item.error_detail.error_word}</span>
                        </div>
                        <div class="popup-correction">
                            <span class="correction-label">CORRECTED TO:</span>
                            <span class="corrected-word">${item.error_detail.corrected_word}</span>
                        </div>
                        <div class="popup-analysis">
                            <span class="analysis-type">ERROR TYPE:</span>
                            <span class="analysis-result">Typographical Error</span>
                        </div>
                    </div>
                ` : `
                    <div class="popup-valid">
                        <span class="valid-indicator">✓</span>
                        <span class="valid-text">No spelling errors detected</span>
                    </div>
                `}
                <div class="popup-metrics">
                    <span class="metric">Confidence: ${Math.floor(Math.random() * 20 + 80)}%</span>
                </div>
            </div>
        `;
        const popup = new maplibregl.Popup({
            closeButton: false,
            closeOnClick: false,
            offset: 16
        }).setHTML(popupContent);
        marker.setPopup(popup);
        if (item.has_error && Math.random() > 0.7) {
            popup.setLngLat([item.coordinates.lng, item.coordinates.lat]).addTo(this.map);
            setTimeout(() => popup.remove(), 3000);
        }
        this.markers.push({
            instance: marker,
            timestamp: Date.now(),
            country: item.country_name
        });
        this.cleanupHeatmap();
    },
    clearHeatmap: function() {
        if (this.heatmapLayer) {
            this.heatmapLayer.innerHTML = '';
        }
        this.heatmapData = [];
    },
    cleanupHeatmap: function() {
        const now = Date.now();
        const maxAge = 10000;
        this.heatmapData = this.heatmapData.filter(data => {
            if (now - data.timestamp > maxAge) {
                if (data.element.parentNode) {
                    data.element.parentNode.removeChild(data.element);
                }
                return false;
            }
            return true;
        });
        if (this.markers.length > 50) {
            const toRemove = this.markers.splice(0, this.markers.length - 50);
            toRemove.forEach(m => {
                if (m.instance && m.instance.remove) {
                    m.instance.remove();
                }
            });
        }
    },
    getRegionalErrorRates: function() {
        const regions = {};
        Object.values(this.countryLayers).forEach(layer => {
            if (!regions[layer.country.region]) {
                regions[layer.country.region] = {
                    totalErrors: 0,
                    totalItems: 0,
                    countries: 0,
                    avgErrorRate: 0
                };
            }
            regions[layer.country.region].totalErrors += layer.errorCount;
            regions[layer.country.region].totalItems += layer.totalCount;
            regions[layer.country.region].countries++;
        });
        Object.keys(regions).forEach(region => {
            const r = regions[region];
            r.avgErrorRate = r.totalItems > 0 ? (r.totalErrors / r.totalItems * 100).toFixed(1) : 0;
        });
        return regions;
    },
    getBehavioralFingerprintData: function() {
        const fingerprint = {
            geographicDistribution: {},
            temporalPatterns: {},
            errorIntensity: {},
            hotspots: []
        };
        Object.values(this.countryLayers).forEach(layer => {
            if (layer.errorCount > 0) {
                fingerprint.geographicDistribution[layer.country.code] = {
                    name: layer.country.name,
                    errorCount: layer.errorCount,
                    errorRate: (layer.errorCount / layer.totalCount * 100).toFixed(1),
                    intensity: this.calculateIntensity(layer.errorCount, layer.lastErrorTime)
                };
            }
        });
        fingerprint.hotspots = Object.values(this.countryLayers)
            .filter(layer => layer.totalCount > 0)
            .map(layer => ({
                country: layer.country.name,
                code: layer.country.code,
                errorRate: (layer.errorCount / layer.totalCount * 100),
                errorCount: layer.errorCount,
                coordinates: [layer.country.lat, layer.country.lng]
            }))
            .sort((a, b) => b.errorRate - a.errorRate)
            .slice(0, 10);
        return fingerprint;
    },
    calculateIntensity: function(errorCount, lastErrorTime) {
        const timeDecay = Math.exp(-(Date.now() - lastErrorTime) / (24 * 60 * 60 * 1000));
        const countFactor = Math.log(errorCount + 1) / Math.log(10);
        return Math.min((countFactor * timeDecay * 100).toFixed(1), 100);
    },
    getHeatmapIntensityForTimeline: function(dayData) {
        const intensityData = [];
        Object.values(this.countryLayers).forEach(layer => {
            if (layer.errorCount > 0) {
                const intensity = this.calculateIntensity(layer.errorCount, layer.lastErrorTime);
                if (intensity > 10) {
                    intensityData.push({
                        lat: layer.country.lat,
                        lng: layer.country.lng,
                        intensity: intensity,
                        country: layer.country.name
                    });
                }
            }
        });
        return intensityData;
    }
};
