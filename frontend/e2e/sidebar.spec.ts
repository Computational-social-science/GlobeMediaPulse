import { test, expect } from '@playwright/test';

test('sidebar collapse, expand, and panel navigation', async ({ page }) => {
  await page.goto('/');

  const sidebar = page.locator('aside');
  const nav = sidebar.locator('nav');

  const collapseBtn = page.locator('button[title="Collapse Sidebar"]');
  if (await collapseBtn.count()) {
    await collapseBtn.click();
  }
  await expect(sidebar).toHaveCSS('width', '56px');

  const expandBtn = page.locator('button[title="Expand Sidebar"]');
  await expandBtn.click();
  await expect(sidebar).toHaveCSS('width', '320px');

  await expect(page.getByText('Globe Media Pulse')).toBeVisible();

  await nav.locator('button[title="Geographic Diversity Entropy"]').click();
  const gdeDialog = page.getByRole('dialog', { name: 'Geographic Diversity Entropy' });
  await expect(gdeDialog).toBeVisible();
  await expect(gdeDialog.locator('.fw-title')).toHaveText('Geographic Diversity Entropy');
  await gdeDialog.getByRole('button', { name: 'Close' }).click();
  await expect(gdeDialog).toHaveCount(0);

  await nav.locator('button[title="Autoheal"]').click();
  const autohealDialog = page.getByRole('dialog', { name: 'Status & Autoheal' });
  await expect(autohealDialog).toBeVisible();
  await expect(autohealDialog.locator('.fw-title')).toHaveText('Status & Autoheal');
  await expect(autohealDialog.getByText('Safety', { exact: true })).toBeVisible();
  await autohealDialog.getByRole('button', { name: 'Close' }).click();
  await expect(autohealDialog).toHaveCount(0);

  await nav.getByRole('button', { name: /Status/i }).click();
  const statusDialog = page.getByRole('dialog', { name: 'Status & Autoheal' });
  await expect(statusDialog).toBeVisible();
  await expect(statusDialog.locator('.fw-title')).toHaveText('Status & Autoheal');
  await statusDialog.getByRole('button', { name: 'Close' }).click();
  await expect(statusDialog).toHaveCount(0);

  const collapseBtnFinal = page.locator('button[title="Collapse Sidebar"]');
  await collapseBtnFinal.click();
  await expect(sidebar).toHaveCSS('width', '56px');
});
