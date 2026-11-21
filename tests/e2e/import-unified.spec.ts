import {test, expect} from '@playwright/test';

test('queues multiple PDFs with Codex from the single import form', async ({page}) => {
  const queued: any[] = [];
  await page.route('**/api/codex/status', route => route.fulfill({json:{connected:true, models:[{id:'test-model',name:'Test model',default:true}]}}));
  await page.route('**/api/imports/sources?*', route => route.fulfill({json:{id:crypto.randomUUID(),kind:'pdf'}}));
  await page.route('**/api/imports', route => {
    if (route.request().method() === 'POST') { queued.push(route.request().postDataJSON()); return route.fulfill({json:{id:'job'}}); }
    return route.fulfill({json:[]});
  });
  await page.goto('/imports');
  await expect(page.getByRole('heading',{name:'Convert PDFs with Codex'})).toBeVisible();
  await expect(page.getByRole('heading',{name:'Add music'})).toHaveCount(0);
  await expect(page.getByRole('heading',{name:'Import converted batch'})).toHaveCount(0);
  await page.getByLabel('PDF files').setInputFiles([
    {name:'first.pdf',mimeType:'application/pdf',buffer:Buffer.from('%PDF-1.4')},
    {name:'second.pdf',mimeType:'application/pdf',buffer:Buffer.from('%PDF-1.4')},
  ]);
  await expect(page.getByText('Send these PDFs to Codex using my subscription')).toHaveCount(0);
  await page.getByRole('button',{name:'Queue PDFs'}).click();
  await expect.poll(()=>queued.length).toBe(2);
  for (const job of queued) {
    expect(job.method).toBe('ai');
    expect(job.selection[0]).toMatchObject({all_pages:true,provider:'codex',model:'test-model',authorization:true});
  }
});
