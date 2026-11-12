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

test('sign-in uses a responsive songbook card and keeps errors visible',async({page})=>{
 await page.goto('/');
 await expect(page.locator('main')).toHaveClass(/auth-page/);
 for(const width of [1280,390,320]){
  await page.setViewportSize({width,height:700});await expect(page.getByLabel('Password')).toBeVisible();
  const card=await page.locator('.auth-card').boundingBox();expect(card!.x).toBeGreaterThanOrEqual(0);expect(card!.x+card!.width).toBeLessThanOrEqual(width);
 }
 await page.getByLabel('Password').fill('incorrect synthetic password');await page.getByRole('button',{name:'Sign in',exact:true}).click();
 await expect(page.getByRole('alert')).toContainText('Unable to sign in.');await expect(page.getByLabel('Password')).toHaveValue('');
 await page.screenshot({path:'.local/review/sign-in-phone.png'});
 await page.setViewportSize({width:1280,height:800});await page.screenshot({path:'.local/review/sign-in-desktop.png'});
});
