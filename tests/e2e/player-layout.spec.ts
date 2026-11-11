import {test, expect} from '@playwright/test';
import {readFileSync} from 'node:fs';

for (const viewport of [{width:1440,height:900}, {width:390,height:844}, {width:320,height:700}]) {
  test(`player keeps music visible at ${viewport.width}px`, async ({page}) => {
    const id = readFileSync('/private/tmp/songbook-auth-e2e-player-id','utf8');
    await page.setViewportSize(viewport);
    await page.goto(`/player?id=${id}`);
    await page.getByLabel('Password').fill('synthetic test password');
    await page.getByRole('button',{name:'Sign in'}).click();
    await expect(page.getByTestId('song')).toBeVisible();
    await expect(page.getByTestId('song')).toContainText('Player Test');
    await expect(page.getByRole('navigation',{name:'Songbook'})).toHaveCount(0);
    if (viewport.width < 700) {
      await page.getByRole('button',{name:'Tools'}).click();
      await expect(page.getByRole('complementary',{name:'Player tools'})).toBeVisible();
      await page.keyboard.press('Escape');
      await expect(page.getByRole('complementary',{name:'Player tools'})).toBeHidden();
    } else {
      await expect(page.getByRole('complementary',{name:'Player tools'})).toBeVisible();
    }
    await expect(page.getByTestId('song')).toBeVisible();
    await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  });
}

test('keeps requested text size and wide tab accessible on a narrow screen', async ({page}) => {
  const id = readFileSync('/private/tmp/songbook-auth-e2e-player-id','utf8');
  await page.setViewportSize({width:320,height:700});
  await page.goto(`/player?id=${id}`);
  await page.getByLabel('Password').fill('synthetic test password');
  await page.getByRole('button',{name:'Sign in'}).click();
  await page.getByRole('button',{name:'Tools'}).click();
  await page.getByLabel(/Text size/).fill('32');
  await page.getByLabel('Columns').selectOption('3');
  await expect(page.getByText('Showing 1 column (limited by available width)')).toBeVisible();
  await page.getByRole('button',{name:'Focus view'}).click();
  await page.getByRole('button',{name:'Close tools'}).click();
  await expect(page.getByTestId('song')).toHaveCSS('font-size','32px');
  await expect(page.getByTestId('tab')).toHaveCSS('white-space','pre');
  expect(await page.getByTestId('tab').evaluate(element => element.scrollWidth > element.clientWidth)).toBe(true);
  await expect(page.getByTestId('song')).toContainText('Music');
});

test('columns preserve source order and keep section headings with music', async ({page}) => {
  const id = readFileSync('/private/tmp/songbook-auth-e2e-player-id','utf8');
  await page.setViewportSize({width:1440,height:900});
  await page.goto(`/player?id=${id}`);
  await page.getByLabel('Password').fill('synthetic test password');
  await page.getByRole('button',{name:'Sign in'}).click();
  await expect(page.locator('.music-column')).toHaveCount(3);
  const result = await page.locator('.music-column').evaluateAll(columns => columns.map(column => ({text:column.textContent ?? '', headings:Array.from(column.querySelectorAll('.music-block--heading')).map(heading => Boolean(heading.nextElementSibling))})));
  const lines = result.flatMap(column => Array.from(column.text.matchAll(/Line-(\d\d)/g), match => Number(match[1])));
  expect(lines).toEqual(Array.from({length:30}, (_, index) => index));
  expect(result.flatMap(column => column.headings).every(Boolean)).toBe(true);
});
