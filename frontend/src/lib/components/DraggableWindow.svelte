<script>
  import { onMount, createEventDispatcher } from 'svelte';
  import { scale } from 'svelte/transition';
  import { quintOut } from 'svelte/easing';
  import { windowState } from '../stores.js';

  // Component Props
  /** @type {string} */
  export let id; // Unique identifier for the window
  export let title = 'WINDOW'; // Title displayed in the header
  export let icon = '⬜'; // Icon displayed in the header
  export let initialX = 100; // Initial X position
  export let initialY = 100; // Initial Y position
  export let width = 'auto'; // Window width
  export let height = 'auto'; // Window height

  /** @type {HTMLElement} */
  let element;
  let isDragging = false;
  let dragOffset = { x: 0, y: 0 };

  const dispatch = createEventDispatcher();

  // Initialize global window state if not present
  onMount(() => {
    windowState.update(s => {
      /** @type {any} */
      const state = s;
      if (!state[id]) {
        return {
          ...s,
          [id]: { visible: true, minimized: false, maximized: false, position: { x: initialX, y: initialY } }
        };
      }
      return s;
    });
  });

  // Reactive access to this window's state
  // @ts-ignore
  $: state = $windowState[id] || { visible: false, minimized: false, maximized: false, position: { x: initialX, y: initialY } };

  /** 
   * Initiates the drag operation.
   * @param {MouseEvent} e 
   */
  function startDrag(e) {
    // @ts-ignore
    if (state.maximized) return; // Cannot drag maximized windows
    isDragging = true;
    // @ts-ignore
    dragOffset.x = e.clientX - state.position.x;
    // @ts-ignore
    dragOffset.y = e.clientY - state.position.y;
    
    window.addEventListener('mousemove', handleDrag);
    window.addEventListener('mouseup', stopDrag);
  }

  /** 
   * Updates window position during drag.
   * @param {MouseEvent} e 
   */
  function handleDrag(e) {
    if (!isDragging) return;
    
    const newX = e.clientX - dragOffset.x;
    const newY = e.clientY - dragOffset.y;
    
    windowState.update(s => {
      /** @type {any} */
      const state = s;
      return {
        ...state,
        [id]: { ...state[id], position: { x: newX, y: newY } }
      };
    });
  }

  function stopDrag() {
    isDragging = false;
    window.removeEventListener('mousemove', handleDrag);
    window.removeEventListener('mouseup', stopDrag);
  }

  function toggleMinimize() {
    windowState.update(s => {
      /** @type {any} */
      const state = s;
      return {
        ...state,
        [id]: { ...state[id], minimized: !state[id].minimized }
      };
    });
  }

  function closeWindow() {
    windowState.update(s => {
      /** @type {any} */
      const state = s;
      return {
        ...state,
        [id]: { ...state[id], visible: false }
      };
    });
  }

  /**
   * Brings this window to the front by increasing its Z-Index.
   */
  export function bringToFront() {
    windowState.update(s => {
      // Find max z-index among all windows
      let maxZ = 10;
      Object.values(s).forEach(w => {
          // @ts-ignore
          if (w.zIndex && w.zIndex > maxZ) maxZ = w.zIndex;
      });
      
      /** @type {any} */
      const state = s;
      return {
        ...state,
        [id]: { ...state[id], zIndex: maxZ + 1 }
      };
    });
    dispatch('focus');
  }
</script>

{#if state.visible}
  <!-- svelte-ignore a11y-no-static-element-interactions -->
  <div 
    bind:this={element}
    class="fixed bg-[#050a14]/85 backdrop-blur-2xl border border-white/15 ring-1 ring-white/5 shadow-[0_10px_50px_rgba(0,0,0,0.8)] rounded-xl overflow-hidden flex flex-col transition-shadow duration-300 pointer-events-auto"
    class:ring-neon-blue={isDragging}
    class:shadow-[0_0_30px_rgba(0,243,255,0.15)]={isDragging}
    style="top: {state.position.y}px; left: {state.position.x}px; width: {width}; height: {height}; z-index: {state.zIndex || 10}; transform-origin: top left;"
    in:scale={{duration: 300, easing: quintOut, start: 0.9, opacity: 0}}
    on:mousedown={bringToFront}
  >
    <!-- Header -->
    <div 
      class="h-11 bg-gradient-to-r from-white/10 via-white/5 to-transparent border-b border-white/10 flex items-center justify-between px-4 cursor-move select-none relative overflow-hidden"
      on:mousedown={startDrag}
    >
      <!-- Header Highlight Line -->
      <div class="absolute top-0 left-0 w-full h-[1px] bg-gradient-to-r from-transparent via-white/20 to-transparent"></div>

      <div class="flex items-center gap-3 text-cyan-400 font-mono text-sm tracking-widest relative z-10">
        <span class="text-lg opacity-80 drop-shadow-[0_0_5px_rgba(34,211,238,0.5)]">{icon}</span>
        <span class="font-bold drop-shadow-md">{title}</span>
      </div>
      <div class="flex items-center gap-2">
        <button 
          class="w-6 h-6 flex items-center justify-center rounded hover:bg-white/10 text-gray-400 hover:text-white transition-colors"
          on:click={toggleMinimize}
        >
          {state.minimized ? '□' : '_'}
        </button>
        <button 
          class="w-6 h-6 flex items-center justify-center rounded hover:bg-red-500/20 text-gray-400 hover:text-red-400 transition-colors"
          on:click={closeWindow}
        >
          ✕
        </button>
      </div>
    </div>

    <!-- Content -->
    {#if !state.minimized}
      <div class="flex-1 overflow-auto bg-transparent p-4 min-h-[200px] max-h-[60vh] text-gray-300 font-mono text-sm">
        <slot></slot>
      </div>
    {/if}
  </div>
{/if}
