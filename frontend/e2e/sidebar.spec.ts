import { test, expect } from '@playwright/test';

test('sidebar collapse, expand, and panel navigation', async ({ page }) => {
  // Navigate to home
  await page.goto('/');

  const sidebar = page.locator('aside');
  
  // 1. Initial State: Collapsed
  // Based on App.svelte: let sidebarCollapsed = true;
  // Width should be 56px
  await expect(sidebar).toHaveCSS('width', '56px');

  // 2. Expand Sidebar
  // Button with title "Expand Sidebar"
  const expandBtn = page.locator('button[title="Expand Sidebar"]');
  await expandBtn.click();
  
  // Width should be 320px
  await expect(sidebar).toHaveCSS('width', '320px');

  // 3. Verify Content Visibility
  // "Globe Media Pulse" title should be visible
  await expect(page.getByText('Globe Media Pulse')).toBeVisible();

  // 4. Panel Navigation (GDE is default active)
  // Verify GDE panel content
  await expect(page.getByText('Geographic Diversity Entropy', { exact: false }).first()).toBeVisible();

  // 5. Toggle Status Panel
  // Find button with text "Status"
  const statusBtn = page.locator('button:has-text("Status")');
  // It might be expanded by default? let statusPanelExpanded = true;
  // If we click it, it should toggle.
  await statusBtn.click();
  // Wait a bit for transition/reactivity if any, though Svelte is fast.
  
  // 6. Collapse Sidebar
  const collapseBtn = page.locator('button[title="Collapse Sidebar"]');
  await collapseBtn.click();
  await expect(sidebar).toHaveCSS('width', '56px');
});
