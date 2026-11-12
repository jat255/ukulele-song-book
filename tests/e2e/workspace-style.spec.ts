import {test, expect} from '@playwright/test';

test('library workspace stays usable and styled at desktop and phone widths', async ({page}) => {
  await page.goto('/');
  await page.getByLabel('Password').fill('synthetic test password');
  await page.getByRole('button', {name:'Sign in'}).click();
  await expect(page.getByRole('heading', {name:'Library'})).toBeVisible();
  await expect(page.locator('main')).toHaveClass(/workspace/);
  await expect(page.locator('nav')).toHaveCSS('display', 'flex');
  for (const width of [1200, 390]) {
    await page.setViewportSize({width, height:800});
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
    await expect(page.getByLabel('Search')).toBeVisible();
  }
});
