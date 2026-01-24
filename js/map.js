const AppMap = {
    map: null,
    markers: [],
    
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
    },

    addMarker: function(item) {
        if (!this.map) {
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

        // Popup Content
        let popupContent = `
            <div class="popup-content">
                <span class="popup-country">${item.country_name}</span>
                <div class="popup-headline">"${item.headline}"</div>
                ${item.has_error ? `
                    <div class="popup-error">
                        ⚠ ${item.error_detail.error_word} &rarr; ${item.error_detail.corrected_word}
                    </div>
                ` : ''}
            </div>
        `;

        const popup = new maplibregl.Popup({
            closeButton: false,
            closeOnClick: false,
            offset: 12
        }).setHTML(popupContent);
        marker.setPopup(popup);
        
        // Auto open popup for errors sometimes
        if (item.has_error && Math.random() > 0.7) {
            popup.setLngLat([lng, lat]).addTo(this.map);
            setTimeout(() => popup.remove(), 3000);
        }

        this.markers.push({
            instance: marker,
            timestamp: Date.now()
        });

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
    }
};
