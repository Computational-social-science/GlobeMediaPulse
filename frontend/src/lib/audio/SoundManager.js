
import { get } from 'svelte/store';
import { audioEnabled, audioVolume, systemStatus } from '../stores';

/**
 * SoundManager: A singleton class to handle UI sound effects using Web Audio API.
 * Generates synthetic sounds to avoid asset dependencies and ensure a consistent "Tech" feel.
 */
class SoundManager {
    constructor() {
        this.ctx = null;
        this.masterGain = null;
        this.humOscillator = null;
        this.isInitialized = false;
        this.systemStatus = 'OFFLINE'; // Default to OFFLINE
    }

    /**
     * Initialize the AudioContext (must be called after user interaction)
     */
    init() {
        if (this.isInitialized) return;

        try {
            // @ts-ignore
            const AudioContext = window.AudioContext || window.webkitAudioContext;
            this.ctx = new AudioContext();
            this.masterGain = this.ctx.createGain();
            this.masterGain.connect(this.ctx.destination);
            
            // Subscribe to volume store
            audioVolume.subscribe(vol => {
                if (this.masterGain) {
                    this.masterGain.gain.setValueAtTime(vol, this.ctx.currentTime);
                }
            });

            // Subscribe to system status store
            systemStatus.subscribe(status => {
                this.systemStatus = status;
            });

            this.isInitialized = true;
            console.log('🔊 SoundManager Initialized');
        } catch (e) {
            console.error('Failed to initialize SoundManager:', e);
        }
    }

    /**
     * Play a short, high-pitched "blip" for hover effects.
     * Logic: Only play if system is OFFLINE.
     */
    playHover() {
        if (!get(audioEnabled) || !this.ctx) return;
        // Only play interaction sounds if OFFLINE
        if (this.systemStatus !== 'OFFLINE') return;

        if (this.ctx.state === 'suspended') this.ctx.resume();

        const osc = this.ctx.createOscillator();
        const gain = this.ctx.createGain();

        osc.connect(gain);
        gain.connect(this.masterGain);

        // Tech/Sci-Fi Blip: High frequency, very short envelope
        osc.type = 'sine';
        osc.frequency.setValueAtTime(800, this.ctx.currentTime);
        osc.frequency.exponentialRampToValueAtTime(1200, this.ctx.currentTime + 0.05);

        gain.gain.setValueAtTime(0.05, this.ctx.currentTime); // Lower volume
        gain.gain.exponentialRampToValueAtTime(0.001, this.ctx.currentTime + 0.05);

        osc.start();
        osc.stop(this.ctx.currentTime + 0.05);
    }

    /**
     * Play a mechanical "click" or "thud" for active interactions.
     * Logic: Only play if system is OFFLINE.
     */
    playClick() {
        if (!get(audioEnabled) || !this.ctx) return;
        if (this.systemStatus !== 'OFFLINE') return;

        if (this.ctx.state === 'suspended') this.ctx.resume();

        const osc = this.ctx.createOscillator();
        const gain = this.ctx.createGain();

        osc.connect(gain);
        gain.connect(this.masterGain);

        osc.type = 'triangle';
        osc.frequency.setValueAtTime(300, this.ctx.currentTime);
        osc.frequency.exponentialRampToValueAtTime(50, this.ctx.currentTime + 0.1);

        gain.gain.setValueAtTime(0.1, this.ctx.currentTime);
        gain.gain.exponentialRampToValueAtTime(0.001, this.ctx.currentTime + 0.1);

        osc.start();
        osc.stop(this.ctx.currentTime + 0.1);
    }

    /**
     * Play a "Data Chirp" sound for real-time events.
     * This plays regardless of system status (as it indicates work).
     */
    playDataChirp() {
        if (!get(audioEnabled) || !this.ctx) return;
        if (this.ctx.state === 'suspended') this.ctx.resume();

        const t = this.ctx.currentTime;
        const osc = this.ctx.createOscillator();
        const gain = this.ctx.createGain();

        osc.connect(gain);
        gain.connect(this.masterGain);

        // Chirp: Rapid frequency sweep up
        osc.type = 'sine';
        osc.frequency.setValueAtTime(2000, t);
        osc.frequency.linearRampToValueAtTime(4000, t + 0.05);

        gain.gain.setValueAtTime(0.05, t);
        gain.gain.exponentialRampToValueAtTime(0.001, t + 0.05);

        osc.start(t);
        osc.stop(t + 0.05);
    }

    /**
     * Play a digital "chirp" for success or new data.
     */
    playSuccess() {
        if (!get(audioEnabled) || !this.ctx) return;
        if (this.ctx.state === 'suspended') this.ctx.resume();

        const osc = this.ctx.createOscillator();
        const gain = this.ctx.createGain();

        osc.connect(gain);
        gain.connect(this.masterGain);

        // Digital Chirp: Arpeggio-like frequency jump
        osc.type = 'triangle';
        osc.frequency.setValueAtTime(880, this.ctx.currentTime);
        osc.frequency.setValueAtTime(1760, this.ctx.currentTime + 0.05);

        gain.gain.setValueAtTime(0.1, this.ctx.currentTime);
        gain.gain.exponentialRampToValueAtTime(0.001, this.ctx.currentTime + 0.2);

        osc.start();
        osc.stop(this.ctx.currentTime + 0.2);
    }

    /**
     * Toggle a low-frequency background hum (Ambience).
     * @param {boolean} active 
     */
    toggleHum(active) {
        if (!this.ctx) return;

        if (active && !this.humOscillator && get(audioEnabled)) {
            const osc = this.ctx.createOscillator();
            const gain = this.ctx.createGain();
            
            osc.connect(gain);
            gain.connect(this.masterGain);

            osc.type = 'sawtooth';
            osc.frequency.setValueAtTime(40, this.ctx.currentTime); // Low 40Hz drone
            
            // Very subtle volume
            gain.gain.setValueAtTime(0.005, this.ctx.currentTime);

            osc.start();
            this.humOscillator = { osc, gain };
        } else if (!active && this.humOscillator) {
            this.humOscillator.osc.stop();
            this.humOscillator.osc.disconnect();
            this.humOscillator.gain.disconnect();
            this.humOscillator = null;
        }
    }
}

export const soundManager = new SoundManager();
