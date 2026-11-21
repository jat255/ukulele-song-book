import {test, expect} from '@playwright/test';

test('queues multiple PDFs with Codex from the single import form', async ({page}) => {
  const queued: any[] = [];
  await page.route('**/api/codex/status', route => route.fulfill({json:{connected:true, models:[{id:'gpt-6-sol',name:'Sol',default:true},{id:'gpt-6.1-terra',name:'Terra 6.1',default:false},{id:'gpt-6.2-terra',name:'Terra 6.2',default:false}]}}));
  await page.route('**/api/imports/sources?*', route => route.fulfill({json:{id:crypto.randomUUID(),kind:'pdf'}}));
  await page.route('**/api/imports', route => {
    if (route.request().method() === 'POST') { queued.push(route.request().postDataJSON()); return route.fulfill({json:{id:'job'}}); }
    return route.fulfill({json:[]});
  });
  await page.goto('/imports');
  await expect(page.getByRole('heading',{name:'Convert PDFs with Codex'})).toBeVisible();
  await expect(page.getByRole('heading',{name:'Add music'})).toHaveCount(0);
  await expect(page.getByRole('heading',{name:'Import converted batch'})).toHaveCount(0);
  await expect(page.getByLabel('Codex model')).toHaveValue('gpt-6.2-terra');
  await page.getByLabel('PDF files',{exact:true}).setInputFiles([
    {name:'first.pdf',mimeType:'application/pdf',buffer:Buffer.from('%PDF-1.4')},
    {name:'second.pdf',mimeType:'application/pdf',buffer:Buffer.from('%PDF-1.4')},
  ]);
  await expect(page.getByText('Send these PDFs to Codex using my subscription')).toHaveCount(0);
  await page.getByRole('button',{name:'Queue PDFs'}).click();
  await expect.poll(()=>queued.length).toBe(2);
  for (const job of queued) {
    expect(job.method).toBe('ai');
    expect(job.selection[0]).toMatchObject({all_pages:true,provider:'codex',model:'gpt-6.2-terra',authorization:true});
  }
});


test('drop zone accepts PDF files and rejects other files', async ({page}) => {
  await page.route('**/api/codex/status', route => route.fulfill({json:{connected:true,models:[{id:'gpt-6.1-terra',name:'Terra',default:false}]}}));
  await page.goto('/imports');
  const zone = page.getByLabel('Drop PDF files here');
  await expect(zone).toBeVisible();
  const transfer = await page.evaluateHandle(() => {
    const data = new DataTransfer();
    data.items.add(new File(['%PDF'], 'song.pdf', {type:'application/pdf'}));
    data.items.add(new File(['no'], 'notes.txt', {type:'text/plain'}));
    return data;
  });
  await zone.dispatchEvent('drop', {dataTransfer:transfer});
  await expect(page.getByText('song.pdf')).toBeVisible();
  await expect(page.getByText('Only PDF files can be added.')).toBeVisible();
  await expect(page.getByRole('button',{name:'Queue PDFs'})).toBeEnabled();
});
