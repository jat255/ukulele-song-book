import {test, expect} from '@playwright/test';
import {readFileSync} from 'node:fs';

test('signs in, accesses a retained original, and revokes access on logout', async ({page}) => {
  const sourceId = readFileSync('/private/tmp/songbook-auth-e2e-source-id', 'utf8');
  await page.goto('/');
  await expect(page.getByRole('heading', {name:'Sign in'})).toBeVisible();
  expect(await page.evaluate(async id => (await fetch(`/api/sources/${id}/original`)).status, sourceId)).toBe(401);
  await page.getByLabel('Password').fill('synthetic test password');
  await page.getByRole('button', {name:'Sign in'}).click();
  await expect(page.getByRole('heading', {name:'Songbook'})).toBeVisible();
  expect(await page.evaluate(async id => (await fetch(`/api/sources/${id}/original`)).status, sourceId)).toBe(200);
  await page.getByRole('button', {name:'Sign out'}).click();
  await expect(page.getByRole('heading', {name:'Sign in'})).toBeVisible();
  expect(await page.evaluate(async id => (await fetch(`/api/sources/${id}/original`)).status, sourceId)).toBe(401);
});
