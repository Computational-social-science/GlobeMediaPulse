<script>
    import { countryStats } from '../stores.js';
</script>

<!-- Regional Statistics Table Container -->
<div class="p-4 w-[400px] h-[400px]">
    <table class="w-full text-xs font-mono text-left">
        <!-- Table Header -->
        <thead class="text-neon-blue border-b border-white/10">
            <tr>
                <th class="p-2">CNTRY</th>
                <th class="p-2 text-right">EVENTS</th>
                <th class="p-2 text-right">ERRORS</th>
                <th class="p-2">SOURCE</th>
            </tr>
        </thead>
        
        <!-- Table Body: Sorted by Error Count Descending -->
        <tbody class="text-gray-300">
            {#each Object.entries($countryStats).sort((a,b) => b[1].errors - a[1].errors) as [code, stats]}
                <tr class="border-b border-white/5 hover:bg-white/5 transition-colors">
                    <td class="p-2 font-bold">{stats.name}</td>
                    <td class="p-2 text-right">{stats.total}</td>
                    <td class="p-2 text-right text-red-400">{stats.errors}</td>
                    <td class="p-2 text-[10px] text-gray-400">
                        {#if stats.sources && stats.sources.length > 0}
                            {stats.sources[0].source.toUpperCase()} 
                            <span class="opacity-50">({Math.round((stats.sources[0].count / stats.errors) * 100)}%)</span>
                        {:else}
                            -
                        {/if}
                    </td>
                </tr>
            {/each}
        </tbody>
    </table>
    
    <!-- Empty State Message -->
    {#if Object.keys($countryStats).length === 0}
        <div class="text-center text-gray-500 mt-10">NO DATA COLLECTED</div>
    {/if}
</div>