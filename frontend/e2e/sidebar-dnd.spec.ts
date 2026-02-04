import { test, expect } from '@playwright/test';

const viewports = [
  { width: 1280, height: 720 },
  { width: 1920, height: 1080 }
];

for (const viewport of viewports) {
  test(`sidebar drag and drop works at ${viewport.width}x${viewport.height}`, async ({ page }) => {
    await page.setViewportSize(viewport);
    await page.goto('/');

    const collapseBtn = page.locator('button[title="Collapse Sidebar"]');
    if (await collapseBtn.count()) {
      await collapseBtn.click();
    }

    await page.locator('button[title="Expand Sidebar"]').click();

    const autoheal = page.locator('[data-testid="sidebar-item-autoheal"]');
    const newGroup = page.locator('[data-testid="sidebar-new-group"]');
    await autoheal.dragTo(newGroup);

    const groups = page.locator('[data-testid^="sidebar-group-"]');
    await expect(groups).toHaveCount(2);
    const newGroupItems = groups.nth(1).locator('xpath=following-sibling::*[1]');
    await expect(newGroupItems.getByText('Autoheal', { exact: true })).toBeVisible();
  });
}
