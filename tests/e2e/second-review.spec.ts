import {test,expect} from '@playwright/test';
import {readFileSync} from 'node:fs';
test('song destinations, grouped controls, chord toggle and floating actions',async({page})=>{
 await page.setViewportSize({width:1440,height:1000});await page.goto('/player');await page.getByLabel('Password').fill('synthetic test password');await page.getByRole('button',{name:'Sign in'}).click();
 await expect(page.getByRole('heading',{name:'Choose a song to play'})).toBeVisible();
 await page.goto('/print');await expect(page.getByRole('heading',{name:'Choose a song to print'})).toBeVisible();
 const id=readFileSync('/private/tmp/songbook-auth-e2e-performance-id','utf8');await page.goto('/player?id='+id);
 await expect(page.getByRole('region',{name:'Key & capo'})).toBeVisible();
 await expect(page.getByRole('region',{name:'Readability'})).toBeVisible();
 const chords=page.getByRole('region',{name:'Song chords'});await expect(chords.locator('svg').first()).toBeVisible();
 await page.getByRole('button',{name:'Hide chords',exact:true}).click();await expect(chords.locator('svg')).toHaveCount(0);
 await page.getByRole('button',{name:'Show chords',exact:true}).click();await expect(chords.locator('svg').first()).toBeVisible();
 await page.screenshot({path:'.local/review/second-player-desktop.png',fullPage:true});
 await page.setViewportSize({width:390,height:844});
 expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);
 await page.getByRole('button',{name:'Tools',exact:true}).click();
 await page.screenshot({path:'.local/review/second-player-phone.png'});
 await page.keyboard.press('Escape');await expect(page.getByRole('button',{name:'Tools',exact:true})).toBeFocused();
 await page.setViewportSize({width:1440,height:1000});
 await page.goto('/settings');await expect(page.getByRole('group',{name:'Playing defaults'})).toBeVisible();
 await page.screenshot({path:'.local/review/second-settings.png'});await page.goto('/');const row=page.getByRole('row').filter({has:page.getByRole('link',{name:'Browser Test',exact:true})}).first();
 const before=await row.boundingBox();await row.getByRole('button',{name:'Export',exact:true}).click();
 await expect(row.getByRole('button',{name:'Export ChordPro'})).toBeVisible();expect((await row.boundingBox())!.height).toBe(before!.height);
 await page.screenshot({path:'.local/review/second-menu.png'});await page.keyboard.press('Escape');await expect(row.getByRole('button',{name:'Export ChordPro'})).toBeHidden();
 await row.getByRole('button',{name:'Export',exact:true}).click();await page.getByRole('heading',{name:'Library',exact:true}).click();await expect(row.getByRole('button',{name:'Export ChordPro'})).toBeHidden();
 await page.setViewportSize({width:390,height:600});await row.getByRole('button',{name:'More',exact:true}).click();
 const panel=row.locator('.offline-actions [popover]');await expect(panel).toBeVisible();const bounds=await panel.boundingBox();expect(bounds!.x).toBeGreaterThanOrEqual(0);expect(bounds!.x+bounds!.width).toBeLessThanOrEqual(390);expect(bounds!.y+bounds!.height).toBeLessThanOrEqual(600);

});
test('navigation uses arrangement IDs only on arrangement pages',async({page})=>{
 await page.goto('/setlists?id=00000000-0000-0000-0000-000000000000');await page.getByLabel('Password').fill('synthetic test password');await page.getByRole('button',{name:'Sign in'}).click();
 await expect(page.getByRole('navigation').getByRole('link',{name:'Player',exact:true})).toHaveAttribute('href','/player');
 await expect(page.getByRole('navigation').getByRole('link',{name:'Print',exact:true})).toHaveAttribute('href','/print');
 const id=readFileSync('/private/tmp/songbook-auth-e2e-performance-id','utf8');await page.goto('/edit?id='+id);
 await expect(page.getByRole('navigation').getByRole('link',{name:'Player',exact:true})).toHaveAttribute('href','/player?id='+id);
});
test('capo value has room for two digits and tuning controls are absent',async({page})=>{
 const id=readFileSync('/private/tmp/songbook-auth-e2e-performance-id','utf8');await page.goto('/player?id='+id);await page.getByLabel('Password').fill('synthetic test password');await page.getByRole('button',{name:'Sign in'}).click();
 for(const width of [1440,390,320]){
  await page.setViewportSize({width,height:844});if(width<700)await page.getByRole('button',{name:'Tools',exact:true}).click();
  const capo=page.getByRole('spinbutton',{name:/Capo/});await capo.fill('12');await expect(capo).toHaveValue('12');
  expect((await capo.boundingBox())!.width).toBeGreaterThanOrEqual(64);await expect(capo).toHaveCSS('appearance','textfield');
  await expect(page.getByLabel('Tuning',{exact:false})).toHaveCount(0);
  if(width<700)await page.keyboard.press('Escape');
 }
 await page.goto('/settings');await expect(page.getByLabel('Tuning',{exact:false})).toHaveCount(0);
});
test('chord hints escape the music frame and remain inside the viewport',async({page})=>{
 await page.goto('/');await page.getByLabel('Password').fill('synthetic test password');await page.getByRole('button',{name:'Sign in'}).click();await expect(page.getByRole('heading',{name:'Library',exact:true})).toBeVisible();
 const base=readFileSync('/private/tmp/songbook-auth-e2e-performance-id','utf8');const id=await page.evaluate(async base=>{const item=await(await fetch('/api/arrangements/'+base)).json(),session=await(await fetch('/api/session')).json();return(await(await fetch('/api/songs/'+item.song_id+'/arrangements',{method:'POST',headers:{'Content-Type':'application/json','X-CSRF-Token':session.csrf},body:JSON.stringify({source:'{title: Hint regression}\n{key: C}\n[Am/D]Synthetic slash chord\n[C]Last line'})})).json()).id;},base);
 await page.goto('/player?id='+id);const chord=page.locator('.music--play .chord').last();await chord.hover();const hint=page.locator('.chord-popover').filter({visible:true});await expect(hint).toBeVisible();
 const box=await hint.boundingBox();expect(await hint.evaluate((el,point)=>el.contains(document.elementFromPoint(point.x,point.y)),{x:box!.x+box!.width/2,y:box!.y+box!.height-8})).toBe(true);
 await expect(page.getByRole('region',{name:'Song chords'}).getByRole('img',{name:/Am\/D, frets/})).toBeVisible();
 await hint.hover();await expect(hint).toBeVisible();await page.screenshot({path:'.local/review/chord-hint-unclipped.png'});
 await page.keyboard.press('Escape');await expect(hint).toBeHidden();
 await chord.focus();await expect(hint).toBeVisible();await page.setViewportSize({width:390,height:600});await expect(hint).toBeHidden();await chord.evaluate(el=>el.blur());await chord.focus();await expect(hint).toBeVisible();const phoneBox=await hint.boundingBox();expect(phoneBox!.x+phoneBox!.width).toBeLessThanOrEqual(390);expect(phoneBox!.y+phoneBox!.height).toBeLessThanOrEqual(600);
});
