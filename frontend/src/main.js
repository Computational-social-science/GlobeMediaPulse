/**
 * Main Entry Point for the Svelte Application.
 * Mounts the App component to the DOM.
 */

import 'maplibre-gl/dist/maplibre-gl.css' // Import MapLibre GL styles
import 'flag-icons/css/flag-icons.min.css'
import '@/app.css' // Import global application styles
import * as Sentry from "@sentry/svelte";
import App from '@/App.svelte'
import { mount } from 'svelte'

// Initialize Sentry for error monitoring
// TODO: Replace 'YOUR_SENTRY_DSN' with your actual DSN from Sentry dashboard
Sentry.init({
  dsn: "YOUR_SENTRY_DSN", 
  integrations: [
    Sentry.browserTracingIntegration(),
    Sentry.replayIntegration(),
  ],
  // Performance Monitoring
  tracesSampleRate: 1.0, // Capture 100% of the transactions
  // Session Replay
  replaysSessionSampleRate: 0.1, // This sets the sample rate at 10%. You may want to change it to 100% while in development and then sample at a lower rate in production.
  replaysOnErrorSampleRate: 1.0, // If you're not already sampling the entire session, change the sample rate to 100% when an error occurs.
});

// Mount the main App component to the 'app' element in index.html
const app = mount(App, {
  target: /** @type {HTMLElement} */ (document.getElementById('app')),
})

export default app
