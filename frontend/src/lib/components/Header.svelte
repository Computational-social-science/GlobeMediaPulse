<!-- STABLE COMPONENT: Do not modify without explicit user request -->
<script>
    import { onMount } from 'svelte';
    import { soundManager } from '../audio/SoundManager.js';
    
    // Stats State
    let totalSources = 0;
    
    // Real-time Clock State
    let time = new Date().toLocaleTimeString();
    let date = new Date().toLocaleDateString();

    onMount(() => {
        // Define async init function
        const init = async () => {
             // Fetch Initial Stats
            try {
                const res = await fetch('http://localhost:8002/api/map-data');
                if (res.ok) {
                    const data = await res.json();
                    if (data.total_sources) {
                        totalSources = data.total_sources;
                    }
                }
            } catch (e) {
                console.error("Failed to fetch map stats:", e);
            }
        };

        init();

        // Update clock every second
        const clockInterval = setInterval(() => {
            const now = new Date();
            time = now.toLocaleTimeString();
            date = now.toLocaleDateString();
        }, 1000);

        // Optional: Poll for updates every minute
        const statsInterval = setInterval(async () => {
             try {
                const res = await fetch('http://localhost:8002/api/map-data');
                if (res.ok) {
                    const data = await res.json();
                    if (data.total_sources) {
                        totalSources = data.total_sources;
                    }
                }
            } catch (e) {
                // Silent fail
            }
        }, 60000);

        return () => { 
            clearInterval(clockInterval);
            clearInterval(statsInterval);
        };
    });

    /**
     * Formats large numbers into a readable format (e.g., 1.2 M).
     * @param {number} num - The number to format.
     * @returns {string} - The formatted string.
     */
    function formatBigNumber(num) {
        if (num >= 1000000) {
            return (num / 1000000).toFixed(3) + ' M';
        }
        return num.toLocaleString();
    }

</script>

<!-- Main Header Component -->
<header class="w-full h-20 flex items-center justify-between px-6 z-50 pointer-events-auto bg-[#0f172a]/85 border-b border-white/25 backdrop-blur-md select-none shadow-[0_8px_32px_rgba(0,0,0,0.5),inset_0_0_20px_rgba(255,255,255,0.08)]">
    <!-- Left: Brand Identity -->
    <div class="flex items-center gap-4">
        <!-- Vivid Animated ICON -->
        <div class="relative w-12 h-12 flex items-center justify-center">
            <!-- Outer Ring -->
            <div class="absolute inset-0 rounded-full border border-neon-blue/30 animate-spin-slow"></div>
            <!-- Inner Pulse -->
            <div class="absolute w-8 h-8 rounded-full bg-neon-blue/10 animate-pulse border border-neon-blue/50 flex items-center justify-center">
                <div class="w-4 h-4 bg-neon-blue/80 rounded-full shadow-[0_0_15px_#00f3ff]"></div>
            </div>
            <!-- Scanning Line -->
            <div class="absolute inset-0 rounded-full border-t-2 border-neon-blue/80 animate-spin shadow-[0_0_10px_#00f3ff]"></div>
        </div>
        
        <div class="flex flex-col">
        <h1 class="text-2xl font-black tracking-tighter text-transparent bg-clip-text bg-gradient-to-r from-white via-neon-blue to-neon-purple drop-shadow-[0_0_10px_rgba(0,243,255,0.5)] font-tech">
            GLOBE MEDIA PULSE
        </h1>
        <span class="text-xs tracking-[0.2em] text-neon-blue/80 font-mono font-bold">Uncharted Pulse of Global Media</span>
    </div>
    </div>

    <!-- Center: Decorative Elements -->
    <div class="hidden lg:flex items-center gap-2 opacity-40">
        <div class="w-24 h-[1px] bg-gradient-to-r from-transparent via-white to-transparent"></div>
        <div class="w-2 h-2 border border-white rotate-45 animate-pulse"></div>
        <div class="w-24 h-[1px] bg-gradient-to-r from-transparent via-white to-transparent"></div>
    </div>

    <!-- Right: System Status & Clock -->
    <div class="flex items-center gap-6">
        
        <!-- Total Sources Stats -->
        <div class="hidden md:flex items-center gap-3 border-r border-white/10 pr-6">
            <div class="flex flex-col items-end">
                <span class="text-[10px] text-neon-blue/70 font-mono tracking-widest uppercase">DISCOVERED SOURCES</span>
                <span class="text-xl font-mono font-bold text-white drop-shadow-[0_0_5px_rgba(255,255,255,0.5)] flex items-center gap-2">
                    <span class="w-2 h-2 rounded-full bg-green-500 animate-pulse"></span>
                    {totalSources.toLocaleString()}
                </span>
            </div>
        </div>



        <!-- Real-time Clock -->
        <div class="hidden xl:flex items-center gap-3 pl-6">
            <div class="flex flex-col items-end">
                <span class="text-[10px] text-neon-blue/70 font-mono tracking-widest uppercase">{date}</span>
                <span class="text-xl font-mono font-bold text-white drop-shadow-[0_0_5px_rgba(255,255,255,0.5)]">
                    {time}
                </span>
            </div>
        </div>
    </div>
</header>
