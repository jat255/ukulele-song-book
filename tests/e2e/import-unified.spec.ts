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

test('shows Codex usage bars in settings and the imports popover', async ({page}) => {
  await page.route('**/api/codex/status', route => route.fulfill({json:{connected:true,email:null,plan:'plus',models:[{id:'gpt-6.1-terra',name:'Terra',default:true}]}}));
  await page.route('**/api/codex/usage', route => route.fulfill({json:{primary:{used_percent:30,window_minutes:300,resets_at:1800000000},secondary:{used_percent:6,window_minutes:10080,resets_at:1800500000}}}));
  await page.goto('/settings');
  await expect(page.getByRole('heading',{name:'Codex subscription'})).toBeVisible();
  await expect(page.getByRole('button',{name:'Configure AI conversion'})).toHaveCount(0);
  await expect(page.getByRole('progressbar',{name:'5-hour limit'})).toHaveAttribute('value','30');
  await expect(page.getByRole('progressbar',{name:'Weekly limit'})).toHaveAttribute('value','6');
  await page.goto('/imports');
  await page.getByRole('button',{name:'Usage'}).click();
  const popover=page.getByLabel('Usage options');
  await expect(popover.getByRole('progressbar',{name:'5-hour limit'})).toHaveAttribute('value','30');
  await expect(popover.getByRole('progressbar',{name:'Weekly limit'})).toHaveAttribute('value','6');
});

test('shows unavailable usage without presenting zero percent', async ({page}) => {
  await page.route('**/api/codex/status', route => route.fulfill({json:{connected:true,email:null,plan:null,models:[{id:'gpt-6.1-terra',name:'Terra',default:true}]}}));
  await page.route('**/api/codex/usage', route => route.fulfill({json:{primary:null,secondary:{used_percent:6,window_minutes:10080,resets_at:null}}}));
  await page.goto('/settings');
  await expect(page.getByText('5-hour limit unavailable')).toBeVisible();
  await expect(page.getByRole('progressbar',{name:'5-hour limit'})).toHaveCount(0);
  await expect(page.getByRole('progressbar',{name:'Weekly limit'})).toHaveAttribute('value','6');
});

test('reports quota change next to a completed conversion', async ({page}) => {
  await page.route('**/api/codex/status', route => route.fulfill({json:{connected:true,models:[{id:'gpt-6.1-terra',name:'Terra',default:true}]}}));
  await page.route('**/api/imports', route => route.fulfill({json:[{id:'job',source_id:'source',state:'needs-review',method:'ai',error_code:null,selection:[{pages:[1],provider:'codex'}],drafts:[{id:'draft',ordinal:0,source:'{title: Song}\n[C]Hello',revision:'rev',diagnostics:[],uncertainties:[],pages:[],accepted_id:null,provider_metadata:{quota_usage:{primary:{delta_percent:3,before_remaining:80,after_remaining:77,window_minutes:300},secondary:{delta_percent:null,window_minutes:10080}}}}]}]}));
  await page.goto('/imports');
  const row=page.getByRole('row').filter({hasText:'Needs review'});
  await expect(row.getByText('5-hour: 80% → 77% remaining (3 percentage points used)')).toBeVisible();
  await expect(row.getByText('Weekly: comparison unavailable')).toBeVisible();
  await expect(row.getByText(/Shared account activity/)).toBeVisible();
});
