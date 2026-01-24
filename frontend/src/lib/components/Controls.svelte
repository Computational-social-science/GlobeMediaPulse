<script>
    import { isPaused, playbackSpeed } from '../stores.js';

    /**
     * Toggles the global pause state.
     */
    function togglePause() {
        isPaused.update(v => !v);
    }

    /** 
     * Updates the global playback speed multiplier.
     * @param {any} e - Input change event.
     */
    function changeSpeed(e) {
        playbackSpeed.set(parseFloat(e.target.value));
    }
</script>

<div class="glass-panel px-6 py-3 flex items-center gap-6 backdrop-blur-xl bg-black/60">
    <!-- Play/Pause Button -->
    <button 
        class="w-12 h-12 rounded-full border border-neon-blue/30 flex items-center justify-center hover:bg-neon-blue/10 transition-all active:scale-95 group"
        on:click={togglePause}
        title={$isPaused ? "Resume Simulation" : "Pause Simulation"}
    >
        {#if $isPaused}
            <!-- Play Icon -->
            <svg xmlns="http://www.w3.org/2000/svg" class="h-6 w-6 text-neon-blue group-hover:text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M14.752 11.168l-3.197-2.132A1 1 0 0010 9.87v4.263a1 1 0 001.555.832l3.197-2.132a1 1 0 000-1.664z" />
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
        {:else}
            <!-- Pause Icon -->
            <svg xmlns="http://www.w3.org/2000/svg" class="h-6 w-6 text-neon-blue group-hover:text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10 9v6m4-6v6m7-3a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
        {/if}
    </button>

    <!-- Speed Slider -->
    <div class="flex flex-col gap-1 w-32">
        <div class="flex justify-between text-[10px] font-mono text-neon-blue">
            <span>SPEED</span>
            <span>{$playbackSpeed}x</span>
        </div>
        <input 
            type="range" 
            min="0.5" 
            max="5.0" 
            step="0.5" 
            value={$playbackSpeed} 
            on:input={changeSpeed}
            class="w-full h-1 bg-gray-700 rounded-lg appearance-none cursor-pointer accent-neon-blue"
        />
    </div>
</div>

<style>
    /* Custom Slider Styling for Webkit */
    input[type=range]::-webkit-slider-thumb {
        -webkit-appearance: none;
        height: 12px;
        width: 12px;
        border-radius: 50%;
        background: #00f3ff;
        cursor: pointer;
        box-shadow: 0 0 5px #00f3ff;
        margin-top: -4px; /* Adjust for vertical alignment */
    }
    input[type=range]::-webkit-slider-runnable-track {
        height: 4px;
        background: #1f1f3a;
        border-radius: 2px;
    }
</style>
