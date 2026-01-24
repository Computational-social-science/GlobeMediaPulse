import { writable } from 'svelte/store';

/** 
 * Global Application State Management using Svelte Stores.
 * 
 * @module stores
 */

/** @type {import('svelte/store').Writable<any[]>} */
export const newsFeed = writable([]); // Store for the list of fetched news articles

// Playback Control Stores
export const isPaused = writable(false); // Controls whether the simulation/feed is paused
export const isPlaying = writable(false); // Controls the auto-play state of the simulation
export const playbackSpeed = writable(1.0); // Multiplier for playback speed

// User Interface Configuration Stores
export const mapMode = writable('vector'); // Map rendering mode: 'osm' (OpenStreetMap) or 'vector'
export const soundEnabled = writable(true); // Toggle for application sound effects
export const heatmapEnabled = writable(true); // Toggle for the heatmap visualization layer
export const is3DMode = writable(false); // Toggle for 3D map visualization

// Map View State
export const mapState = writable({
    selectedCountry: null, // Currently selected country code (ISO 3166-1 alpha-3)
    zoom: 2.5, // Current map zoom level
    center: [20, 0] // Current map center coordinates [lng, lat]
});

// Game/Simulation Statistics
export const gameStats = writable({
    totalItems: 0, // Total number of processed news items
    totalErrors: 0, // Total number of detected spelling/grammar errors
    totalWords: 0, // Total word count processed
    accuracy: 100 // Calculated accuracy percentage
});

// Simulation Time Control
export const simulationDate = writable(new Date()); // Current date in the simulation context
export const timeScale = writable('live'); // Time aggregation scale: 'live', 'year', or 'overview'
export const isConnected = writable(false); // WebSocket connection status indicator
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
    feed: { visible: true, minimized: false, maximized: false, position: { x: 20, y: 100 } },
    timeline: { visible: true, minimized: false, maximized: false, position: { x: 100, y: 100 } },
    countries: { visible: false, minimized: false, maximized: false, position: { x: 150, y: 150 } },
    corpus: { visible: false, minimized: false, maximized: false, position: { x: 300, y: 100 } },
    mediaAtlas: { visible: false, minimized: false, maximized: false, position: { x: 400, y: 150 } }
});

export const latestNewsItem = writable(null); // The most recently processed news item, used to trigger reactive updates

// Media Atlas Store
export const mediaSources = writable([]); // List of all media sources

// System Health Status
export const serviceStatus = writable({
    postgres: 'unknown', // Connection status of the PostgreSQL database
    redis: 'unknown' // Connection status of the Redis cache
});
