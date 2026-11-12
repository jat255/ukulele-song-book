import {test, expect} from '@playwright/test';

test('exports the whole library and one standalone arrangement', async ({page}) => {
  await page.goto('/');
  await page.getByLabel('Password').fill('synthetic test password');
  await page.getByRole('button', {name:'Sign in'}).click();
  await page.locator('.export-actions > summary').first().click();
  await page.getByRole('button', {name:'Export library'}).click();
  await expect(page.getByRole('link', {name:'Download library export'})).toBeVisible();
  const first = page.getByRole('listitem').filter({has:page.getByRole('link', {name:'Browser Test', exact:true})}).first();
  await first.locator('.export-actions > summary').click();
  await first.getByRole('button', {name:'Export ChordPro'}).click();
  const ready = first.getByRole('link', {name:'Download ChordPro'});
  await expect(ready).toBeVisible();
  const download = page.waitForEvent('download');
  await ready.click();
  expect((await download).suggestedFilename()).toBe('song.chordpro');
});
