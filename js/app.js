const App = {
    state: {
        paused: false,
        speed: 1.0,
        totalItems: 0,
        totalErrors: 0,
        lastTime: 0,
        intervalId: null,
        keystrokes: []
    },

    init: function() {
        console.log("System Initializing...");
        AppMap.init();
        this.bindEvents();
        this.startGameLoop();
        console.log("System Online.");
    },

    bindEvents: function() {
        // Time Controls
        document.getElementById('btn-pause').addEventListener('click', () => this.togglePause());
        document.getElementById('btn-slower').addEventListener('click', () => this.changeSpeed(-0.5));
        document.getElementById('btn-faster').addEventListener('click', () => this.changeSpeed(0.5));

        // Fingerprint Analysis
        const fpInput = document.getElementById('fp-input');
        fpInput.addEventListener('input', (e) => this.handleKeystroke(e));
        
        document.getElementById('btn-analyze').addEventListener('click', () => this.analyzeFingerprint());
    },

    togglePause: function() {
        this.state.paused = !this.state.paused;
        const btn = document.getElementById('btn-pause');
        const iconPause = document.getElementById('icon-pause');
        const iconPlay = document.getElementById('icon-play');
        
        if (this.state.paused) {
            btn.classList.add('paused');
            iconPause.style.display = 'none';
            iconPlay.style.display = 'inline';
            this.stopGameLoop();
        } else {
            btn.classList.remove('paused');
            iconPause.style.display = 'inline';
            iconPlay.style.display = 'none';
            this.startGameLoop();
        }
    },

    changeSpeed: function(delta) {
        let newSpeed = this.state.speed + delta;
        if (newSpeed < 0.5) newSpeed = 0.5;
        if (newSpeed > 5.0) newSpeed = 5.0;
        
        this.state.speed = newSpeed;
        document.getElementById('speed-val').textContent = newSpeed.toFixed(1);
        
        // Restart loop if running to apply new speed
        if (!this.state.paused) {
            this.stopGameLoop();
            this.startGameLoop();
        }
    },

    startGameLoop: function() {
        if (this.state.intervalId) clearInterval(this.state.intervalId);
        
        // Base interval is 2000ms. Speed 1x = 2000ms, Speed 2x = 1000ms
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
        // Update Stats
        this.state.totalItems++;
        if (item.has_error) this.state.totalErrors++;
        this.updateHUD();

        // Update Map
        AppMap.addMarker(item);

        // Update Feed
        this.addToFeed(item);

        // Update Threats Panel if error
        if (item.has_error) {
            this.addToThreats(item);
        }
    },

    updateHUD: function() {
        document.getElementById('stat-total').textContent = this.state.totalItems.toString().padStart(6, '0');
        document.getElementById('stat-errors').textContent = this.state.totalErrors.toString().padStart(5, '0');
        
        const rate = this.state.totalItems > 0 
            ? ((this.state.totalErrors / this.state.totalItems) * 100).toFixed(1) 
            : '0.0';
        document.getElementById('stat-rate').textContent = rate;
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
        // Keep limit
        if (feed.children.length > 50) {
            feed.removeChild(feed.lastChild);
        }
    },

    addToThreats: function(item) {
        const threats = document.getElementById('threats-content');
        // Remove empty state if present
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
         if (threats.children.length > 10) {
            threats.removeChild(threats.lastChild);
        }
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
            const h = Math.min(100, k / 5); // Scale
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
        result.classList.add('hidden');

        setTimeout(() => {
            btn.textContent = 'ANALYZE PATTERN';
            btn.disabled = false;
            
            const isSuspicious = input.value.toLowerCase().includes('error');
            
            result.classList.remove('hidden');
            result.className = `fp-result ${isSuspicious ? 'suspicious' : ''}`;
            result.innerHTML = isSuspicious 
                ? '<span class="icon">⚠</span> ANOMALY DETECTED'
                : '<span class="icon">✓</span> VERIFIED HUMAN';
                
        }, 1500);
    }
};

// Global toggle function for HTML buttons
window.togglePanel = function(id) {
    const el = document.getElementById(id);
    el.classList.toggle('hidden');
};

// Start App
window.addEventListener('load', () => {
    App.init();
});
