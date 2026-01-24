<script>
    import { onMount } from 'svelte';
    import { mediaSources } from '../stores.js';
    
    let loading = true;
    let error = null;
    let searchTerm = '';
    let tierFilter = 'all';

    async function fetchMediaSources() {
        loading = true;
        try {
            const apiBase = import.meta.env.VITE_API_URL || import.meta.env.VITE_API_BASE_URL || 'http://localhost:8002';
            const res = await fetch(`${apiBase}/api/media/sources`);
            if (res.ok) {
                const data = await res.json();
                mediaSources.set(data);
            } else {
                error = "Failed to fetch media sources";
            }
        } catch (e) {
            error = e.message;
        } finally {
            loading = false;
        }
    }

    onMount(() => {
        fetchMediaSources();
    });

    $: filteredSources = $mediaSources.filter(source => {
        const matchesSearch = source.name.toLowerCase().includes(searchTerm.toLowerCase()) || 
                              source.domain.toLowerCase().includes(searchTerm.toLowerCase()) ||
                              source.country_name.toLowerCase().includes(searchTerm.toLowerCase());
        const matchesTier = tierFilter === 'all' || source.tier === tierFilter;
        return matchesSearch && matchesTier;
    });
</script>

<div class="h-full flex flex-col text-white font-mono">
    <!-- Toolbar -->
    <div class="flex items-center gap-4 mb-4 p-2 border-b border-white/10">
        <div class="relative flex-1">
            <input 
                type="text" 
                placeholder="Search sources..." 
                bind:value={searchTerm}
                class="w-full bg-black/30 border border-neon-blue/30 rounded px-3 py-1 text-sm focus:outline-none focus:border-neon-blue"
            />
            <span class="absolute right-3 top-1.5 text-xs text-white/50">🔍</span>
        </div>
        
        <select 
            bind:value={tierFilter}
            class="bg-black/30 border border-neon-blue/30 rounded px-2 py-1 text-sm focus:outline-none focus:border-neon-blue"
        >
            <option value="all">All Tiers</option>
            <option value="Tier-0">Tier-0 (Global)</option>
            <option value="Tier-1">Tier-1 (National)</option>
            <option value="Tier-2">Tier-2 (Local)</option>
        </select>
        
        <button 
            on:click={fetchMediaSources}
            class="px-3 py-1 text-xs border border-neon-green/30 rounded hover:bg-neon-green/20 text-neon-green transition-colors"
        >
            REFRESH
        </button>
    </div>

    <!-- Content -->
    <div class="flex-1 overflow-y-auto pr-2 custom-scrollbar">
        {#if loading}
            <div class="flex items-center justify-center h-32">
                <div class="w-8 h-8 border-2 border-neon-blue border-t-transparent rounded-full animate-spin"></div>
            </div>
        {:else if error}
            <div class="text-red-500 p-4 border border-red-500/30 bg-red-500/10 rounded">
                Error: {error}
            </div>
        {:else}
            <div class="grid grid-cols-1 gap-2">
                {#each filteredSources as source}
                    <div class="group relative p-3 bg-black/40 border border-white/5 hover:border-neon-blue/50 transition-all rounded">
                        <div class="flex items-start justify-between">
                            <div class="flex items-center gap-3">
                                <!-- Logo Placeholder or Image -->
                                <div class="w-10 h-10 bg-white/5 rounded flex items-center justify-center overflow-hidden border border-white/10">
                                    {#if source.logo_url}
                                        <img src={source.logo_url} alt={source.name} class="w-full h-full object-contain" />
                                    {:else}
                                        <span class="text-xs font-bold text-white/30">{source.domain.substring(0, 2).toUpperCase()}</span>
                                    {/if}
                                </div>
                                
                                <div>
                                    <div class="flex items-center gap-2">
                                        <h3 class="font-bold text-sm text-neon-blue">{source.name}</h3>
                                        <span class={`text-[10px] px-1.5 rounded border ${
                                            source.tier === 'Tier-0' ? 'border-neon-pink text-neon-pink' : 
                                            source.tier === 'Tier-1' ? 'border-neon-purple text-neon-purple' : 
                                            'border-white/30 text-white/50'
                                        }`}>
                                            {source.tier}
                                        </span>
                                    </div>
                                    <div class="text-xs text-white/60 mt-0.5 flex items-center gap-2">
                                        <span>{source.domain}</span>
                                        <span class="w-1 h-1 bg-white/30 rounded-full"></span>
                                        <span>{source.country_name}</span>
                                    </div>
                                </div>
                            </div>
                            
                            <!-- Status Indicators -->
                            <div class="flex flex-col items-end gap-1">
                                <div class="flex items-center gap-1" title="Structure Fingerprint">
                                    <span class="text-[10px] text-white/40">SIMHASH</span>
                                    <div class={`w-2 h-2 rounded-full ${source.structure_simhash ? 'bg-neon-green shadow-neon-green' : 'bg-white/10'}`}></div>
                                </div>
                            </div>
                        </div>
                        
                        <!-- Hover Detail Overlay (Optional) -->
                        <div class="hidden group-hover:block absolute top-full left-0 w-full bg-black/90 border border-neon-blue/30 z-10 p-2 text-xs mt-1">
                            <div class="grid grid-cols-2 gap-2">
                                <div><span class="text-white/40">Type:</span> {source.type || 'N/A'}</div>
                                <div><span class="text-white/40">Lang:</span> {source.language || 'N/A'}</div>
                                <div class="col-span-2 truncate"><span class="text-white/40">Hash:</span> {source.structure_simhash || 'Pending...'}</div>
                            </div>
                        </div>
                    </div>
                {/each}
            </div>
            
            <div class="mt-4 text-center text-xs text-white/30">
                Showing {filteredSources.length} sources
            </div>
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
</style>
