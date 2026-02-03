<script>
  import { onMount } from 'svelte';
  import { fade, fly } from 'svelte/transition';
  
  export let onClose = () => {};

  let mode = 'selection'; // 'selection', 'auto', 'wizard'
  let step = 1;
  let progress = 0;
  let logs = [];
  let isComplete = false;
  
  // Wizard State
  let wizardData = {
    template: 'news',
    intensity: 50,
    region: 'global',
    subscribeReport: true
  };

  onMount(() => {
    const saved = localStorage.getItem('gmp_setup_config');
    if (saved) {
      try {
        const parsed = JSON.parse(saved);
        wizardData = { ...wizardData, ...parsed };
        addLog('Loaded configuration from previous session.');
      } catch (e) {
        console.error('Failed to load saved config', e);
      }
    }
  });

  function saveConfig() {
    localStorage.setItem('gmp_setup_config', JSON.stringify(wizardData));
    addLog('Configuration saved to local storage.');
  }

  function shareConfig() {
    const configStr = JSON.stringify(wizardData, null, 2);
    navigator.clipboard.writeText(configStr).then(() => {
      alert('Configuration copied to clipboard!');
      addLog('Configuration copied to clipboard.');
    });
  }

  const steps = [
    { id: 1, title: 'Environment Check', icon: '🔍' },
    { id: 2, title: 'Select Template', icon: '📦' },
    { id: 3, title: 'Configuration', icon: '⚙️' },
    { id: 4, title: 'Deployment', icon: '🚀' },
    { id: 5, title: 'Verification', icon: '✅' }
  ];

  function startAutoMode() {
    saveConfig();
    mode = 'auto';
    addLog('Starting Auto-Pilot Mode...');
    simulateProcess();
  }

  function startWizardMode() {
    saveConfig();
    mode = 'wizard';
    step = 1;
  }

  function nextStep() {
    if (step < 5) {
      step++;
      saveConfig(); // Auto-save on step change
      if (step === 4) simulateProcess();
    }
  }

  function prevStep() {
    if (step > 1) step--;
  }

  function addLog(msg) {
    logs = [...logs, { time: new Date().toLocaleTimeString(), msg }];
    // Auto-scroll
    setTimeout(() => {
      const el = document.getElementById('log-container');
      if (el) el.scrollTop = el.scrollHeight;
    }, 10);
  }

  function simulateProcess() {
    progress = 0;
    logs = [];
    isComplete = false;
    
    const tasks = [
      { msg: 'Checking Docker environment...', duration: 1000 },
      { msg: 'Validating API Keys...', duration: 800 },
      { msg: 'Pulling latest images...', duration: 1500 },
      { msg: 'Provisioning Database...', duration: 1200 },
      { msg: 'Starting Crawler Service...', duration: 1000 },
      { msg: 'Running Smoke Tests...', duration: 1500 },
      { msg: 'Verifying Endpoints...', duration: 800 },
      { msg: 'Deployment Successful!', duration: 500 }
    ];

    let currentTask = 0;

    function runTask() {
      if (currentTask >= tasks.length) {
        isComplete = true;
        progress = 100;
        if (mode === 'wizard') step = 5;
        return;
      }

      const task = tasks[currentTask];
      addLog(task.msg);
      
      // Update progress smoothly
      const stepSize = 100 / tasks.length;
      progress = (currentTask + 1) * stepSize;

      setTimeout(() => {
        currentTask++;
        runTask();
      }, task.duration);
    }

    runTask();
  }

  function downloadReport() {
    const text = `Deployment Report\nDate: ${new Date().toLocaleString()}\nStatus: Success\nLogs:\n${logs.map(l => `[${l.time}] ${l.msg}`).join('\n')}`;
    const blob = new Blob([text], { type: 'text/plain' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'deployment_report.txt';
    a.click();
  }
</script>

<div class="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-sm" transition:fade>
  <div class="w-full max-w-4xl bg-gray-900 border border-cyan-500/30 rounded-xl shadow-2xl overflow-hidden flex flex-col h-[600px]" transition:fly={{ y: 20 }}>
    
    <!-- Header -->
    <div class="p-6 border-b border-gray-800 flex justify-between items-center bg-gray-900/50">
      <div>
        <h2 class="text-2xl font-bold text-cyan-400 tracking-wider">SYSTEM DEPLOYMENT WIZARD</h2>
        <p class="text-gray-400 text-sm mt-1">Zero-Threshold Automated Configuration</p>
      </div>
      <button on:click={onClose} class="text-gray-500 hover:text-white transition-colors text-2xl">&times;</button>
    </div>

    <!-- Content -->
    <div class="flex-1 p-8 overflow-y-auto relative">
      
      {#if mode === 'selection'}
        <div class="grid grid-cols-2 gap-8 h-full items-center" in:fade>
          <!-- Auto Pilot -->
          <button on:click={startAutoMode} class="group relative h-64 bg-gray-800/50 hover:bg-cyan-900/20 border border-gray-700 hover:border-cyan-500 rounded-xl p-6 transition-all duration-300 flex flex-col items-center justify-center text-center">
            <div class="text-6xl mb-4 group-hover:scale-110 transition-transform">🤖</div>
            <h3 class="text-xl font-bold text-white mb-2">Auto Pilot Mode</h3>
            <p class="text-gray-400 text-sm">One-click full automation. Sit back and relax while we handle everything.</p>
            <div class="absolute bottom-6 opacity-0 group-hover:opacity-100 transition-opacity text-cyan-400 font-mono text-sm">>> INITIALIZE</div>
          </button>

          <!-- Wizard Mode -->
          <button on:click={startWizardMode} class="group relative h-64 bg-gray-800/50 hover:bg-purple-900/20 border border-gray-700 hover:border-purple-500 rounded-xl p-6 transition-all duration-300 flex flex-col items-center justify-center text-center">
            <div class="text-6xl mb-4 group-hover:scale-110 transition-transform">👨‍✈️</div>
            <h3 class="text-xl font-bold text-white mb-2">Step-by-Step Wizard</h3>
            <p class="text-gray-400 text-sm">Visual guide with customization options. Perfect for first-time setup.</p>
            <div class="absolute bottom-6 opacity-0 group-hover:opacity-100 transition-opacity text-purple-400 font-mono text-sm">>> CONFIGURE</div>
          </button>
        </div>

      {:else if mode === 'auto'}
        <div class="flex flex-col items-center justify-center h-full space-y-8" in:fade>
          <!-- Circular Progress -->
          <div class="relative w-48 h-48">
            <svg class="w-full h-full" viewBox="0 0 100 100">
              <circle class="text-gray-700 stroke-current" stroke-width="8" cx="50" cy="50" r="40" fill="transparent"></circle>
              <circle class="text-cyan-500 progress-ring__circle stroke-current transition-all duration-500" stroke-width="8" stroke-linecap="round" cx="50" cy="50" r="40" fill="transparent" stroke-dasharray="251.2" stroke-dashoffset={251.2 - (251.2 * progress) / 100}></circle>
            </svg>
            <div class="absolute inset-0 flex items-center justify-center flex-col">
              <span class="text-3xl font-bold text-white">{Math.round(progress)}%</span>
              <span class="text-xs text-cyan-400 animate-pulse">{isComplete ? 'COMPLETE' : 'PROCESSING'}</span>
            </div>
          </div>

          <!-- Logs -->
          <div id="log-container" class="w-full max-w-2xl bg-black/50 rounded-lg p-4 h-48 overflow-y-auto font-mono text-sm border border-gray-800">
            {#each logs as log (log.time + log.msg)}
              <div class="mb-1">
                <span class="text-gray-500">[{log.time}]</span>
                <span class="text-green-400 ml-2">>> {log.msg}</span>
              </div>
            {/each}
            {#if isComplete}
               <div class="mt-2 text-cyan-400 font-bold border-t border-gray-700 pt-2">
                 [SYSTEM] All systems operational. Ready for launch.
               </div>
            {/if}
          </div>

          {#if isComplete}
            <div class="flex gap-4">
               <button on:click={downloadReport} class="px-6 py-2 bg-gray-700 hover:bg-gray-600 rounded text-white font-medium transition-colors">Download Report</button>
               <button on:click={onClose} class="px-6 py-2 bg-cyan-600 hover:bg-cyan-500 rounded text-white font-medium transition-colors">Enter Dashboard</button>
            </div>
          {/if}
        </div>

      {:else if mode === 'wizard'}
        <!-- Stepper -->
        <div class="mb-8 flex justify-between relative px-10">
           <div class="absolute top-1/2 left-0 w-full h-1 bg-gray-800 -z-10 transform -translate-y-1/2"></div>
           <div class="absolute top-1/2 left-0 h-1 bg-purple-600 -z-10 transform -translate-y-1/2 transition-all duration-500" style="width: {(step - 1) / (steps.length - 1) * 100}%"></div>
           
           {#each steps as s (s.id)}
             <div class="flex flex-col items-center bg-gray-900 px-2">
               <div class="w-10 h-10 rounded-full flex items-center justify-center border-2 transition-all duration-300 {step >= s.id ? 'border-purple-500 bg-purple-900/50 text-white' : 'border-gray-600 bg-gray-800 text-gray-500'}">
                 {s.icon}
               </div>
               <span class="text-xs mt-2 {step >= s.id ? 'text-purple-400' : 'text-gray-600'}">{s.title}</span>
             </div>
           {/each}
        </div>

        <div class="h-[300px] bg-gray-800/30 rounded-xl p-6 border border-gray-700 relative">
           {#if step === 1}
             <h3 class="text-xl font-bold text-white mb-4">Environment Check</h3>
             <div class="space-y-4">
                <div class="flex items-center justify-between p-4 bg-gray-800 rounded border border-green-500/30">
                   <div class="flex items-center gap-3">
                      <div class="text-green-500">✔</div>
                      <div>
                        <div class="text-white font-medium">Node.js Environment</div>
                        <div class="text-gray-400 text-xs">v20.10.0 Detected</div>
                      </div>
                   </div>
                   <span class="text-green-500 text-sm">Ready</span>
                </div>
                <div class="flex items-center justify-between p-4 bg-gray-800 rounded border border-green-500/30">
                   <div class="flex items-center gap-3">
                      <div class="text-green-500">✔</div>
                      <div>
                        <div class="text-white font-medium">Docker Daemon</div>
                        <div class="text-gray-400 text-xs">Running (v24.0.0)</div>
                      </div>
                   </div>
                   <span class="text-green-500 text-sm">Ready</span>
                </div>
             </div>
           {:else if step === 2}
             <h3 class="text-xl font-bold text-white mb-4">Select Deployment Template</h3>
             <div class="grid grid-cols-3 gap-4">
                {#each ['News Crawler', 'Social Monitor', 'Full Suite'] as t (t)}
                  <button 
                    class="p-4 rounded-lg border-2 transition-all text-left {wizardData.template === t ? 'border-purple-500 bg-purple-900/20' : 'border-gray-700 hover:border-gray-500'}"
                    on:click={() => wizardData.template = t}
                  >
                    <div class="font-bold text-white mb-1">{t}</div>
                    <div class="text-xs text-gray-400">Standard configuration for {t.toLowerCase()}.</div>
                  </button>
                {/each}
             </div>
           {:else if step === 3}
             <h3 class="text-xl font-bold text-white mb-4">Configuration</h3>
             <div class="space-y-6">
                <div>
                  <label class="block text-gray-400 text-sm mb-2">Crawler Intensity (Concurrent Requests)</label>
                  <input type="range" min="1" max="100" bind:value={wizardData.intensity} class="w-full h-2 bg-gray-700 rounded-lg appearance-none cursor-pointer accent-purple-500">
                  <div class="flex justify-between text-xs text-gray-500 mt-1">
                     <span>Safe (1)</span>
                     <span class="text-purple-400">{wizardData.intensity}</span>
                     <span>Aggressive (100)</span>
                  </div>
                </div>
                <div>
                   <label class="block text-gray-400 text-sm mb-2">Target Region</label>
                   <div class="flex gap-2">
                      {#each ['Global', 'Asia', 'Americas', 'EMEA'] as r (r)}
                         <button 
                           class="px-3 py-1 rounded-full text-sm border {wizardData.region === r ? 'bg-purple-600 border-purple-600 text-white' : 'border-gray-600 text-gray-400'}"
                           on:click={() => wizardData.region = r}
                         >
                           {r}
                         </button>
                      {/each}
                   </div>
                </div>
             </div>
           {:else if step === 4}
             <div class="flex flex-col items-center justify-center h-full">
                <h3 class="text-xl font-bold text-white mb-4">Executing Deployment...</h3>
                <div class="w-full max-w-md bg-gray-900 rounded-full h-4 overflow-hidden">
                   <div class="bg-purple-500 h-full transition-all duration-300" style="width: {progress}%"></div>
                </div>
                <div class="mt-4 font-mono text-sm text-green-400">
                   > {logs.length > 0 ? logs[logs.length-1].msg : 'Initializing...'}
                </div>
             </div>
           {:else if step === 5}
             <div class="flex flex-col items-center justify-center h-full text-center">
                <div class="text-6xl mb-4">🎉</div>
                <h3 class="text-2xl font-bold text-white mb-2">Deployment Complete</h3>
                <p class="text-gray-400 mb-6">Your system is now live and monitoring {wizardData.template}.</p>
                <div class="flex gap-4">
                   <button on:click={downloadReport} class="px-6 py-2 bg-gray-700 hover:bg-gray-600 rounded text-white">Download Report</button>
                   <button on:click={shareConfig} class="px-6 py-2 bg-gray-700 hover:bg-gray-600 rounded text-white flex items-center gap-2">
                     <span>🔗</span> Share Config
                   </button>
                   <button on:click={onClose} class="px-6 py-2 bg-purple-600 hover:bg-purple-500 rounded text-white shadow-lg shadow-purple-900/50">Launch Dashboard</button>
                </div>
             </div>
           {/if}
        </div>

        <!-- Wizard Navigation -->
        {#if step < 4}
          <div class="mt-6 flex justify-between">
             <button on:click={prevStep} class="px-6 py-2 text-gray-400 hover:text-white disabled:opacity-50" disabled={step === 1}>Back</button>
             <button on:click={nextStep} class="px-6 py-2 bg-white text-black font-bold rounded hover:bg-gray-200 transition-colors">
               {step === 3 ? 'Deploy Now' : 'Next Step'}
             </button>
          </div>
        {/if}

      {/if}
    </div>
  </div>
</div>

<style>
  /* Custom scrollbar for logs */
  #log-container::-webkit-scrollbar {
    width: 6px;
  }
  #log-container::-webkit-scrollbar-track {
    background: rgba(0,0,0,0.3);
  }
  #log-container::-webkit-scrollbar-thumb {
    background: #374151;
    border-radius: 3px;
  }
  
  .progress-ring__circle {
     transform: rotate(-90deg);
     transform-origin: 50% 50%;
  }
</style>
