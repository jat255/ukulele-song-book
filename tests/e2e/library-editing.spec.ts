import {test, expect} from '@playwright/test';
import {readFileSync} from 'node:fs';

test('preserves stale edits and restores a prior revision', async ({browser}) => {
  const id = readFileSync('/private/tmp/songbook-auth-e2e-arrangement-id', 'utf8');
  const a = await browser.newContext(); const b = await browser.newContext();
  const first = await a.newPage(); const second = await b.newPage();
  for (const page of [first,second]) {
    await page.goto(`http://127.0.0.1:4173/edit?id=${id}`);
    await page.getByLabel('Password').fill('synthetic test password');
    await page.getByRole('button', {name:'Sign in'}).click();
    await expect(page.getByLabel('ChordPro source')).toHaveValue(/\[C\]Original/);
  }
  await first.getByLabel('ChordPro source').fill('{title: Browser Test}\n[G]First\n{future: preserve}');
  await first.getByRole('button', {name:'Save arrangement'}).click();
  await expect(first.getByText('Arrangement saved')).toBeVisible();
  await second.getByLabel('ChordPro source').fill('{title: Browser Test}\n[D]Unsaved\n{future: preserve}');
  await second.getByRole('button', {name:'Save arrangement'}).click();
  await expect(second.getByText('Changed elsewhere')).toBeVisible();
  await expect(second.getByLabel('ChordPro source')).toHaveValue(/\[D\]Unsaved/);
  await first.getByRole('button', {name:'Restore previous revision'}).click();
  await expect(first.getByLabel('ChordPro source')).toHaveValue(/\[C\]Original/);
  await expect(first.getByLabel('ChordPro source')).toHaveValue(/\{future: preserve\}/);
  await a.close(); await b.close();
});
