<script>
    import { newsFeed, gameStats } from '../stores.js';
    import { afterUpdate } from 'svelte';
    
    /** 
     * @type {any[]} 
     * Local reference to the news feed items for rendering.
     */
    let items = [];
    
    /** 
     * @type {HTMLElement} 
     * Reference to the scrollable container DOM element.
     */
    let scrollContainer;

    // Subscribe to the global news feed store
    newsFeed.subscribe(value => {
        items = value;
    });

    // Auto-scroll to bottom when new items are added
    afterUpdate(() => {
        if (scrollContainer) {
            scrollContainer.scrollTop = scrollContainer.scrollHeight;
        }
    });

</script>

<!-- News Feed Container -->
<div class="w-[400px] h-[400px] flex flex-col overflow-hidden p-2">
    <!-- Header: Status Indicator -->
    <div class="flex justify-between items-center mb-2 border-b border-glass-border pb-2 shrink-0">
        <div class="flex gap-2 items-center">
            <div class="w-2 h-2 rounded-full bg-red-500 animate-ping"></div>
            <span class="text-[0.65rem] font-mono text-neon-pink tracking-wider">LIVE STREAM</span>
        </div>
        <div class="text-[0.65rem] text-gray-400 font-mono">{$gameStats.totalItems} ITEMS</div>
    </div>

    <!-- Scrollable Feed List -->
    <div class="flex-1 overflow-y-auto pr-1 space-y-2 custom-scrollbar" bind:this={scrollContainer}>
        {#each items as item (item.id)}
            <div class="p-2 rounded bg-black/40 border border-white/5 hover:border-neon-blue/50 transition-colors group">
                <!-- Item Meta: Country and Time -->
                <div class="flex justify-between text-[0.6rem] font-mono text-gray-500 mb-0.5">
                    <span class="text-neon-green">{item.country_name}</span>
                    <span>{new Date(item.timestamp).toLocaleString(undefined, {month:'numeric', day:'numeric', hour:'2-digit', minute:'2-digit'})}</span>
                </div>
                
                <!-- Headline Content -->
                <div class="text-xs leading-snug group-hover:text-white transition-colors text-gray-300">
                    {#if item.has_error}
                        <!-- Glitch Effect for Error Items -->
                        <span class="text-red-400 glitch-text" data-text={item.headline}>{item.headline}</span>
                    {:else}
                        {item.headline}
                    {/if}
                </div>
            </div>
        {/each}
        
        <!-- Empty State -->
        {#if items.length === 0}
            <div class="text-center text-gray-600 mt-10 text-[0.6rem] font-mono">INITIALIZING...</div>
        {/if}
    </div>
</div>

<style>
    .custom-scrollbar::-webkit-scrollbar {
        width: 4px;
    }
    .custom-scrollbar::-webkit-scrollbar-track {
        background: rgba(255, 255, 255, 0.05);
    }
    .custom-scrollbar::-webkit-scrollbar-thumb {
        background: rgba(0, 243, 255, 0.3);
        border-radius: 2px;
    }
    
    .glitch-text {
        position: relative;
        display: inline-block;
    }
    
    .glitch-text::before,
    .glitch-text::after {
        content: attr(data-text);
        position: absolute;
        top: 0;
        left: 0;
        width: 100%;
        height: 100%;
    }
    
    .glitch-text::before {
        left: 2px;
        text-shadow: -1px 0 red;
        clip: rect(24px, 550px, 90px, 0);
        animation: glitch-anim-1 2.5s infinite linear alternate-reverse;
    }
    
    .glitch-text::after {
        left: -2px;
        text-shadow: -1px 0 blue;
        clip: rect(85px, 550px, 140px, 0);
        animation: glitch-anim-2 2s infinite linear alternate-reverse;
    }
    
    @keyframes glitch-anim-1 {
        0% { clip: rect(20px, 9999px, 80px, 0); }
        20% { clip: rect(60px, 9999px, 10px, 0); }
        40% { clip: rect(10px, 9999px, 90px, 0); }
        60% { clip: rect(80px, 9999px, 30px, 0); }
        80% { clip: rect(40px, 9999px, 50px, 0); }
        100% { clip: rect(70px, 9999px, 20px, 0); }
    }
    
    @keyframes glitch-anim-2 {
        0% { clip: rect(90px, 9999px, 10px, 0); }
        20% { clip: rect(10px, 9999px, 80px, 0); }
        40% { clip: rect(50px, 9999px, 40px, 0); }
        60% { clip: rect(30px, 9999px, 70px, 0); }
        80% { clip: rect(60px, 9999px, 20px, 0); }
        100% { clip: rect(20px, 9999px, 60px, 0); }
    }
</style>
