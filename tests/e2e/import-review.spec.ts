import {test, expect} from '@playwright/test';
import {readFileSync} from 'node:fs';

test('reviews and accepts a direct synthetic import', async ({page}) => {
  await page.goto('/imports');
  await page.getByLabel('Password').fill('synthetic test password');
  await page.getByRole('button', {name:'Sign in'}).click();
  await page.getByLabel('Choose source').setInputFiles({name:'song.cho', mimeType:'text/plain', buffer:Buffer.from('{title: Test}\n[C]Hello')});
  await page.getByRole('button', {name:'Import source'}).click();
  await expect(page.getByLabel('ChordPro draft')).toHaveValue('{title: Test}\n[C]Hello', {timeout:15000});
  await expect(page.getByRole('table',{name:'Import queue'})).toContainText('song.cho');
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
  const csrf = (await (await page.request.get('/api/session')).json()).csrf;
  await page.goto('/imports');
  const headers = {'X-CSRF-Token':csrf, 'Origin':'http://127.0.0.1:4173'};
  const sourceResponse = await page.request.post('/api/imports/sources?filename=review.pdf', {
    headers, data:readFileSync('/private/tmp/songbook-auth-e2e-book.pdf'),
  });
  expect(sourceResponse.ok()).toBe(true);
  const source = await sourceResponse.json();
  const jobResponse = await page.request.post('/api/imports', {
    headers, data:{source_id:source.id, selection:[{pages:[2]}], method:'local', idempotency_key:crypto.randomUUID()},
  });
  expect(jobResponse.ok()).toBe(true);
  await expect(page.getByAltText('Original page 2')).toBeVisible({timeout:15000});
  await expect(page.getByText('No text could be extracted; consult the original page')).toBeVisible();
  await page.getByLabel('ChordPro draft').fill('{title: Reviewed}\n[C]Synthetic');
  await page.getByRole('button', {name:'Save draft'}).click();
  await expect(page.getByText('Draft saved.')).toBeVisible();
  await expect(page.getByLabel('I reviewed the warnings and original')).toHaveCount(0);
  await page.getByRole('button', {name:'Accept draft'}).click();
  await expect(page.getByText('Arrangement accepted')).toBeVisible();
});

test('PDF import form separates fields and queue identifies each source',async({page})=>{
 await page.goto('/imports');await page.getByLabel('Password').fill('synthetic test password');await page.getByRole('button',{name:'Sign in'}).click();
 await page.getByLabel('Choose source').setInputFiles('/private/tmp/songbook-auth-e2e-book.pdf');
 await expect(page.getByRole('group',{name:'PDF pages'})).toBeVisible();
 await expect(page.getByLabel('Optional crop x0,y0,x1,y1 (each from 0 to 1)')).toBeHidden();
 await expect(page.getByRole('table',{name:'Import queue'})).toBeVisible();
 await page.getByLabel('Choose pages or split songs').check();for(const width of [1280,390,320]){await page.setViewportSize({width,height:800});expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);const file=await page.getByLabel('Choose source').boundingBox(),pages=await page.getByLabel('Pages per song (commas between pages, semicolons between songs)').boundingBox();expect(pages!.y).toBeGreaterThan(file!.y+file!.height);}
 await page.screenshot({path:'.local/review/import-form-phone.png'});await page.setViewportSize({width:1280,height:900});await page.screenshot({path:'.local/review/import-form-desktop.png'});
});

test('accepts consecutive PDF drafts without warning acknowledgement',async({page})=>{
 await page.goto('/imports');await page.getByLabel('Password').fill('synthetic test password');await page.getByRole('button',{name:'Sign in'}).click();
 await page.getByLabel('Choose source').setInputFiles('/private/tmp/songbook-auth-e2e-book.pdf');await page.getByLabel('Choose pages or split songs').check();await page.getByLabel('Pages per song (commas between pages, semicolons between songs)').fill('1;2');await page.getByRole('button',{name:'Import source'}).click();
 await expect(page.getByAltText('Original page 1')).toBeVisible({timeout:15000});await page.getByLabel('ChordPro draft').fill('{title: First warning draft}\n[C]Synthetic');await page.getByRole('button',{name:'Save draft'}).click();await expect(page.getByText('Draft saved.')).toBeVisible();
 await page.getByRole('button',{name:'Accept draft'}).click();
 await expect(page.getByAltText('Original page 2')).toBeVisible({timeout:15000});await expect(page.getByLabel('I reviewed the warnings and original')).toHaveCount(0);
 await page.getByLabel('ChordPro draft').fill('{title: Second warning draft}\n[G]Synthetic');await page.getByRole('button',{name:'Save draft'}).click();await expect(page.getByText('Draft saved.')).toBeVisible();await page.getByRole('button',{name:'Accept draft'}).click();await expect(page.getByText('Arrangement accepted')).toBeVisible();
});

test('discards a draft and starts over from its retained source without another file upload',async({page})=>{
 await page.goto('/imports');await page.getByLabel('Password').fill('synthetic test password');await page.getByRole('button',{name:'Sign in'}).click();
 await page.getByLabel('Choose source').setInputFiles({name:'start-over.cho',mimeType:'text/plain',buffer:Buffer.from('{title: Start over}\n[C]Synthetic')});await page.getByRole('button',{name:'Import source'}).click();
 await expect(page.getByLabel('ChordPro draft')).toHaveValue('{title: Start over}\n[C]Synthetic',{timeout:15000});
 const row=page.getByRole('table',{name:'Import queue'}).getByRole('row').filter({hasText:'start-over.cho'});page.on('dialog',dialog=>dialog.accept());
 await row.getByRole('button',{name:'Start over',exact:true}).click();await expect(page.getByText('Ready to retry: start-over.cho')).toBeVisible();await expect(row).toHaveCount(0);
 await page.getByRole('button',{name:'Import source'}).click();await expect(page.getByLabel('ChordPro draft')).toHaveValue('{title: Start over}\n[C]Synthetic',{timeout:15000});
 await row.getByRole('button',{name:'Discard attempt',exact:true}).click();await expect(row).toHaveCount(0);await expect(page.getByLabel('ChordPro draft')).toHaveCount(0);
});

test('PDF defaults to the entire document as one song with custom pages optional',async({page})=>{
 await page.goto('/imports');await page.getByLabel('Password').fill('synthetic test password');await page.getByRole('button',{name:'Sign in'}).click();await page.getByLabel('Choose source').setInputFiles('/private/tmp/songbook-auth-e2e-book.pdf');
 await expect(page.getByLabel('Entire PDF as one song')).toBeChecked();await expect(page.getByLabel('Pages per song (commas between pages, semicolons between songs)')).toBeHidden();
 let requestBody:any;page.on('request',request=>{if(new URL(request.url()).pathname==='/api/imports' && request.method()==='POST')requestBody=request.postDataJSON();});
 await page.getByRole('button',{name:'Import source'}).click();await expect(page.getByAltText('Original page 1')).toBeVisible({timeout:15000});await expect(page.getByAltText('Original page 2')).toBeVisible();expect(requestBody.selection).toHaveLength(1);expect(requestBody.selection[0].all_pages).toBe(true);
});

test('failed imports explain the problem and next step without provider payloads',async({page})=>{
 await page.goto('/imports');await page.getByLabel('Password').fill('synthetic test password');await page.getByRole('button',{name:'Sign in'}).click();
 await expect(page.getByRole('heading',{name:'Imports',exact:true})).toBeVisible();await page.route('**/api/imports',route=>route.fulfill({status:200,contentType:'application/json',body:JSON.stringify([{id:'synthetic-failed',source_id:'none',state:'failed',method:'ai',drafts:[],selection:[{pages:[1]}],error_code:'provider_auth',error_details:{message:'AI service rejected the API credentials.',hint:'Check the saved API key in Settings, then start over.',retryable:false}}])}));
 await page.reload();await expect(page.getByText('AI service rejected the API credentials.')).toBeVisible();await expect(page.getByText('Check the saved API key in Settings, then start over.')).toBeVisible();await expect(page.getByRole('button',{name:'Retry',exact:true})).toHaveCount(0);await page.screenshot({path:'.local/review/import-failure-feedback.png'});
});
