import { test, expect } from '@playwright/test';

const baseUrl = process.env.PLAYWRIGHT_BASE_URL || 'http://localhost:5173/';

test('system monitor controls fits without scroll and logs are scrollable', async ({ page }) => {
  await page.goto(baseUrl, { waitUntil: 'networkidle' });

  await page.getByTitle('Toggle System Monitor').click();
  await page.getByRole('button', { name: 'Controls' }).click();

  const controls = page.getByTestId('system-controls');
  await expect(controls).toBeVisible();
  const controlsScroll = await controls.evaluate(el => ({
    clientHeight: el.clientHeight,
    scrollHeight: el.scrollHeight
  }));
  expect(controlsScroll.scrollHeight).toBeLessThanOrEqual(controlsScroll.clientHeight);

  await page.getByRole('button', { name: 'Logs' }).click();
  const logsContainer = page.getByTestId('system-logs');
  const logsScroll = page.getByTestId('system-logs-scroll');
  await expect(logsContainer).toBeVisible();
  const overflowY = await logsScroll.evaluate(el => getComputedStyle(el).overflowY);
  expect(overflowY).toBe('auto');
});
