import { test, expect } from '@playwright/test';

async function getSidebarItemOrder(page: import('@playwright/test').Page) {
  return await page.evaluate(() => {
    const nav = document.querySelector('aside nav');
    if (!nav) return [];
    const items = Array.from(nav.querySelectorAll('button[data-testid^="sidebar-item-"]'));
    return items
      .map((el) => el.getAttribute('data-testid') || '')
      .filter((v) => v.length > 0);
  });
}

async function getSidebarConfigFromStorage(page: import('@playwright/test').Page) {
  return await page.evaluate(() => {
    const raw = window.localStorage.getItem('sidebarConfig');
    return raw ? JSON.parse(raw) : null;
  });
}

test('sidebar reorder updates immediately (desktop drag events)', async ({ page }) => {
  await page.goto('/', { waitUntil: 'domcontentloaded' });

  const collapseBtn = page.locator('button[title="Collapse Sidebar"]');
  if (await collapseBtn.count()) {
    await collapseBtn.click();
  }
  await page.locator('button[title="Expand Sidebar"]').click();

  const status = page.locator('[data-testid="sidebar-item-status"]').first();
  const autoheal = page.locator('[data-testid="sidebar-item-autoheal"]').first();

  const before = await getSidebarItemOrder(page);
  await autoheal.dragTo(status, { targetPosition: { x: 6, y: 6 } });
  await page.waitForTimeout(100);
  const after = await getSidebarItemOrder(page);

  expect(after).not.toEqual(before);
  await expect
    .poll(async () => {
      const cfg = await getSidebarConfigFromStorage(page);
      const items = cfg?.groups?.[0]?.items || [];
      const iAutoheal = items.indexOf('autoheal');
      const iGde = items.indexOf('gde');
      return { iAutoheal, iGde };
    })
    .toEqual(expect.objectContaining({ iAutoheal: 0, iGde: 2 }));
});

test('sidebar reorder works on touch via pointer events', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto('/', { waitUntil: 'domcontentloaded' });

  const collapseBtn = page.locator('button[title="Collapse Sidebar"]');
  if (await collapseBtn.count()) {
    await collapseBtn.click();
  }
  await page.locator('button[title="Expand Sidebar"]').click();

  const autoheal = page.locator('[data-testid="sidebar-item-autoheal"]').first();
  const status = page.locator('[data-testid="sidebar-item-status"]').first();

  await page.evaluate(() => {
    const buttons = Array.from(document.querySelectorAll('button[data-dnd-item]')) as HTMLButtonElement[];
    for (const b of buttons) b.draggable = false;
  });

  const a = await autoheal.boundingBox();
  const b = await status.boundingBox();
  expect(a).not.toBeNull();
  expect(b).not.toBeNull();

  const startX = (a!.x + a!.width / 2) | 0;
  const startY = (a!.y + a!.height / 2) | 0;
  const endX = (b!.x + b!.width / 2) | 0;
  const endY = (b!.y + 6) | 0;

  await page.mouse.move(startX, startY);
  await page.mouse.down();
  await page.mouse.move(startX, startY - 40);
  await expect(page.locator('.sidebar-drag-ghost')).toBeVisible();
  await page.mouse.move(endX, endY, { steps: 12 });
  await page.mouse.up();

  await expect
    .poll(async () => {
      const cfg = await getSidebarConfigFromStorage(page);
      const items = cfg?.groups?.[0]?.items || [];
      return items[0] || null;
    })
    .toBe('autoheal');
});
