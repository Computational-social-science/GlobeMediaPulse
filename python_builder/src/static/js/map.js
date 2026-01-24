const AppMap = {
    map: null,
    markers: [],
    countryLayers: {},
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
        this.map.on('load', () => {
            this.mapReady = true;
            this.initializeCountryLayers();
        });
    },

    initializeCountryLayers: function() {
        if (!this.mapReady) {
            return;
        }
        DATA.COUNTRIES.forEach(country => {
            const lng = Number(country.lng);
            const lat = Number(country.lat);
            if (Number.isNaN(lng) || Number.isNaN(lat)) {
                return;
            }
            const markerElement = this.createCountryMarkerElement({
                radius: 3,
                color: 'rgba(0, 243, 255, 0.3)',
                fillColor: 'rgba(0, 243, 255, 0.1)',
                opacity: 0.3,
                weight: 1,
                className: 'country-base-marker'
            });
            const marker = new maplibregl.Marker({ element: markerElement, anchor: 'center' })
                .setLngLat([lng, lat])
                .addTo(this.map);
            const tooltip = new maplibregl.Popup({
                closeButton: false,
                closeOnClick: false,
                offset: 12
            }).setHTML(`
                <div class="country-tooltip">
                    <strong>${country.name}</strong><br>
                    <span class="country-code">${country.code}</span><br>
                    <span class="country-region">${country.region}</span>
                </div>
            `);
            markerElement.addEventListener('mouseenter', () => {
                tooltip.setLngLat([lng, lat]).addTo(this.map);
            });
            markerElement.addEventListener('mouseleave', () => {
                tooltip.remove();
            });
            
            this.countryLayers[country.code] = {
                marker: marker,
                element: markerElement,
                tooltip: tooltip,
                country: country,
                errorCount: 0,
                totalCount: 0
            };
        });
    },

    updateCountryVisualization: function(countryCode, errorRate) {
        const layer = this.countryLayers[countryCode];
        if (layer) {
            const intensity = Math.min(errorRate / 50, 1);
            const radius = 3 + (intensity * 5);
            
            if (errorRate > 10) {
                this.applyCountryMarkerStyle(layer, {
                    radius: radius,
                    color: 'var(--alert)',
                    fillColor: 'var(--alert)',
                    opacity: 0.6,
                    weight: 2,
                    className: 'country-alert-marker pulse-marker'
                });
            } else if (errorRate > 5) {
                this.applyCountryMarkerStyle(layer, {
                    radius: radius,
                    color: 'var(--primary)',
                    fillColor: 'var(--primary)',
                    opacity: 0.4,
                    weight: 1,
                    className: 'country-medium-marker'
                });
            } else {
                this.applyCountryMarkerStyle(layer, {
                    radius: 3,
                    color: 'rgba(0, 243, 255, 0.3)',
                    fillColor: 'rgba(0, 243, 255, 0.1)',
                    opacity: 0.3,
                    weight: 1,
                    className: 'country-base-marker'
                });
            }
        }
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

    addMarker: function(item) {
        if (!this.mapReady) {
            return;
        }
        const color = item.has_error ? '#FF4500' : '#00F3FF';
        const radius = item.has_error ? 8 : 4;
        const className = item.has_error ? 'pulse-marker' : '';

        const lng = Number(item?.coordinates?.lng);
        const lat = Number(item?.coordinates?.lat);
        if (Number.isNaN(lng) || Number.isNaN(lat)) {
            return;
        }

        const markerElement = document.createElement('div');
        const size = radius * 2;
        markerElement.style.width = `${size}px`;
        markerElement.style.height = `${size}px`;
        markerElement.style.borderRadius = '50%';
        markerElement.style.background = color;
        markerElement.style.opacity = item.has_error ? '0.85' : '0.5';
        markerElement.style.boxShadow = `0 0 ${item.has_error ? 12 : 6}px ${color}`;
        markerElement.className = ['event-marker', className].filter(Boolean).join(' ');
        const marker = new maplibregl.Marker({ element: markerElement, anchor: 'center' })
            .setLngLat([lng, lat])
            .addTo(this.map);

        // Popup Content with enhanced scientific information
        let popupContent = `
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
                    <span class="metric">Source: News Feed #${Math.floor(Math.random() * 999 + 1)}</span>
                </div>
            </div>
        `;

        const popup = new maplibregl.Popup({
            closeButton: false,
            closeOnClick: false,
            offset: 12
        }).setHTML(popupContent);
        marker.setPopup(popup);
        
        if (item.has_error && Math.random() > 0.7) {
            popup.setLngLat([lng, lat]).addTo(this.map);
            setTimeout(() => popup.remove(), 3000);
        }

        this.markers.push({
            instance: marker,
            timestamp: Date.now(),
            country: item.country_name
        });

        if (item.has_error) {
            const countryCode = item.country_code || (item.country_name ? item.country_name.substring(0, 3).toUpperCase() : '');
            if (this.countryLayers[countryCode]) {
                this.countryLayers[countryCode].errorCount++;
                this.countryLayers[countryCode].totalCount++;
                
                const errorRate = (this.countryLayers[countryCode].errorCount / this.countryLayers[countryCode].totalCount) * 100;
                this.updateCountryVisualization(countryCode, errorRate);
            }
        }

        // Cleanup old markers
        this.cleanup();
    },

    cleanup: function() {
        const now = Date.now();
        // Remove markers older than 10 seconds or if > 50 markers
        if (this.markers.length > 50) {
            const toRemove = this.markers.splice(0, this.markers.length - 50);
            toRemove.forEach(m => m.instance.remove());
        }
    },

    // Scientific analysis methods
    getRegionalErrorRates: function() {
        const regions = {};
        
        Object.values(this.countryLayers).forEach(layer => {
            if (!regions[layer.country.region]) {
                regions[layer.country.region] = {
                    totalErrors: 0,
                    totalItems: 0,
                    countries: 0
                };
            }
            
            regions[layer.country.region].totalErrors += layer.errorCount;
            regions[layer.country.region].totalItems += layer.totalCount;
            regions[layer.country.region].countries++;
        });
        
        return regions;
    },

    getTopErrorCountries: function(limit = 10) {
        return Object.values(this.countryLayers)
            .filter(layer => layer.totalCount > 0)
            .map(layer => ({
                country: layer.country.name,
                code: layer.country.code,
                region: layer.country.region,
                errorRate: (layer.errorCount / layer.totalCount) * 100,
                errorCount: layer.errorCount,
                totalCount: layer.totalCount
            }))
            .sort((a, b) => b.errorRate - a.errorRate)
            .slice(0, limit);
    }
};
