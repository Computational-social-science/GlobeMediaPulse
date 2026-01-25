<script>
    import { serviceStatus, backendThreadStatus } from '../stores.js';
    import LogViewer from './LogViewer.svelte';
    import CrawlerControl from './CrawlerControl.svelte';
    
    let activeTab = 'health'; // 'health' | 'logs' | 'controls'

    /**
     * @param {string} status
     */
    function getStatusColor(status) {
        if (status === 'ok' || status === 'running' || status === 'active') return 'text-green-400';
        if (status === 'degraded' || status === 'warning') return 'text-yellow-400';
        return 'text-red-400';
    }
</script>

<div class="h-full flex flex-col">
    <!-- Tabs -->
    <div class="flex border-b border-white/10 mb-4">
        <button class="px-3 py-2 text-xs font-bold uppercase transition-colors {activeTab === 'health' ? 'text-neon-blue border-b-2 border-neon-blue' : 'text-gray-500 hover:text-white'}"
                on:click={() => activeTab = 'health'}>
            Health
        </button>
        <button class="px-3 py-2 text-xs font-bold uppercase transition-colors {activeTab === 'logs' ? 'text-neon-blue border-b-2 border-neon-blue' : 'text-gray-500 hover:text-white'}"
                on:click={() => activeTab = 'logs'}>
            Logs
        </button>
        <button class="px-3 py-2 text-xs font-bold uppercase transition-colors {activeTab === 'controls' ? 'text-neon-blue border-b-2 border-neon-blue' : 'text-gray-500 hover:text-white'}"
                on:click={() => activeTab = 'controls'}>
            Controls
        </button>
    </div>

    <!-- Content -->
    <div class="flex-1 overflow-x-auto overflow-y-auto pr-1 pl-1">
        {#if activeTab === 'health'}
            <div class="space-y-4">
                <!-- System Health Monitor -->
                <div class="bg-white/5 p-3 rounded border border-white/10">
                    <h4 class="text-neon-blue font-bold text-xs uppercase mb-2 flex items-center gap-2">
                        <span class="material-icons-round text-sm">dns</span>
                        System Health
                    </h4>
                    
                    <!-- Services -->
                    <div class="mb-3">
                        <div class="text-[10px] text-gray-400 mb-1 font-mono uppercase">Infrastructure</div>
                        <div class="grid grid-cols-2 gap-2 text-xs">
                            <div class="flex justify-between bg-black/20 p-1.5 rounded">
                                <span>Postgres</span>
                                <span class="font-mono {getStatusColor($serviceStatus.postgres)}">{$serviceStatus.postgres?.toUpperCase() || 'UNK'}</span>
                            </div>
                            <div class="flex justify-between bg-black/20 p-1.5 rounded">
                                <span>Redis</span>
                                <span class="font-mono {getStatusColor($serviceStatus.redis)}">{$serviceStatus.redis?.toUpperCase() || 'UNK'}</span>
                            </div>
                        </div>
                    </div>

                    <!-- Threads -->
                    <div>
                        <div class="text-[10px] text-gray-400 mb-1 font-mono uppercase">Active Threads</div>
                        <div class="space-y-1 text-xs">
                            <div class="flex justify-between bg-black/20 p-1.5 rounded border-l-2 border-neon-blue">
                                <span>News Crawler</span>
                                <span class="font-mono {getStatusColor($backendThreadStatus.crawler)}">{$backendThreadStatus.crawler?.toUpperCase() || 'UNK'}</span>
                            </div>
                            <div class="flex justify-between bg-black/20 p-1.5 rounded border-l-2 border-purple-500">
                                <span>AI Analyzer</span>
                                <span class="font-mono {getStatusColor($backendThreadStatus.analyzer)}">{$backendThreadStatus.analyzer?.toUpperCase() || 'UNK'}</span>
                            </div>
                            <div class="flex justify-between bg-black/20 p-1.5 rounded border-l-2 border-gray-500">
                                <span>System Cleanup</span>
                                <span class="font-mono {getStatusColor($backendThreadStatus.cleanup)}">{$backendThreadStatus.cleanup?.toUpperCase() || 'UNK'}</span>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        {:else if activeTab === 'logs'}
            <LogViewer />
        {:else if activeTab === 'controls'}
            <CrawlerControl />
        {/if}
    </div>
</div>
