import {test, expect} from '@playwright/test';

test('reviews and accepts a direct synthetic import', async ({page}) => {
  await page.goto('/imports');
  await page.getByLabel('Password').fill('synthetic test password');
  await page.getByRole('button', {name:'Sign in'}).click();
  await page.getByLabel('Choose source').setInputFiles({name:'song.cho', mimeType:'text/plain', buffer:Buffer.from('{title: Test}\n[C]Hello')});
  await page.getByRole('button', {name:'Import source'}).click();
  await expect(page.getByLabel('ChordPro draft')).toHaveValue('{title: Test}\n[C]Hello', {timeout:15000});
  await page.getByLabel('ChordPro draft').fill('{title: Test}\n[G]Reviewed');
  await page.getByRole('button', {name:'Save draft'}).click();
  await expect(page.getByText('Draft saved.')).toBeVisible();
  await page.reload();
  await expect(page.getByLabel('ChordPro draft')).toHaveValue('{title: Test}\n[G]Reviewed');
  await page.getByRole('button', {name:'Accept draft'}).click();
  await expect(page.getByText('Arrangement accepted')).toBeVisible();
  const href = await page.getByRole('link', {name:'Open arrangement'}).getAttribute('href');
  const id = new URL(href!, 'http://localhost').searchParams.get('id');
  const saved = await page.evaluate(async id => (await fetch(`/api/arrangements/${id}`)).json(), id);
  expect(saved.source).toBe('{title: Test}\n[G]Reviewed');
});

test('reviews a selected page of a synthetic PDF', async ({page}) => {
  await page.goto('/imports');
  await page.getByLabel('Password').fill('synthetic test password');
  await page.getByRole('button', {name:'Sign in'}).click();
  await page.getByLabel('Choose source').setInputFiles('/private/tmp/songbook-auth-e2e-book.pdf');
  await page.getByLabel('Pages per song (commas between pages, semicolons between songs)').fill('2');
  await page.getByRole('button', {name:'Import source'}).click();
  await expect(page.getByAltText('Original page 2')).toBeVisible({timeout:15000});
  await expect(page.getByText('No text could be extracted; consult the original page')).toBeVisible();
  await page.getByLabel('ChordPro draft').fill('{title: Reviewed}\n[C]Synthetic');
  await page.getByRole('button', {name:'Save draft'}).click();
  await page.getByLabel('I reviewed the warnings and original').check();
  await page.getByRole('button', {name:'Accept draft'}).click();
  await expect(page.getByText('Arrangement accepted')).toBeVisible();
});
