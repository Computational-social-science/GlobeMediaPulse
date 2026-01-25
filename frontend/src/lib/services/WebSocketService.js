
import { get } from 'svelte/store';
import { isConnected, systemStatus, newsEvents, systemLogs } from '../stores.js';

class WebSocketService {
    constructor() {
        this.ws = null;
        this.reconnectInterval = 5000;
        this.url = (window.location.hostname === 'localhost') 
            ? 'ws://localhost:8002/ws' 
            : 'wss://globe-media-pulse.fly.dev/ws';
    }

    connect() {
        if (this.ws) return;

        console.log(`Connecting to WebSocket: ${this.url}`);
        this.ws = new WebSocket(this.url);

        this.ws.onopen = () => {
            console.log('✅ WebSocket Connected');
            isConnected.set(true);
            systemStatus.set('ONLINE');
        };

        this.ws.onmessage = (event) => {
            try {
                const message = JSON.parse(event.data);
                
                switch (message.type) {
                    case 'news_event':
                        // Payload might be a string or object
                        let article = message.payload;
                        if (typeof article === 'string') {
                            article = JSON.parse(article);
                        }
                        newsEvents.set(article);
                        break;
                        
                    case 'log_entry':
                        systemLogs.update(logs => {
                            const newLogs = [message.payload, ...logs];
                            if (newLogs.length > 100) newLogs.pop(); // Keep last 100
                            return newLogs;
                        });
                        break;
                        
                    default:
                        console.log('Unknown WS Message:', message);
                }
            } catch (e) {
                console.error('WS Parse Error:', e);
            }
        };

        this.ws.onclose = () => {
            console.log('⚠️ WebSocket Closed');
            isConnected.set(false);
            systemStatus.set('OFFLINE');
            this.ws = null;
            setTimeout(() => this.connect(), this.reconnectInterval);
        };

        this.ws.onerror = (e) => {
            console.error('WebSocket Error:', e);
        };
    }
}

export const webSocketService = new WebSocketService();
