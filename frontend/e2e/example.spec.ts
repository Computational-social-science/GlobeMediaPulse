import { test, expect } from '@playwright/test';
import { DATA } from '../src/lib/data.js';

const env =
  (globalThis as unknown as { process?: { env?: Record<string, string | undefined> } }).process?.env || {};

const baseUrl = env.PLAYWRIGHT_BASE_URL || 'http://localhost:4173/';

test('system monitor controls fits without scroll and logs are scrollable', async ({ page }) => {
  await page.goto(baseUrl, { waitUntil: 'domcontentloaded' });
  await page.waitForSelector('.maplibregl-map', { timeout: 30000 });
  await page.locator('.z-\\[10000\\]').waitFor({ state: 'detached', timeout: 60000 });

  await page.locator('aside nav button').first().click();

  const monitor = page.getByRole('dialog', { name: 'Status' });
  await expect(monitor).toBeVisible();

  const body = monitor.locator('.fw-body');
  const bodyScroll = await body.evaluate((el) => ({
    clientHeight: el.clientHeight,
    scrollHeight: el.scrollHeight
  }));
  expect(bodyScroll.scrollHeight).toBeLessThanOrEqual(bodyScroll.clientHeight);

  const logsPanel = monitor.locator('.sidebar-panel-sub').filter({ hasText: 'Logs' }).first();
  await expect(logsPanel).toBeVisible();

  const logsScroll = logsPanel.locator('.overflow-auto').first();
  const overflowY = await logsScroll.evaluate((el) => getComputedStyle(el).overflowY);
  expect(overflowY).toBe('auto');
});

test('territory boundaries render and header stats load', async ({ page }) => {
  await page.route('**/api/map-data', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ total_sources: 123 })
    });
  });

  await page.route('**/api/metadata/countries', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        COUNTRIES: [
          { code: 'GRL', code_alpha2: 'GL', name: 'Greenland', lat: 72.0, lng: -40.0, region: 'Americas' },
          { code: 'GUM', code_alpha2: 'GU', name: 'Guam', lat: 13.4443, lng: 144.7937, region: 'Oceania' },
          { code: 'BMU', code_alpha2: 'BM', name: 'Bermuda', lat: 32.3078, lng: -64.7505, region: 'Americas' }
        ]
      })
    });
  });

  await page.route('**/api/metadata/geojson', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        type: 'FeatureCollection',
        features: [
          {
            type: 'Feature',
            id: 'GRL',
            properties: { name: 'Greenland' },
            geometry: {
              type: 'Polygon',
              coordinates: [[[-50, 60], [-10, 60], [-10, 84], [-50, 84], [-50, 60]]]
            }
          }
        ]
      })
    });
  });

  await page.goto(baseUrl, { waitUntil: 'domcontentloaded' });
  await page.waitForSelector('.maplibregl-map', { timeout: 30000 });
  await page.locator('.z-\\[10000\\]').waitFor({ state: 'detached', timeout: 60000 });

  await page.locator('aside nav button').first().click();
  const monitor = page.getByRole('dialog', { name: 'Status' });
  await expect(monitor).toBeVisible();
  await expect(monitor.getByText('SRC')).toBeVisible();
  await expect(monitor.getByText('123')).toBeVisible();

  await page.waitForFunction(() => {
    const map = (window as unknown as {
      map?: {
        getLayer?: (id: string) => unknown;
        queryRenderedFeatures?: (opts: { layers: string[] }) => unknown;
      };
    }).map;
    if (!map) return false;
    if (!map.getLayer || !map.getLayer('country-layer')) return false;
    try {
      const features = map.queryRenderedFeatures
        ? map.queryRenderedFeatures({ layers: ['country-layer'] })
        : null;
      return Array.isArray(features) && features.length > 0;
    } catch {
      return false;
    }
  }, { timeout: 30000 });

  const hasGreenland = await page.evaluate(() => {
    const map = (window as unknown as {
      map?: {
        queryRenderedFeatures?: (opts: { layers: string[] }) => unknown;
      };
    }).map;
    if (!map?.queryRenderedFeatures) return false;
    const rawFeatures = map.queryRenderedFeatures({ layers: ['country-layer'] });
    if (!Array.isArray(rawFeatures)) return false;

    const codes = rawFeatures
      .map((feature) => {
        if (!feature || typeof feature !== 'object') return null;
        const typed = feature as { properties?: Record<string, unknown>; id?: unknown };
        const code = typed.properties?.code;
        if (typeof code === 'string') return code;
        if (typeof typed.id === 'string') return typed.id;
        return null;
      })
      .filter((code): code is string => typeof code === 'string' && code.length > 0)
      .map((code) => code.toUpperCase());

    return codes.includes('GRL');
  });
  expect(hasGreenland).toBeTruthy();
});

test('flag icons render for news cards', async ({ page }) => {
  await page.goto(baseUrl, { waitUntil: 'domcontentloaded' });
  await page.waitForSelector('.maplibregl-map', { timeout: 30000 });
  await page.locator('.z-\\[10000\\]').waitFor({ state: 'detached', timeout: 60000 });

  await page.evaluate(() => {
    const w = window as unknown as {
      __createNewsCardElement?: (article: Record<string, unknown>) => HTMLElement;
    };
    if (!w.__createNewsCardElement) throw new Error('Missing __createNewsCardElement');
    const el = w.__createNewsCardElement({
      country_code: 'USA',
      source_domain: 'example.com',
      source_name: 'Example',
      tier: 'Tier-1',
      title: 'Test headline'
    });
    el.setAttribute('data-testid', 'test-news-card');
    document.body.appendChild(el);
  });

  const flag = page.locator('[data-testid="test-news-card"] span.fi.fi-us');
  await expect(flag).toBeVisible();
  await expect(flag).toHaveClass(/(^|\s)gmp-flag(\s|$)/);
});

test('real-time floating news card renders flag and media profile', async ({ page }) => {
  await page.addInitScript(() => {
    class NoopWebSocket {
      static CONNECTING = 0;
      static OPEN = 1;
      static CLOSING = 2;
      static CLOSED = 3;
      readyState = NoopWebSocket.CLOSED;
      onopen: ((ev: Event) => unknown) | null = null;
      onmessage: ((ev: MessageEvent) => unknown) | null = null;
      onclose: ((ev: CloseEvent) => unknown) | null = null;
      onerror: ((ev: Event) => unknown) | null = null;
      constructor() {
        queueMicrotask(() => {
          this.onclose?.(new CloseEvent('close'));
        });
      }
      close() {}
      send() {}
      addEventListener() {}
      removeEventListener() {}
      dispatchEvent() {
        return false;
      }
    }
    (window as unknown as { WebSocket?: unknown }).WebSocket = NoopWebSocket as unknown as WebSocket;
  });

  await page.route('**/api/map-data', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ total_sources: 1 })
    });
  });

  await page.route('**/api/metadata/countries', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        COUNTRIES: [
          { code: 'QAT', code_alpha2: 'QA', name: 'Qatar', lat: 25.2854, lng: 51.531 },
          { code: 'USA', code_alpha2: 'US', name: 'United States', lat: 38.9072, lng: -77.0369 }
        ]
      })
    });
  });

  await page.route('**/health/full', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ status: 'ok' })
    });
  });

  await page.route('**/api/stats/brain', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({})
    });
  });

  await page.route('**/api/media/sources', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify([
        { domain: 'aljazeera.com', name: 'Al Jazeera', logo_url: null, tier: 'Tier-0', country_code: 'QAT' }
      ])
    });
  });

  await page.route('**/api/stats/heatmap', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify([])
    });
  });

  await page.route('**/api/metadata/geojson', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ type: 'FeatureCollection', features: [] })
    });
  });

  await page.goto(baseUrl, { waitUntil: 'domcontentloaded' });
  await page.waitForSelector('.maplibregl-map', { timeout: 30000 });
  await page.locator('.z-\\[10000\\]').waitFor({ state: 'detached', timeout: 60000 });

  await page.waitForFunction(() => {
    const map = (window as unknown as { map?: { loaded?: () => boolean } }).map;
    return Boolean(map?.loaded?.());
  }, { timeout: 30000 });

  await page.waitForFunction(() => {
    const w = window as unknown as {
      __createNewsCardElement?: (article: Record<string, unknown>) => HTMLElement;
    };
    if (!w.__createNewsCardElement) return false;
    const el = w.__createNewsCardElement({
      country_code: 'QAT',
      source_domain: 'aljazeera.com',
      source_name: 'Fallback Name',
      tier: 'Tier-0',
      title: 'Preflight'
    });
    const hasFlag = Boolean(el.querySelector('span.fi.fi-qa'));
    const header = el.querySelector('h4')?.textContent?.trim();
    return hasFlag && header === 'Al Jazeera';
  }, { timeout: 10000 });

  await page.evaluate(() => {
    const w = window as unknown as { __emitNewsEvent?: (article: Record<string, unknown>) => void };
    if (!w.__emitNewsEvent) throw new Error('Missing __emitNewsEvent');
    w.__emitNewsEvent({
      country_code: 'QAT',
      source_domain: 'aljazeera.com',
      source_name: 'Fallback Name',
      tier: 'Tier-0',
      language: 'en',
      lat: 25.2854,
      lng: 51.531
    });
  });

  const marker = page.locator('.news-card-marker', { hasText: 'aljazeera.com' }).first();
  await expect(marker).toBeVisible({ timeout: 10000 });

  const flag = marker.locator('span.fi.fi-qa');
  await expect(flag).toBeVisible();
  await expect(flag).toHaveClass(/(^|\s)gmp-flag(\s|$)/);

  await expect(marker.locator('h4')).toHaveText('Al Jazeera');
  await expect(marker.getByRole('link', { name: 'aljazeera.com' })).toBeVisible();
  await expect(marker.getByText('EN')).toBeVisible();
});

test('country list includes key non-sovereign territories', async () => {
  const codes = new Set((DATA.COUNTRIES || []).map((c) => c.code));
  expect(codes.has('BMU')).toBeTruthy();
  expect(codes.has('GRL')).toBeTruthy();
  expect(codes.has('GUM')).toBeTruthy();
});
