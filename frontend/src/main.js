/**
 * Main Entry Point for the Svelte Application.
 * Mounts the App component to the DOM.
 */

import 'maplibre-gl/dist/maplibre-gl.css' // Import MapLibre GL styles
import './app.css' // Import global application styles
import App from './App.svelte'
import { mount } from 'svelte'

// Mount the main App component to the 'app' element in index.html
const app = mount(App, {
  target: /** @type {HTMLElement} */ (document.getElementById('app')),
})

export default app
