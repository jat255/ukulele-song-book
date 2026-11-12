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
 await page.screenshot({path:'.local/review/second-settings.png'});await page.goto('/');const row=page.getByRole('listitem').filter({has:page.getByRole('link',{name:'Browser Test',exact:true})}).first();
 const before=await row.boundingBox();await row.getByRole('button',{name:'Export',exact:true}).click();
 await expect(row.getByRole('button',{name:'Export ChordPro'})).toBeVisible();expect((await row.boundingBox())!.height).toBe(before!.height);
 await page.screenshot({path:'.local/review/second-menu.png'});await page.keyboard.press('Escape');await expect(row.getByRole('button',{name:'Export ChordPro'})).toBeHidden();
 await row.getByRole('button',{name:'Export',exact:true}).click();await page.getByRole('heading',{name:'Library',exact:true}).click();await expect(row.getByRole('button',{name:'Export ChordPro'})).toBeHidden();
 await page.setViewportSize({width:390,height:600});await row.getByRole('button',{name:'Offline options',exact:true}).click();
 const panel=row.locator('.offline-actions [popover]');await expect(panel).toBeVisible();const bounds=await panel.boundingBox();expect(bounds!.x).toBeGreaterThanOrEqual(0);expect(bounds!.x+bounds!.width).toBeLessThanOrEqual(390);expect(bounds!.y+bounds!.height).toBeLessThanOrEqual(600);

});
test('navigation uses arrangement IDs only on arrangement pages',async({page})=>{
 await page.goto('/setlists?id=00000000-0000-0000-0000-000000000000');await page.getByLabel('Password').fill('synthetic test password');await page.getByRole('button',{name:'Sign in'}).click();
 await expect(page.getByRole('navigation').getByRole('link',{name:'Player',exact:true})).toHaveAttribute('href','/player');
 await expect(page.getByRole('navigation').getByRole('link',{name:'Print',exact:true})).toHaveAttribute('href','/print');
 const id=readFileSync('/private/tmp/songbook-auth-e2e-performance-id','utf8');await page.goto('/edit?id='+id);
 await expect(page.getByRole('navigation').getByRole('link',{name:'Player',exact:true})).toHaveAttribute('href','/player?id='+id);
});
