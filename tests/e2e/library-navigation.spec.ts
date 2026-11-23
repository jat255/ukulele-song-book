import {test, expect} from '@playwright/test';
import {readFileSync} from 'node:fs';

test('the library replaces the generic player and print pickers while song links still work', async ({page}) => {
  for (const path of ['/player','/print']) {
    await page.goto(path);
    await expect(page).toHaveURL(/\/$/);
    await expect(page.getByRole('heading',{name:'Library',exact:true})).toBeVisible();
    const nav=page.getByRole('navigation',{name:'Songbook'});
    await expect(nav.getByRole('link',{name:'Player',exact:true})).toHaveCount(0);
    await expect(nav.getByRole('link',{name:'Print',exact:true})).toHaveCount(0);
  }
  const id=readFileSync('/private/tmp/songbook-auth-e2e-performance-id','utf8');
  await page.goto('/player?id='+id);
  await expect(page.getByRole('complementary',{name:'Player tools'})).toBeVisible();
  await page.getByRole('link',{name:'Print',exact:true}).click();
  await expect(page).toHaveURL(new RegExp('/print\\?id='+id));
  await expect(page.getByRole('heading',{name:'Print preview'})).toBeVisible();
  await page.goto('/edit?id='+id);
  await expect(page.getByRole('link',{name:'Play song'})).toHaveAttribute('href','/player?id='+id);
  await expect(page.getByRole('link',{name:'Print song'})).toHaveAttribute('href','/print?id='+id);
});
