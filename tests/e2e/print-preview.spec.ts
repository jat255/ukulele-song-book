import {test,expect} from '@playwright/test';
import {readFileSync} from 'node:fs';

test('previews actual PDF pages and replaces stale settings results', async ({page}) => {
  const id=readFileSync('/private/tmp/songbook-auth-e2e-print-id','utf8');
  await page.goto(`/print?id=${id}`);
  await page.getByLabel('Password').fill('synthetic test password');
  await page.getByRole('button',{name:'Sign in'}).click();
  await expect(page.getByText(/Actual page count:/)).toBeVisible({timeout:30000});
  await expect(page.getByAltText('PDF page 1')).toBeVisible();
  await expect(page.getByRole('link',{name:'Download PDF'})).toBeVisible();
  await page.getByLabel('Paper').selectOption('A4');
  await expect(page.getByText('Generating current PDF…')).toBeVisible();
  await expect(page.getByText(/Actual page count:/)).toBeVisible({timeout:30000});
  await expect(page.getByAltText('PDF page 1')).toBeVisible();
});

test('ignores an older result when settings change during rendering', async ({page}) => {
  const id=readFileSync('/private/tmp/songbook-auth-e2e-print-id','utf8');
  const created:string[]=[];
  page.on('response',async response => {
    if (response.url().endsWith('/api/pdfs') && response.request().method()==='POST' && response.status()===202) {
      const value=await response.json() as {id:string}; created.push(value.id);
    }
  });
  await page.goto(`/print?id=${id}`);
  await page.getByLabel('Password').fill('synthetic test password');
  await page.getByRole('button',{name:'Sign in'}).click();
  await expect.poll(() => created.length).toBeGreaterThan(0);
  const currentPaper=await page.getByLabel('Paper').inputValue();
  await page.getByLabel('Paper').selectOption(currentPaper === 'A4' ? 'Letter' : 'A4');
  await expect.poll(() => created.length).toBeGreaterThan(1);
  await expect(page.getByText(/Actual page count:/)).toBeVisible({timeout:30000});
  await expect(page.getByRole('link',{name:'Download PDF'})).toHaveAttribute('href',`/api/pdfs/${created[created.length-1]}/file`);
});
