import { test, expect } from '@playwright/test';

test.describe('Sidebar Visual Regression', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    // Wait for sidebar to be visible
    await page.waitForSelector('aside.sidebar-shell');
  });

  test('should match collapsed state snapshot', async ({ page }) => {
    // Ensure sidebar is collapsed (default for smaller screens, but let's force it if needed)
    // For 1280x720, it might be expanded. Let's check state.
    const sidebar = page.locator('aside.sidebar-shell');
    
    // Force collapse if expanded
    const width = await sidebar.evaluate((el) => el.style.width);
    if (width !== '56px') {
        await page.click('button[title="Collapse Sidebar"]');
    }
    await expect(sidebar).toHaveCSS('width', '56px');
    
    // Take screenshot
    await expect(sidebar).toHaveScreenshot('sidebar-collapsed.png', { maxDiffPixelRatio: 0.02 });
  });

  test('should match expanded state snapshot', async ({ page }) => {
    // Expand sidebar
    const sidebar = page.locator('aside.sidebar-shell');
    const width = await sidebar.evaluate((el) => el.style.width);
    if (width === '56px') {
        await page.click('button[title="Expand Sidebar"]');
    }
    await expect(sidebar).toHaveCSS('width', '320px');
    
    // Wait for animation
    await page.waitForTimeout(300);
    
    // Take screenshot
    await expect(sidebar).toHaveScreenshot('sidebar-expanded.png', { maxDiffPixelRatio: 0.02 });
  });

  test('should adhere to contrast guidelines', async ({ page }) => {
      // Basic automated accessibility check using axe-core could go here
      // For now, we verify specific styling classes
      const sidebar = page.locator('aside.sidebar-shell');
      await expect(sidebar).toHaveClass(/bg-slate-950/);
      await expect(sidebar).toHaveClass(/text-slate-100/); // Or inherited text color
  });
});
