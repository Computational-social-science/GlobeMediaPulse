const App = {
    state: {
        paused: false,
        speed: 1.0,
        totalItems: 0,
        totalErrors: 0,
        lastTime: 0,
        intervalId: null,
        keystrokes: [],
        dynamicIslandTimeout: null,
        windows: {}, // Track window states
        countryStats: {}, // Track country-specific statistics
        currentRegionFilter: 'all',
        timeline: {
            data: [],
            currentDay: 0,
            isPlaying: false,
            playbackSpeed: 1.0,
            maxDays: 30
        },
        heatmap: {
            intensityData: [],
            maxIntensity: 100,
            decayRate: 0.95
        }
    },

    init: function() {
        console.log("System Initializing...");
        
        // --- Auto-Debug / Self-Check ---
        try {
            if (typeof AppMap === 'undefined') throw new Error("AppMap module missing");
            if (typeof Simulator === 'undefined') throw new Error("Simulator module missing");
            if (typeof DATA === 'undefined') throw new Error("DATA module missing");
            if (!document.getElementById('map')) throw new Error("Map container missing");
            if (!document.getElementById('dynamic-island')) throw new Error("Dynamic Island missing");
            console.log("Self-Check: PASSED");
        } catch (e) {
            console.error("Self-Check FAILED:", e);
            alert("SYSTEM ERROR: " + e.message);
            return;
        }
        // -------------------------------

        this.updateClock();
        setInterval(() => this.updateClock(), 1000);
        
        AppMap.init();
        this.registerWindows();
        this.bindEvents();
        this.makeWindowsDraggable();
        this.initializeCountryStats();
        this.initializeTimeline();
        this.startGameLoop();
        
        this.showDynamicMessage("SYSTEM INITIALIZED", "success");
        console.log("System Online.");
    },

    initializeTimeline: function() {
        this.createTimelineWindow();
        this.generateInitialTimelineData();
        
        // Take daily snapshots
        setInterval(() => {
            this.takeDailySnapshot();
        }, 60000); // Every minute (for demo purposes)
    },

    createTimelineWindow: function() {
        const timelineWindow = document.createElement('div');
        timelineWindow.id = 'win-timeline';
        timelineWindow.className = 'glass-window timeline-window';
        timelineWindow.dataset.title = 'TIMELINE';
        timelineWindow.style.cssText = 'right: 20px; top: 80px; width: 700px; height: 400px; display: none;';
        
        timelineWindow.innerHTML = `
            <div class="window-header">
                <div class="win-title-group">
                    <span class="win-icon">⏱</span>
                    <span class="win-title">TEMPORAL_ANALYSIS</span>
                </div>
                <div class="win-controls">
                    <button class="win-btn minimize" title="Minimize">_</button>
                    <button class="win-btn maximize" title="Maximize">□</button>
                </div>
            </div>
            <div class="window-body">
                <div class="timeline-controls">
                    <div class="timeline-playback">
                        <button id="btn-timeline-prev" class="timeline-btn" title="Previous Day">◀</button>
                        <button id="btn-timeline-play" class="timeline-btn" title="Play/Pause">▶</button>
                        <button id="btn-timeline-next" class="timeline-btn" title="Next Day">▶</button>
                    </div>
                    <input type="range" id="timeline-slider" class="timeline-slider" min="0" max="29" value="0">
                    <div class="timeline-speed">
                        <span class="speed-label">SPEED</span>
                        <div class="speed-control">
                            <button id="btn-timeline-slower" class="speed-btn" title="Slower">-</button>
                            <span class="speed-display" id="timeline-speed-display">1.0x</span>
                            <button id="btn-timeline-faster" class="speed-btn" title="Faster">+</button>
                        </div>
                    </div>
                </div>
                <div class="timeline-chart">
                    <canvas id="timeline-canvas" class="timeline-canvas" width="680" height="280"></canvas>
                    <div class="timeline-info">
                        <div class="timeline-day">Day 0</div>
                        <div class="timeline-stats">
                            <div class="timeline-stat">
                                <span class="stat-label">Total Events</span>
                                <span class="stat-value" id="timeline-total">0</span>
                            </div>
                            <div class="timeline-stat">
                                <span class="stat-label">Error Rate</span>
                                <span class="stat-value" id="timeline-error-rate">0%</span>
                            </div>
                            <div class="timeline-stat">
                                <span class="stat-label">Countries</span>
                                <span class="stat-value" id="timeline-countries">0</span>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
            <div class="window-footer">
                <span class="status-light online"></span> TIMELINE ACTIVE
            </div>
        `;
        
        document.querySelector('.window-layer').appendChild(timelineWindow);
    },

    generateInitialTimelineData: function() {
        // Generate 30 days of synthetic data for demonstration
        for (let day = 0; day < 30; day++) {
            const dayData = {
                day: day,
                date: new Date(Date.now() - (29 - day) * 24 * 60 * 60 * 1000),
                totalEvents: Math.floor(Math.random() * 500) + 200,
                errorEvents: Math.floor(Math.random() * 50) + 10,
                countries: this.generateDailyCountryData(),
                errorRate: 0,
                heatmapData: this.generateDailyHeatmapData()
            };
            dayData.errorRate = ((dayData.errorEvents / dayData.totalEvents) * 100).toFixed(1);
            this.state.timeline.data.push(dayData);
        }
        
        this.updateTimelineDisplay();
    },

    generateDailyCountryData: function() {
        const countries = {};
        DATA.COUNTRIES.slice(0, 15).forEach(country => {
            countries[country.code] = {
                name: country.name,
                events: Math.floor(Math.random() * 20) + 5,
                errors: Math.floor(Math.random() * 5) + 1,
                region: country.region
            };
        });
        return countries;
    },

    generateDailyHeatmapData: function() {
        const heatmapData = [];
        // Generate heatmap points for behavioral fingerprinting
        for (let i = 0; i < 20; i++) {
            const country = DATA.COUNTRIES[Math.floor(Math.random() * DATA.COUNTRIES.length)];
            const intensity = Math.random();
            heatmapData.push({
                lat: country.lat + (Math.random() - 0.5) * 5,
                lng: country.lng + (Math.random() - 0.5) * 5,
                intensity: intensity,
                type: intensity > 0.7 ? 'error' : 'valid',
                country: country.name
            });
        }
        return heatmapData;
    },

    takeDailySnapshot: function() {
        const today = new Date();
        const snapshot = {
            day: this.state.timeline.data.length,
            date: today,
            totalEvents: this.state.totalItems,
            errorEvents: this.state.totalErrors,
            countries: JSON.parse(JSON.stringify(this.state.countryStats)),
            errorRate: this.state.totalItems > 0 ? ((this.state.totalErrors / this.state.totalItems) * 100).toFixed(1) : 0,
            heatmapData: this.generateCurrentHeatmapData()
        };
        
        this.state.timeline.data.push(snapshot);
        
        // Keep only last 30 days
        if (this.state.timeline.data.length > this.state.timeline.maxDays) {
            this.state.timeline.data.shift();
        }
        
        this.showDynamicMessage("DAILY SNAPSHOT CAPTURED", "success");
        this.updateTimelineDisplay();
    },

    generateCurrentHeatmapData: function() {
        const heatmapData = [];
        const behavioralData = AppMap.getBehavioralFingerprintData();
        
        // Convert behavioral fingerprint data to heatmap format
        behavioralData.hotspots.forEach(hotspot => {
            heatmapData.push({
                lat: hotspot.coordinates[0],
                lng: hotspot.coordinates[1],
                intensity: hotspot.errorRate / 100,
                type: 'error',
                country: hotspot.country
            });
        });
        
        return heatmapData;
    },

    updateTimelineDisplay: function() {
        const canvas = document.getElementById('timeline-canvas');
        if (!canvas) return;
        
        const ctx = canvas.getContext('2d');
        const data = this.state.timeline.data;
        
        if (data.length === 0) return;
        
        // Clear canvas
        ctx.clearRect(0, 0, canvas.width, canvas.height);
        
        // Draw timeline chart
        const maxEvents = Math.max(...data.map(d => d.totalEvents));
        const barWidth = canvas.width / data.length;
        
        data.forEach((day, index) => {
            const x = index * barWidth;
            const height = (day.totalEvents / maxEvents) * (canvas.height - 40);
            const y = canvas.height - height - 20;
            
            // Draw total events bar
            ctx.fillStyle = index === this.state.timeline.currentDay ? '#00F3FF' : '#0066CC';
            ctx.fillRect(x + 2, y, barWidth - 4, height);
            
            // Draw error portion
            const errorHeight = (day.errorEvents / maxEvents) * (canvas.height - 40);
            ctx.fillStyle = '#FF4500';
            ctx.fillRect(x + 2, canvas.height - errorHeight - 20, barWidth - 4, errorHeight * 0.3);
            
            // Highlight current day
            if (index === this.state.timeline.currentDay) {
                ctx.strokeStyle = '#00F3FF';
                ctx.lineWidth = 2;
                ctx.strokeRect(x, 10, barWidth, canvas.height - 20);
            }
        });
        
        // Update stats
        const currentDay = data[this.state.timeline.currentDay];
        if (currentDay) {
            document.getElementById('timeline-total').textContent = currentDay.totalEvents;
            document.getElementById('timeline-error-rate').textContent = currentDay.errorRate + '%';
            document.getElementById('timeline-countries').textContent = Object.keys(currentDay.countries).length;
            document.querySelector('.timeline-day').textContent = `Day ${currentDay.day}`;
            
            // Update heatmap with current day's data
            if (currentDay.heatmapData) {
                this.displayTimelineHeatmap(currentDay.heatmapData);
            }
        }
        
        // Update slider
        document.getElementById('timeline-slider').max = data.length - 1;
        document.getElementById('timeline-slider').value = this.state.timeline.currentDay;
    },

    displayTimelineHeatmap: function(heatmapData) {
        // Clear existing heatmap
        AppMap.clearHeatmap();
        
        // Display heatmap for current timeline day
        heatmapData.forEach(point => {
            AppMap.addHeatmapPoint(point.lat, point.lng, point.intensity, point.type);
        });
    },

    playTimeline: function() {
        if (this.state.timeline.isPlaying) {
            this.pauseTimeline();
            return;
        }
        
        this.state.timeline.isPlaying = true;
        document.getElementById('btn-timeline-play').textContent = '⏸';
        document.getElementById('btn-timeline-play').classList.add('playing');
        
        const playInterval = setInterval(() => {
            if (!this.state.timeline.isPlaying) {
                clearInterval(playInterval);
                return;
            }
            
            this.state.timeline.currentDay++;
            if (this.state.timeline.currentDay >= this.state.timeline.data.length) {
                this.state.timeline.currentDay = 0;
            }
            
            this.updateTimelineDisplay();
            document.getElementById('timeline-slider').value = this.state.timeline.currentDay;
        }, 1000 / this.state.timeline.playbackSpeed);
    },

    pauseTimeline: function() {
        this.state.timeline.isPlaying = false;
        document.getElementById('btn-timeline-play').textContent = '▶';
        document.getElementById('btn-timeline-play').classList.remove('playing');
    },

    navigateTimeline: function(direction) {
        this.pauseTimeline();
        
        if (direction === 'prev') {
            this.state.timeline.currentDay--;
            if (this.state.timeline.currentDay < 0) {
                this.state.timeline.currentDay = this.state.timeline.data.length - 1;
            }
        } else {
            this.state.timeline.currentDay++;
            if (this.state.timeline.currentDay >= this.state.timeline.data.length) {
                this.state.timeline.currentDay = 0;
            }
        }
        
        document.getElementById('timeline-slider').value = this.state.timeline.currentDay;
        this.updateTimelineDisplay();
    },

    changeTimelineSpeed: function(delta) {
        let newSpeed = this.state.timeline.playbackSpeed + delta;
        if (newSpeed < 0.5) newSpeed = 0.5;
        if (newSpeed > 5.0) newSpeed = 5.0;
        
        this.state.timeline.playbackSpeed = newSpeed;
        document.getElementById('timeline-speed-display').textContent = newSpeed.toFixed(1) + 'x';
        
        if (this.state.timeline.isPlaying) {
            this.pauseTimeline();
            this.playTimeline(); // Restart with new speed
        }
    },

    updateClock: function() {
        const now = new Date();
        const timeString = now.toISOString().split('T')[1].split('.')[0] + " UTC";
        document.getElementById('system-clock').textContent = timeString;
    },

    registerWindows: function() {
        // Find all windows and create taskbar entries
        const windows = document.querySelectorAll('.glass-window');
        const taskbar = document.getElementById('taskbar');
        
        windows.forEach(win => {
            const id = win.id;
            const title = win.dataset.title || "WINDOW";
            const isWarning = win.classList.contains('warning-theme');
            
            // Create Taskbar Button
            const btn = document.createElement('button');
            btn.className = `task-btn ${isWarning ? 'warning' : ''}`;
            btn.dataset.target = id;
            btn.innerHTML = `<span class="indicator"></span> ${title}`;
            
            // Initial state check
            if (win.style.display !== 'none') {
                btn.classList.add('active');
            }

            btn.addEventListener('click', () => this.toggleWindow(id));
            taskbar.appendChild(btn);
            
            // Store ref
            this.state.windows[id] = {
                element: win,
                button: btn,
                visible: win.style.display !== 'none'
            };
        });
    },

    toggleWindow: function(id) {
        const winData = this.state.windows[id];
        if (!winData) return;

        if (winData.visible) {
            if (winData.element.classList.contains('focused')) {
                this.minimizeWindow(id);
            } else {
                this.focusWindow(id);
            }
        } else {
            this.restoreWindow(id);
        }
    },

    minimizeWindow: function(id) {
        const winData = this.state.windows[id];
        winData.element.classList.add('minimized');
        winData.element.classList.remove('focused');
        
        winData.button.classList.remove('active');
        winData.visible = false;
    },

    restoreWindow: function(id) {
        const winData = this.state.windows[id];
        winData.element.style.display = 'flex';
        
        // Force reflow
        void winData.element.offsetWidth;
        winData.element.classList.remove('minimized');
        
        winData.button.classList.add('active');
        winData.visible = true;
        this.focusWindow(id);
    },

    toggleMaximize: function(id) {
        const winData = this.state.windows[id];
        winData.element.classList.toggle('maximized');
        this.focusWindow(id);
    },

    focusWindow: function(id) {
        // Lower z-index of all others
        Object.values(this.state.windows).forEach(w => {
            w.element.style.zIndex = w.element.classList.contains('maximized') ? 998 : 10;
            w.element.classList.remove('focused');
        });
        
        // Raise target
        const winData = this.state.windows[id];
        winData.element.style.zIndex = winData.element.classList.contains('maximized') ? 999 : 100;
        winData.element.classList.add('focused');
    },

    bindEvents: function() {
        // Top Nav Menu
        document.querySelectorAll('.nav-item').forEach(btn => {
            btn.addEventListener('click', (e) => {
                document.querySelectorAll('.nav-item').forEach(b => b.classList.remove('active'));
                e.currentTarget.classList.add('active');
                
                const action = e.currentTarget.dataset.action;
                if (action === 'toggle-settings') {
                    this.toggleWindow('win-fingerprint');
                } else if (action === 'toggle-analysis') {
                    this.toggleWindow('win-threats');
                } else if (action === 'toggle-countries') {
                    this.toggleWindow('win-countries');
                } else if (action === 'reset-view') {
                    AppMap.map.setView([20, 0], 2.5);
                    this.showDynamicMessage("VIEW RESET", "info");
                }
            });
        });

        // Timeline Controls
        document.getElementById('btn-timeline-play')?.addEventListener('click', () => this.playTimeline());
        document.getElementById('btn-timeline-prev')?.addEventListener('click', () => this.navigateTimeline('prev'));
        document.getElementById('btn-timeline-next')?.addEventListener('click', () => this.navigateTimeline('next'));
        document.getElementById('btn-timeline-slower')?.addEventListener('click', () => this.changeTimelineSpeed(-0.5));
        document.getElementById('btn-timeline-faster')?.addEventListener('click', () => this.changeTimelineSpeed(0.5));
        
        const timelineSlider = document.getElementById('timeline-slider');
        if (timelineSlider) {
            timelineSlider.addEventListener('input', (e) => {
                this.state.timeline.currentDay = parseInt(e.target.value);
                this.updateTimelineDisplay();
            });
        }

        // Window Controls
        document.querySelectorAll('.win-btn.minimize').forEach(btn => {
            btn.addEventListener('click', (e) => {
                const win = e.target.closest('.glass-window');
                this.minimizeWindow(win.id);
            });
        });
        
        document.querySelectorAll('.win-btn.close').forEach(btn => {
            btn.addEventListener('click', (e) => {
                const win = e.target.closest('.glass-window');
                this.minimizeWindow(win.id); // For now, close just minimizes
            });
        });
        
        document.querySelectorAll('.win-btn.maximize').forEach(btn => {
            btn.addEventListener('click', (e) => {
                const win = e.target.closest('.glass-window');
                this.toggleMaximize(win.id);
            });
        });
        
        // Start Menu
        const startBtn = document.querySelector('.start-btn');
        if (startBtn) {
            startBtn.addEventListener('click', () => {
                this.showDynamicMessage("SYSTEM MENU LOCKED", "alert");
            });
        }

        // Window Focus on Click
        document.querySelectorAll('.glass-window').forEach(win => {
            win.addEventListener('mousedown', () => this.focusWindow(win.id));
        });

        // Time Controls
        document.getElementById('btn-pause').addEventListener('click', () => this.togglePause());
        document.getElementById('btn-slower').addEventListener('click', () => this.changeSpeed(-0.5));
        document.getElementById('btn-faster').addEventListener('click', () => this.changeSpeed(0.5));

        // Country Statistics Filters
        document.querySelectorAll('.filter-btn').forEach(btn => {
            btn.addEventListener('click', (e) => {
                document.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
                e.currentTarget.classList.add('active');
                this.state.currentRegionFilter = e.currentTarget.dataset.region;
                this.updateCountryDisplay();
            });
        });

        // Fingerprint Analysis
        const fpInput = document.getElementById('fp-input');
        if (fpInput) {
            fpInput.addEventListener('input', (e) => this.handleKeystroke(e));
        }
        
        const analyzeBtn = document.getElementById('btn-analyze');
        if (analyzeBtn) {
            analyzeBtn.addEventListener('click', () => this.analyzeFingerprint());
        }
    },

    makeWindowsDraggable: function() {
        const windows = document.querySelectorAll('.glass-window');
        windows.forEach(win => {
            const header = win.querySelector('.window-header');
            let isDragging = false;
            let startX, startY, initialLeft, initialTop;

            header.addEventListener('mousedown', (e) => {
                isDragging = true;
                startX = e.clientX;
                startY = e.clientY;
                initialLeft = win.offsetLeft;
                initialTop = win.offsetTop;
                this.focusWindow(win.id);
            });

            window.addEventListener('mousemove', (e) => {
                if (!isDragging) return;
                e.preventDefault();
                const dx = e.clientX - startX;
                const dy = e.clientY - startY;
                win.style.left = `${initialLeft + dx}px`;
                win.style.top = `${initialTop + dy}px`;
            });

            window.addEventListener('mouseup', () => {
                isDragging = false;
            });
        });
    },

    showDynamicMessage: function(msg, type = 'info') {
        const island = document.getElementById('dynamic-island');
        const msgEl = island.querySelector('.island-message');
        const iconEl = island.querySelector('.island-icon');

        // Reset animation classes
        island.classList.remove('active', 'alert');
        void island.offsetWidth; // Trigger reflow

        msgEl.textContent = msg;
        iconEl.textContent = type === 'alert' ? '⚠' : (type === 'success' ? '✓' : 'ℹ');
        
        if (type === 'alert') island.classList.add('alert');
        island.classList.add('active');
        
        if (this.state.dynamicIslandTimeout) clearTimeout(this.state.dynamicIslandTimeout);
        
        this.state.dynamicIslandTimeout = setTimeout(() => {
            island.classList.remove('active', 'alert');
            // Revert to default after shrinking
            setTimeout(() => {
                if (!island.classList.contains('active')) {
                    msgEl.textContent = "SYSTEM READY";
                    iconEl.textContent = "ℹ";
                }
            }, 400);
        }, 3000);
    },

    togglePause: function() {
        this.state.paused = !this.state.paused;
        const btn = document.getElementById('btn-pause');
        
        if (this.state.paused) {
            btn.textContent = "▶";
            btn.classList.add('paused');
            this.showDynamicMessage("SIMULATION PAUSED", "info");
            this.stopGameLoop();
        } else {
            btn.textContent = "II";
            btn.classList.remove('paused');
            this.showDynamicMessage("SIMULATION RESUMED", "success");
            this.startGameLoop();
        }
    },

    changeSpeed: function(delta) {
        let newSpeed = this.state.speed + delta;
        if (newSpeed < 0.5) newSpeed = 0.5;
        if (newSpeed > 5.0) newSpeed = 5.0;
        
        this.state.speed = newSpeed;
        document.getElementById('speed-val').textContent = newSpeed.toFixed(1) + "x";
        
        if (!this.state.paused) {
            this.stopGameLoop();
            this.startGameLoop();
        }
        this.showDynamicMessage(`SPEED SET TO ${newSpeed.toFixed(1)}x`, "info");
    },

    startGameLoop: function() {
        if (this.state.intervalId) clearInterval(this.state.intervalId);
        const interval = 2000 / this.state.speed;
        this.state.intervalId = setInterval(() => {
            this.tick();
        }, interval);
    },

    stopGameLoop: function() {
        if (this.state.intervalId) {
            clearInterval(this.state.intervalId);
            this.state.intervalId = null;
        }
    },

    tick: function() {
        const item = Simulator.generateItem();
        this.processItem(item);
    },

    processItem: function(item) {
        this.state.totalItems++;
        if (item.has_error) this.state.totalErrors++;
        this.updateHUD();
        this.updateCountryStats(item);

        AppMap.addMarker(item);
        this.addToFeed(item);

        if (item.has_error) {
            this.addToThreats(item);
            this.showDynamicMessage(`ANOMALY DETECTED: ${item.country_name}`, "alert");
        }
    },

    updateHUD: function() {
        document.getElementById('stat-total').textContent = this.state.totalItems.toString();
        document.getElementById('stat-errors').textContent = this.state.totalErrors.toString();
    },

    initializeCountryStats: function() {
        // Initialize country statistics
        DATA.COUNTRIES.forEach(country => {
            this.state.countryStats[country.code] = {
                name: country.name,
                region: country.region,
                totalItems: 0,
                errorItems: 0,
                errorRate: 0
            };
        });
        this.updateCountryDisplay();
    },

    updateCountryStats: function(item) {
        const countryCode = item.country_name.substring(0, 3).toUpperCase();
        const countryStat = this.state.countryStats[countryCode];
        
        if (countryStat) {
            countryStat.totalItems++;
            if (item.has_error) {
                countryStat.errorItems++;
            }
            countryStat.errorRate = (countryStat.errorItems / countryStat.totalItems * 100).toFixed(1);
        }
        
        // Update display every 10 items to avoid excessive DOM updates
        if (this.state.totalItems % 10 === 0) {
            this.updateCountryDisplay();
        }
    },

    updateCountryDisplay: function() {
        const countryList = document.getElementById('country-list');
        if (!countryList) return;
        
        countryList.innerHTML = '';
        
        // Get countries based on current filter
        let countriesToShow = Object.values(this.state.countryStats);
        if (this.state.currentRegionFilter !== 'all') {
            countriesToShow = countriesToShow.filter(country => country.region === this.state.currentRegionFilter);
        }
        
        // Sort by error rate (descending)
        countriesToShow.sort((a, b) => b.errorRate - a.errorRate);
        
        // Show top 20 countries
        countriesToShow.slice(0, 20).forEach(country => {
            const countryEl = document.createElement('div');
            countryEl.className = 'country-item';
            
            const hasErrors = country.errorItems > 0;
            
            countryEl.innerHTML = `
                <div class="country-info">
                    <span class="country-name">${country.name}</span>
                    <span class="country-region">${country.region}</span>
                </div>
                <div class="country-stats">
                    <span class="error-count ${hasErrors ? '' : 'zero'}">${country.errorItems} ERR</span>
                    <span class="total-count">${country.totalItems} TOTAL</span>
                </div>
            `;
            
            countryList.appendChild(countryEl);
        });
    },

    addToFeed: function(item) {
        const feed = document.getElementById('feed-content');
        const el = document.createElement('div');
        el.className = `feed-item ${item.has_error ? 'error' : ''}`;
        el.innerHTML = `
            <div class="feed-meta">
                <span>${item.country_name}</span>
                <span>${item.timestamp.split('T')[1].split('.')[0]}</span>
            </div>
            <div class="feed-text">${item.headline}</div>
            ${item.has_error ? `
                <div class="error-correction">
                    <span>⚠</span> ${item.error_detail.error_word} &rarr; ${item.error_detail.corrected_word}
                </div>
            ` : ''}
        `;
        
        feed.prepend(el);
        if (feed.children.length > 50) feed.removeChild(feed.lastChild);
    },

    addToThreats: function(item) {
        const threats = document.getElementById('threats-content');
        const empty = threats.querySelector('.empty-state');
        if (empty) empty.remove();

        const el = document.createElement('div');
        el.className = 'feed-item error';
        el.innerHTML = `
            <div class="feed-meta">
                <span style="color:#FF4500">ANOMALY DETECTED</span>
            </div>
            <div class="feed-text">${item.headline}</div>
            <div class="error-correction" style="background:rgba(255,69,0,0.2)">
                ${item.error_detail.error_word}
            </div>
        `;
        threats.prepend(el);
         if (threats.children.length > 10) threats.removeChild(threats.lastChild);
    },

    // --- Fingerprint Logic ---
    handleKeystroke: function(e) {
        const now = performance.now();
        if (this.state.lastTime !== 0) {
            const diff = now - this.state.lastTime;
            this.state.keystrokes.push(diff);
            if (this.state.keystrokes.length > 20) this.state.keystrokes.shift();
            this.renderVisualizer();
        }
        this.state.lastTime = now;

        const btn = document.getElementById('btn-analyze');
        if (e.target.value.length > 5) {
            btn.disabled = false;
        } else {
            btn.disabled = true;
        }
    },

    renderVisualizer: function() {
        const container = document.getElementById('fp-visualizer');
        container.innerHTML = '';
        this.state.keystrokes.forEach(k => {
            const bar = document.createElement('div');
            bar.className = 'vis-bar';
            const h = Math.min(100, k / 5);
            bar.style.height = `${h}%`;
            container.appendChild(bar);
        });
    },

    analyzeFingerprint: function() {
        const btn = document.getElementById('btn-analyze');
        const result = document.getElementById('fp-result');
        const input = document.getElementById('fp-input');
        
        btn.disabled = true;
        btn.textContent = 'SCANNING...';
        result.textContent = "ANALYZING...";
        result.style.color = "#888";

        setTimeout(() => {
            btn.textContent = 'INITIATE SCAN';
            btn.disabled = false;
            
            const isSuspicious = input.value.toLowerCase().includes('error');
            
            result.textContent = isSuspicious ? '⚠ ANOMALY DETECTED' : '✓ IDENTITY VERIFIED';
            result.style.color = isSuspicious ? 'var(--alert)' : 'var(--success)';
            
            this.showDynamicMessage(isSuspicious ? "THREAT DETECTED IN INPUT" : "USER VERIFIED", isSuspicious ? "alert" : "success");
                
        }, 1500);
    }
};

// Start App
window.addEventListener('load', () => {
    App.init();
});