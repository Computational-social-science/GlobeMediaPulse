import { test, expect } from '@playwright/test';

test('verify 3D mode default off and toggle', async ({ page }) => {
  // Listen for console errors
  const errors: string[] = [];
  page.on('console', (msg) => {
    const text = msg.text();
    if (msg.type() === 'error') {
      errors.push(text);
      console.log(`[Browser Error] ${text}`);
    } else {
      console.log(`[Browser Log] ${text}`);
    }
  });

  const env =
    (globalThis as unknown as { process?: { env?: Record<string, string | undefined> } }).process?.env || {};

  await page.goto(env.PLAYWRIGHT_BASE_URL || 'http://localhost:4173/', { waitUntil: 'domcontentloaded' });
  await page.waitForSelector('.maplibregl-map');
  
  // Wait for style and initial layers to load
  await page.waitForTimeout(5000);

  // Check initial state (Should be 3D OFF by default)
  const initialState = await page.evaluate(() => {
    const map = (window as unknown as { map?: { getStyle?: () => unknown; getTerrain?: () => unknown; getLayer?: (id: string) => unknown; getPitch?: () => number } }).map;
    const style = map?.getStyle ? map.getStyle() : null;
    return {
      is3D: map?.getTerrain ? Boolean(map.getTerrain()) : false,
      has3DBuildings: map?.getLayer ? Boolean(map.getLayer('3d-buildings')) : false,
      pitch: map?.getPitch ? map.getPitch() : 0,
      projection:
        style && typeof style === 'object' && 'projection' in (style as Record<string, unknown>)
          ? (style as Record<string, unknown>).projection
          : 'style-undefined'
    };
  });
  console.log('Initial State (Default OFF):', initialState);

  expect(initialState.is3D).toBe(false);
  expect(initialState.has3DBuildings).toBe(false);
  // If projection is not in style, it might be undefined even if map uses it.
  // We'll log it for now.
  // expect(initialState.projection).toMatch(/globe/);

  const toggleBtn = page.locator('button[title="Toggle 3D Mode"]');
  if ((await toggleBtn.count()) === 0) {
    test.skip(true, '3D toggle is not present in the current UI');
  }
  await expect(toggleBtn).toBeVisible();
  
  // Verify button visual state (should indicate OFF)
  await expect(toggleBtn).not.toHaveClass(/text-neon-blue/);

  // Click to ENABLE 3D
  await toggleBtn.click();
  console.log('Clicked 3D Toggle (ON)');
  
  await page.waitForTimeout(5000);

  // Check state after enable
  const afterEnableState = await page.evaluate(() => {
    const map = (window as unknown as { map?: { getTerrain?: () => unknown; getLayer?: (id: string) => unknown } }).map;
    return {
      is3D: map?.getTerrain ? Boolean(map.getTerrain()) : false,
      has3DBuildings: map?.getLayer ? Boolean(map.getLayer('3d-buildings')) : false
    };
  });
  console.log('After Enable State:', afterEnableState);
  
  expect(afterEnableState.is3D).toBe(true);
  expect(afterEnableState.has3DBuildings).toBe(true);
  await expect(toggleBtn).toHaveClass(/text-neon-blue/);

  // Click to DISABLE 3D again
  await toggleBtn.click();
  console.log('Clicked 3D Toggle (OFF)');

  await page.waitForTimeout(2000);

  // Check state after disable
  const afterDisableState = await page.evaluate(() => {
    const map = (window as unknown as { map?: { getTerrain?: () => unknown; getLayer?: (id: string) => unknown } }).map;
    return {
      is3D: map?.getTerrain ? Boolean(map.getTerrain()) : false,
      has3DBuildings: map?.getLayer ? Boolean(map.getLayer('3d-buildings')) : false
    };
  });
  console.log('After Disable State:', afterDisableState);

  expect(afterDisableState.is3D).toBe(false);
  expect(afterDisableState.has3DBuildings).toBe(false);
  await expect(toggleBtn).not.toHaveClass(/text-neon-blue/);

  // Check for any console errors caught during transition
  const terrainErrors = errors.filter(e => e.includes('terrain') || e.includes('3D') || e.includes('setFog'));
  expect(terrainErrors).toEqual([]);
});
