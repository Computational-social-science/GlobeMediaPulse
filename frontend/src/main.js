/**
 * Main Entry Point for the Svelte Application.
 * Mounts the App component to the DOM.
 */

import 'maplibre-gl/dist/maplibre-gl.css' // Import MapLibre GL styles
import 'flag-icons/css/flag-icons.min.css'
import '@/theme/windows-classic.css'
import '@/app.css' // Import global application styles
import * as Sentry from '@sentry/svelte'
import App from '@/App.svelte'
import { mount } from 'svelte'

const sentryDsn = (typeof import.meta !== 'undefined' && import.meta && import.meta.env && import.meta.env.VITE_SENTRY_DSN) ? import.meta.env.VITE_SENTRY_DSN : ''
if (sentryDsn) {
  Sentry.init({
    dsn: sentryDsn,
    integrations: [Sentry.browserTracingIntegration(), Sentry.replayIntegration()],
    tracesSampleRate: 1.0,
    replaysSessionSampleRate: 0.1,
    replaysOnErrorSampleRate: 1.0
  })
}

// Mount the main App component to the 'app' element in index.html
const app = mount(App, {
  target: /** @type {HTMLElement} */ (document.getElementById('app')),
})

export default app
