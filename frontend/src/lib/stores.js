import { writable } from 'svelte/store';

/** 
 * Global Application State Management using Svelte Stores.
 * 
 * @module stores
 */

/** @type {import('svelte/store').Writable<any[]>} */
export const newsFeed = writable([]); // Store for the list of fetched news articles

// User Interface Configuration Stores
export const mapMode = writable('vector'); // Map rendering mode: 'osm' (OpenStreetMap) or 'vector'
export const soundEnabled = writable(true); // Toggle for application sound effects
export const audioEnabled = soundEnabled; // Alias for SoundManager compatibility
export const audioVolume = writable(0.5); // Master volume for sound effects
export const heatmapEnabled = writable(true); // Toggle for the heatmap visualization layer

// Map View State
export const mapState = writable({
    selectedCountry: null, // Currently selected country code (ISO 3166-1 alpha-3)
    zoom: 2.5, // Current map zoom level
    center: [20, 0] // Current map center coordinates [lng, lat]
});

// Simulation Time Control
export const isConnected = writable(false); // WebSocket connection status indicator
export const systemStatus = writable('OFFLINE'); // Global System Status (ONLINE, OFFLINE, DEGRADED)
export const newsEvents = writable(null); // Store for real-time news events (for Data-Flow visualization)
/** @type {import('svelte/store').Writable<any[]>} */
export const systemLogs = writable([]); // Store for real-time system logs

export const countrySourceFilter = writable('all');

// Restored Functionality Stores
export const countryStats = writable({}); // Aggregated statistics per country. Key: Country Code, Value: Stats Object
/** @type {import('svelte/store').Writable<any[]>} */
export const timelineData = writable([]); // Historical data snapshots for the timeline visualization

/** 
 * Window Management State.
 * Controls the visibility, position, and state (minimized/maximized) of floating UI windows.
 * @type {import('svelte/store').Writable<Record<string, any>>} 
 */
export const windowState = writable({
    brain: { visible: true, minimized: false, maximized: false, position: { x: 20, y: 100 } },
    systemMonitor: { visible: false, minimized: false, maximized: false, position: { x: 100, y: 100 } }
});

export const latestNewsItem = writable(null); // The most recently processed news item, used to trigger reactive updates

// Media Atlas Store
export const mediaSources = writable([]); // List of all media sources

// System Health Status
export const serviceStatus = writable({
    postgres: 'unknown', // Connection status of the PostgreSQL database
    redis: 'unknown' // Connection status of the Redis cache
});
export const backendThreadStatus = writable({
    crawler: 'unknown',
    analyzer: 'unknown',
    cleanup: 'unknown'
});
