import {test, expect} from '@playwright/test';

test('library workspace stays usable and styled at desktop and phone widths', async ({page}) => {
  await page.goto('/');
  await page.getByLabel('Password').fill('synthetic test password');
  await page.getByRole('button', {name:'Sign in'}).click();
  await expect(page.getByRole('heading', {name:'Library'})).toBeVisible();
  await expect(page.locator('main')).toHaveClass(/workspace/);
  await expect(page.locator('nav')).toHaveCSS('display', 'flex');
  for (const width of [1200, 390]) {
    await page.setViewportSize({width, height:800});
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
    await expect(page.getByLabel('Search')).toBeVisible();
  }
});

test('sign-in uses a responsive songbook card and keeps errors visible',async({page})=>{
 await page.goto('/');
 await expect(page.locator('main')).toHaveClass(/auth-page/);
 for(const width of [1280,390,320]){
  await page.setViewportSize({width,height:700});await expect(page.getByLabel('Password')).toBeVisible();
  const card=await page.locator('.auth-card').boundingBox();expect(card!.x).toBeGreaterThanOrEqual(0);expect(card!.x+card!.width).toBeLessThanOrEqual(width);
 }
 await page.getByLabel('Password').fill('incorrect synthetic password');await page.getByRole('button',{name:'Sign in',exact:true}).click();
 await expect(page.getByRole('alert')).toContainText('Unable to sign in.');await expect(page.getByLabel('Password')).toHaveValue('');
 await page.screenshot({path:'.local/review/sign-in-phone.png'});
 await page.setViewportSize({width:1280,height:800});await page.screenshot({path:'.local/review/sign-in-desktop.png'});
});

test('library presents compact song rows in a table without storage estimates',async({page})=>{
 await page.goto('/');await page.getByLabel('Password').fill('synthetic test password');await page.getByRole('button',{name:'Sign in'}).click();
 await expect(page.getByRole('table',{name:'Song library'})).toBeVisible();
 for(const name of ['Song','Artist','Favorite','Tags','Actions'])await expect(page.getByRole('columnheader',{name,exact:true})).toBeVisible();
 await expect(page.getByText(/Browser storage:|Storage estimate unavailable/)).toHaveCount(0);
 await expect(page.getByText('Online only',{exact:true}).filter({visible:true})).toHaveCount(0);
 const row=page.getByRole('row').filter({has:page.getByRole('link',{name:'Player Test',exact:true})}).first();await expect(row).toBeVisible();expect((await row.boundingBox())!.height).toBeLessThan(80);
 for(const width of [1280,390,320]){await page.setViewportSize({width,height:800});expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);}
 await page.screenshot({path:'.local/review/library-table-phone.png'});await page.setViewportSize({width:1280,height:800});await page.screenshot({path:'.local/review/library-table-desktop.png'});
});

test('sign out sits at the top right beside the songbook title',async({page})=>{
 await page.goto('/');await page.getByLabel('Password').fill('synthetic test password');await page.getByRole('button',{name:'Sign in'}).click();
 for(const width of [1280,390,320]){
  await page.setViewportSize({width,height:800});const title=page.getByRole('heading',{name:'Songbook',exact:true});await expect(title).toBeVisible();
  const heading=await title.boundingBox(),button=await page.getByRole('button',{name:'Sign out',exact:true}).boundingBox();
  expect(button!.x).toBeGreaterThan(heading!.x+heading!.width);expect(button!.y).toBeLessThan(heading!.y+heading!.height);
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);
 }
});

test('library delete requires confirmation and removes both songs and source-only entries',async({page})=>{
 await page.goto('/');await page.getByLabel('Password').fill('synthetic test password');await page.getByRole('button',{name:'Sign in'}).click();await expect(page.getByRole('heading',{name:'Library',exact:true})).toBeVisible();
 await page.evaluate(async()=>{const session=await(await fetch('/api/session')).json();await fetch('/api/imports/sources?filename=delete-only.pdf',{method:'POST',headers:{'X-CSRF-Token':session.csrf},body:'synthetic retained source'});});await page.reload();
 const source=page.getByRole('row').filter({has:page.getByRole('link',{name:'delete-only.pdf',exact:true})});
 page.once('dialog',dialog=>dialog.dismiss());await source.getByRole('button',{name:'Delete from library',exact:true}).click();await expect(source).toBeVisible();
 page.once('dialog',dialog=>dialog.accept());await source.getByRole('button',{name:'Delete from library',exact:true}).click();await expect(source).toHaveCount(0);await page.reload();await expect(source).toHaveCount(0);
 const id=await page.evaluate(async()=>{const session=await(await fetch('/api/session')).json();const rows=await(await fetch('/api/library')).json();const base=rows.find((item:{source_only:boolean})=>!item.source_only);return(await(await fetch('/api/songs/'+base.song_id+'/arrangements',{method:'POST',headers:{'Content-Type':'application/json','X-CSRF-Token':session.csrf},body:JSON.stringify({source:'{title: Delete song}\n[C]Synthetic'})})).json()).id;});await page.goto('/player?id='+id);await expect(page.getByRole('status').filter({hasText:/Saved for offline/})).toBeVisible();await page.goto('/');
 const song=page.getByRole('row').filter({has:page.getByRole('link',{name:'Delete song',exact:true})});page.once('dialog',dialog=>dialog.accept());await song.getByRole('button',{name:'Delete from library',exact:true}).click();await expect(song).toHaveCount(0);await page.reload();await expect(song).toHaveCount(0);
});
