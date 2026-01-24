<script>
    import { onMount, onDestroy } from 'svelte';
    import { newsFeed, isPaused, isPlaying, playbackSpeed, timeScale, latestNewsItem, gameStats, countryStats, timelineData, soundEnabled, simulationDate, isConnected, countrySourceFilter } from '../stores.js';
    
    /** @type {WebSocket} WebSocket connection instance */
    let socket;
    
    // Audio Context for Sonar Sound Effects
    /** @type {AudioContext} */
    let audioCtx;
    
    /** @type {any} Interval ID for data snapshots */
    let snapshotId;
    /** @type {any} Interval ID for batch processing */
    let batchInterval;
    /** @type {any[]} Buffer for incoming WebSocket messages */
    let messageBuffer = [];

    /**
     * Plays a synthetic sonar ping sound using the Web Audio API.
     * Used when an error event is detected.
     */
    function playSonarSound() {
        if (!audioCtx) {
            // @ts-ignore
            audioCtx = new (window.AudioContext || window.webkitAudioContext)();
        }
        
        // Resume context if suspended (browser autoplay policy)
        if (audioCtx.state === 'suspended') {
            audioCtx.resume();
        }

        const oscillator = audioCtx.createOscillator();
        const gainNode = audioCtx.createGain();

        // Sound Profile: Passive Sonar Ping (Sine wave, high pitch, quick decay)
        oscillator.type = 'sine';
        oscillator.frequency.setValueAtTime(880, audioCtx.currentTime); // Start at A5 (880Hz)
        oscillator.frequency.exponentialRampToValueAtTime(440, audioCtx.currentTime + 0.2); // Drop to A4 (440Hz)

        gainNode.gain.setValueAtTime(0.1, audioCtx.currentTime); // Low volume
        gainNode.gain.exponentialRampToValueAtTime(0.001, audioCtx.currentTime + 0.5); // Fade out

        oscillator.connect(gainNode);
        gainNode.connect(audioCtx.destination);

        oscillator.start();
        oscillator.stop(audioCtx.currentTime + 0.5);
    }

    /**
     * Establishes a WebSocket connection to the backend simulator.
     * Handles incoming news items and connection state.
     */
    function connectWebSocket() {
        // Robust fallback: If env var is missing, guess based on environment
        // @ts-ignore
        const wsUrl = import.meta.env.VITE_WS_URL || 
                      (window.location.hostname === 'localhost' ? 'ws://localhost:8000' : 'wss://globemediapulse-backend-production.fly.dev');
        
        console.log('Connecting to WebSocket:', `${wsUrl}/ws`);
        socket = new WebSocket(`${wsUrl}/ws`);

        socket.onopen = () => {
            console.log('Connected to backend simulator');
            isConnected.set(true);
        };

        socket.onmessage = (event) => {
            if ($isPaused) return; // Skip updates if paused

            try {
                const payload = JSON.parse(event.data);
                
                // Handle different message types
                if (payload.type === 'heartbeat' || payload.type === 'info') return;

                if (payload.type === 'news_item') {
                    // Parse Timestamp (Handle GDELT formats or ISO)
                    let timestamp = Date.now();
                    if (payload.timestamp) {
                        const parsed = new Date(payload.timestamp);
                        if (!isNaN(parsed.getTime())) {
                            timestamp = parsed.getTime();
                        }
                    }

                    const payloadSource = payload.country_source || 'unknown';
                    if ($countrySourceFilter !== 'all' && payloadSource !== $countrySourceFilter) {
                        return;
                    }

                    const newItem = {
                        ...payload,
                        id: timestamp + Math.random(), // Unique ID based on event time + random
                        timestamp: timestamp, // Event timestamp
                        country_name: payload.country_name || payload.country,
                        country_code: payload.country_code || payload.country,
                        coordinates: payload.coordinates,
                        has_error: payload.has_error || (payload.errors && payload.errors.length > 0),
                        headline: payload.headline || payload.title,
                        country_source: payloadSource,
                        error_details: payload.error_details || (payload.errors && payload.errors.length > 0 ? payload.errors[0] : null)
                    };
                    messageBuffer.push(newItem);
                }
            } catch (e) {
                console.error('Error processing message:', e);
            }
        };

        socket.onclose = () => {
            console.log('Disconnected from backend. Reconnecting in 3s...');
            isConnected.set(false);
            setTimeout(connectWebSocket, 3000);
        };
        
        socket.onerror = (/** @type {Event} */ err) => {
            console.error('WebSocket error:', err);
            isConnected.set(false);
            socket.close();
        };
    }

    /** @type {any} Interval ID for syncing stats */
    let syncInterval;
    /** @type {any} Interval ID for simulation auto-play */
    let playInterval;

    // --- Auto-Play Logic ---
    // Reactively starts/stops the simulation clock based on `isPlaying` store
    $: {
        if (playInterval) clearInterval(playInterval);
        
        if ($isPlaying) {
            playInterval = setInterval(() => {
                const d = new Date($simulationDate);
                const scale = $timeScale;
                const now = new Date();

                if (scale === 'overview') {
                    // Overview Mode: 1 month per tick
                    d.setMonth(d.getMonth() + 1);
                    if (d.getFullYear() > now.getFullYear()) {
                         d.setFullYear(now.getFullYear());
                         d.setMonth(now.getMonth());
                         $isPlaying = false;
                    }
                } else {
                    // Standard Mode: 1 day per tick
                    d.setDate(d.getDate() + 1);
                    if (scale === 'year') {
                         // Loop within the year for continuous observation
                         if (d.getFullYear() !== $simulationDate.getFullYear()) {
                             d.setFullYear($simulationDate.getFullYear());
                             d.setMonth(0);
                             d.setDate(1);
                         }
                    } else if (scale === 'live') {
                        if (d > now) {
                             $isPlaying = false;
                             return;
                        }
                    }
                }
                simulationDate.set(d);
            }, 500 / $playbackSpeed);
        }
    }

    onMount(() => {
        connectWebSocket();

        // Robust fallback: If env var is missing, guess based on environment
        // @ts-ignore
        const apiBase = import.meta.env.VITE_API_URL || 
                        (window.location.hostname === 'localhost' ? 'http://localhost:8000' : 'https://globemediapulse-backend-production.fly.dev');

        // Periodic Sync with Backend Stats (to ensure Total Words count is accurate)
        syncInterval = setInterval(async () => {
            try {
                const res = await fetch(`${apiBase}/api/stats`);
                if (res.ok) {
                    const data = await res.json();
                    gameStats.update(s => ({
                        ...s,
                        totalErrors: Math.max(s.totalErrors, data.total_errors || 0),
                        totalWords: data.total_words || 0
                    }));
                }
            } catch (e) {
                console.warn("Failed to sync stats", e);
            }
        }, 5000);

        // Snapshot Loop (Client-side aggregation for Timeline)
        snapshotId = setInterval(() => {
            if (!$isPaused) {
                /** @type {any} */
                let currentStats;
                const unsub = gameStats.subscribe(v => currentStats = v);
                unsub();
                
                timelineData.update(data => {
                    /** @type {any} */
                    const newData = [
                        ...data,
                        {
                            day: data.length + 1,
                            totalEvents: currentStats.totalItems,
                            errorEvents: currentStats.totalErrors
                        }
                    ].slice(-30); // Keep last 30 snapshots
                    return newData;
                });
            }
        }, 10000); // Snapshot every 10 seconds

        // Batch Processing Loop (Consumes Message Buffer)
        batchInterval = setInterval(() => {
            if ($isPaused || messageBuffer.length === 0) return;

            const batch = messageBuffer.splice(0, 50); // Process max 50 items per tick
            
            // 1. Update News Feed
            const newItems = [...batch].reverse();
            newsFeed.update(current => [...newItems, ...current].slice(0, 50));

            // Update Simulation Date (Only if NOT playing manually, to follow the stream)
            if (batch.length > 0 && !$isPlaying) {
                const latestTimestamp = batch[batch.length - 1].timestamp;
                if (latestTimestamp) {
                    simulationDate.set(new Date(latestTimestamp));
                }
            }

            // 2. Trigger Map Update (Notify MapContainer)
            batch.forEach(item => latestNewsItem.set(item));

            // 3. Play Sound Effect (if enabled and error present)
            if ($soundEnabled && batch.some(i => i.has_error)) {
                playSonarSound();
            }
        }, 50); // High frequency loop for smooth updates
    });

    onDestroy(() => {
        if (socket) socket.close();
        if (snapshotId) clearInterval(snapshotId);
        if (batchInterval) clearInterval(batchInterval);
        if (syncInterval) clearInterval(syncInterval);
        if (playInterval) clearInterval(playInterval);
    });
</script>

<!-- Headless Controller Component (Logic Only) -->
<slot></slot>
