import {test as base,expect,webkit} from '@playwright/test';
const test=base.extend({context:async({browserName,browser,baseURL},use,testInfo)=>{const context=browserName==='webkit' ? await webkit.launchPersistentContext(testInfo.outputPath('profile'),{headless:true,baseURL}) : await browser.newContext({baseURL});await use(context);await context.close();}});
import type {Page} from '@playwright/test';
import {readFileSync} from 'node:fs';

async function isolatedSong(page:Page,title:string):Promise<string>{await expect.poll(async()=>(await page.request.get('/api/session')).status()).toBe(200);const originalId=readFileSync('/private/tmp/songbook-auth-e2e-player-id','utf8');const original=await (await page.request.get(`/api/arrangements/${originalId}`)).json();const session=await (await page.request.get('/api/session')).json();const response=await page.request.post(`/api/songs/${original.song_id}/arrangements`,{headers:{Origin:'http://127.0.0.1:4173','X-CSRF-Token':session.csrf},data:{source:original.source.replace('{title: Player Test}',`{title: ${title}}`),source_arrangement_id:originalId}});expect(response.status()).toBe(201);return (await response.json()).id;}


test('offline performance preferences survive a cold reload', async ({page,context})=>{
  await page.goto('/');await page.getByLabel('Password').fill('synthetic test password');await page.getByRole('button',{name:'Sign in'}).click();
  const song=page.getByRole('listitem').filter({has:page.getByRole('link',{name:'Player Test',exact:true})}).first();await song.getByRole('button',{name:'Download for offline'}).click();await expect(song.getByText('Downloaded',{exact:true})).toBeVisible();
  const href=await song.getByRole('link',{name:'Player Test',exact:true}).getAttribute('href');await context.setOffline(true);await page.goto(href!);
  await page.getByLabel('Transpose semitones').fill('2');await expect(page.getByLabel('Transpose semitones')).toHaveValue('2');
  await page.waitForTimeout(700);await page.reload();await expect(page.getByLabel('Transpose semitones')).toHaveValue('2');
});

test('offline performance changes sync after reconnect without changing source', async ({page,context})=>{
  await page.goto('/');await page.getByLabel('Password').fill('synthetic test password');await page.getByRole('button',{name:'Sign in'}).click();
  const song=page.getByRole('listitem').filter({has:page.getByRole('link',{name:'Player Test',exact:true})}).first();await song.getByRole('button',{name:'Download for offline'}).click();await expect(song.getByText('Downloaded',{exact:true})).toBeVisible();
  const href=await song.getByRole('link',{name:'Player Test',exact:true}).getAttribute('href');const id=new URL(href!,'http://example.test').searchParams.get('id');
  const before=await (await page.request.get(`/api/arrangements/${id}`)).json();
  await context.setOffline(true);await page.goto(href!);await page.getByLabel('Transpose semitones').fill('3');await expect(page.getByLabel('Transpose semitones')).toHaveValue('3');await page.waitForTimeout(700);
  const revisionCheck=page.waitForRequest(request=>request.url().includes('/api/sync/check'),{timeout:5000});await context.setOffline(false);await revisionCheck;
  await expect.poll(async()=>{const response=await page.request.get(`/api/preferences/${id}`);return (await response.json()).groups.performance.value.semitones;},{timeout:10000}).toBe(3);
  const after=await (await page.request.get(`/api/arrangements/${id}`)).json();expect(after.revision).toBe(before.revision);expect(after.source).toBe(before.source);
});

test('preference conflicts retry using the latest server envelope', async ({page})=>{
  const {readFileSync}=await import('node:fs');const id=readFileSync('/private/tmp/songbook-auth-e2e-player-id','utf8');
  await page.goto('/');await page.getByLabel('Password').fill('synthetic test password');await page.getByRole('button',{name:'Sign in'}).click();
  await expect(page.getByRole('heading',{name:'Library'})).toBeVisible();await page.goto(`/player?id=${id}`);await expect(page.getByTestId('song')).toBeVisible();
  let rejected=false;await page.route(`**/api/preferences/${id}`,async route=>{if(route.request().method()==='PUT' && !rejected){rejected=true;await route.fulfill({status:409,json:{message:'Preferences changed'}});}else await route.continue();});
  await page.getByLabel('Transpose semitones').fill('4');
  await expect.poll(async()=>{const response=await page.request.get(`/api/preferences/${id}`);return (await response.json()).groups.performance.value.semitones;},{timeout:10000}).toBe(4);
  expect(rejected).toBe(true);
});

test('server edits mark a playable cached copy outdated until refresh', async ({page,context})=>{
  await page.goto('/');await page.getByLabel('Password').fill('synthetic test password');await page.getByRole('button',{name:'Sign in'}).click();
  const song=page.getByRole('listitem').filter({has:page.getByRole('link',{name:'Player Test',exact:true})}).first();await song.getByRole('button',{name:'Download for offline'}).click();await expect(song.getByText('Downloaded',{exact:true})).toBeVisible();
  const href=await song.getByRole('link',{name:'Player Test',exact:true}).getAttribute('href');const id=new URL(href!,'http://example.test').searchParams.get('id');const target=page.locator('li').filter({has:page.locator(`a[href^="/player?id=${id}"]`)});
  const before=await (await page.request.get(`/api/arrangements/${id}`)).json();const session=await (await page.request.get('/api/session')).json();
  const edit=await page.request.put(`/api/arrangements/${id}`,{headers:{'Origin':'http://127.0.0.1:4173','X-CSRF-Token':session.csrf,'If-Match':before.revision},data:{source:before.source+'\n[C]ChangedMarker'}});expect(edit.status()).toBe(200);
  await page.reload();await expect(target.getByText('Outdated',{exact:true})).toBeVisible();
  const cachedHref=await target.getByRole('link',{name:'Play cached copy'}).getAttribute('href');await page.goto(cachedHref!);await expect(page.getByTestId('song')).toContainText('Line-00');await page.goto('/');await expect(target.getByText('Outdated',{exact:true})).toBeVisible();
  await context.setOffline(true);await page.goto(href!);await expect(page.getByTestId('song')).toContainText('Line-00');await expect(page.getByTestId('song')).not.toContainText('ChangedMarker');
  await context.setOffline(false);await page.goto('/');await expect(target.getByText('Outdated',{exact:true})).toBeVisible();await target.getByRole('button',{name:'Refresh download'}).click();await expect(target.getByText('Downloaded',{exact:true})).toBeVisible();
  await context.setOffline(true);await page.goto(href!);await expect(page.getByTestId('song')).toContainText('ChangedMarker');
});

test('server deletion retains a clearly marked playable cached copy', async ({page,context})=>{
  await page.goto('/');await page.getByLabel('Password').fill('synthetic test password');await page.getByRole('button',{name:'Sign in'}).click();
  await expect(page.getByRole('heading',{name:'Library'})).toBeVisible();const isolated=await isolatedSong(page,'Deleted Song');await page.reload();
  const song=page.locator('li').filter({has:page.locator(`a[href^="/player?id=${isolated}"]`)});await song.getByRole('button',{name:'Download for offline'}).click();await expect(song.getByText('Downloaded',{exact:true})).toBeVisible();
  const href=await song.getByRole('link',{name:'Deleted Song',exact:true}).getAttribute('href');const id=new URL(href!,'http://example.test').searchParams.get('id');const session=await (await page.request.get('/api/session')).json();const meta=await (await page.request.get(`/api/arrangements/${id}/metadata`)).json();
  const removed=await page.request.delete(`/api/arrangements/${id}`,{headers:{'Origin':'http://127.0.0.1:4173','X-CSRF-Token':session.csrf},data:{revision:meta.revision}});expect(removed.status()).toBe(204);
  const cached=page.locator('li').filter({has:page.locator(`a[href^="/player?id=${id}"]`)});
  await page.reload();await expect(cached.getByText('Deleted',{exact:true})).toBeVisible();
  await context.setOffline(true);await page.goto('/');await expect(cached.getByText('Deleted',{exact:true})).toBeVisible();await cached.getByRole('link',{name:'Deleted Song',exact:true}).click();await expect(page.getByTestId('song')).toContainText('Deleted Song');
});

test('unauthorized sync does not imply deletion', async ({page})=>{
  await page.goto('/');await page.getByLabel('Password').fill('synthetic test password');await page.getByRole('button',{name:'Sign in'}).click();
  const song=page.getByRole('listitem').filter({has:page.getByRole('link',{name:'Player Test',exact:true})}).first();await song.getByRole('button',{name:'Download for offline'}).click();await expect(song.getByText('Downloaded',{exact:true})).toBeVisible();
  await page.addInitScript(()=>{const original=window.fetch.bind(window);window.fetch=(input,init)=>typeof input==='string' && input==='/api/sync/check' ? Promise.resolve(new Response(JSON.stringify({message:'expired'}),{status:401,headers:{'Content-Type':'application/json'}})) : original(input,init);});await page.reload();
  await expect(song.getByText('Sync unavailable',{exact:true})).toBeVisible();await expect(song.getByText('Deleted',{exact:true})).toHaveCount(0);
});

test('reconnection checks downloads without requiring a page reload', async ({page,context})=>{
  await page.goto('/');await page.getByLabel('Password').fill('synthetic test password');await page.getByRole('button',{name:'Sign in'}).click();
  const song=page.getByRole('listitem').filter({has:page.getByRole('link',{name:'Player Test',exact:true})}).first();await song.getByRole('button',{name:'Download for offline'}).click();await expect(song.getByText('Downloaded',{exact:true})).toBeVisible();
  const href=await song.getByRole('link',{name:'Player Test',exact:true}).getAttribute('href');const id=new URL(href!,'http://example.test').searchParams.get('id');
  const before=await (await page.request.get(`/api/arrangements/${id}`)).json();const session=await (await page.request.get('/api/session')).json();await context.setOffline(true);
  const edit=await page.request.put(`/api/arrangements/${id}`,{headers:{Origin:'http://127.0.0.1:4173','X-CSRF-Token':session.csrf,'If-Match':before.revision},data:{source:before.source+'\nReconnect change'}});expect(edit.status()).toBe(200);
  await context.setOffline(false);await expect(song.getByText('Outdated',{exact:true})).toBeVisible({timeout:10000});
});

test('a partially damaged set keeps its order and playable items', async ({page,context})=>{
  await page.goto('/setlists');await page.getByLabel('Password').fill('synthetic test password');await page.getByRole('button',{name:'Sign in'}).click();
  await page.getByLabel('Setlist title').fill('Partial set');await page.getByRole('button',{name:'Create setlist'}).click();
  await page.getByLabel('Choose arrangement').selectOption({label:'Player Test'});await page.getByRole('button',{name:'Add to setlist'}).click();await page.getByLabel('Choose arrangement').selectOption({label:'Browser Test'});await page.getByRole('button',{name:'Add to setlist'}).click();await page.getByRole('button',{name:'Save setlist'}).click();await expect(page.getByText('Setlist saved')).toBeVisible();
  await page.getByRole('button',{name:'Download setlist'}).click();await expect(page.getByText('Downloaded',{exact:true})).toBeVisible();const href=await page.getByRole('link',{name:'Play setlist'}).getAttribute('href');
  await page.evaluate(async()=>{const db=await new Promise<IDBDatabase>((resolve,reject)=>{const request=indexedDB.open('songbook-downloads-v1');request.onsuccess=()=>resolve(request.result);request.onerror=()=>reject(request.error);});await new Promise<void>((resolve,reject)=>{const tx=db.transaction('selections','readwrite'),store=tx.objectStore('selections'),request=store.getAll();request.onsuccess=()=>{const row=request.result.find(item=>item.manifest.selectionId.startsWith('setlist:'));row.manifest.snapshots[1].source+='corrupt';store.put(row);};tx.oncomplete=()=>resolve();tx.onerror=()=>reject(tx.error);});db.close();});
  await context.setOffline(true);await page.goto(href!);await expect(page.getByText('Song 1 of 2')).toBeVisible();await expect(page.getByTestId('song')).toContainText('Player Test');
  await page.getByRole('button',{name:'Next song'}).click();await expect(page.getByText('Song 2 of 2')).toBeVisible();await expect(page.getByText('Arrangement unavailable offline.')).toBeVisible();
});

test('server-deleted setlist item is marked partial but cached occurrence plays', async ({page,context})=>{
  await page.goto('/setlists');await page.getByLabel('Password').fill('synthetic test password');await page.getByRole('button',{name:'Sign in'}).click();const isolated=await isolatedSong(page,'Partial Song');await page.reload();await page.getByLabel('Setlist title').fill('Deleted item set');await page.getByRole('button',{name:'Create setlist'}).click();
  await page.getByLabel('Choose arrangement').selectOption(isolated);await page.getByRole('button',{name:'Add to setlist'}).click();await page.getByRole('button',{name:'Save setlist'}).click();await expect(page.getByText('Setlist saved')).toBeVisible();await page.getByRole('button',{name:'Download setlist'}).click();await expect(page.getByText('Downloaded',{exact:true})).toBeVisible();
  const href=await page.getByRole('link',{name:'Play setlist'}).getAttribute('href');const setId=new URL(href!,'http://example.test').searchParams.get('id');const playlist=await (await page.request.get(`/api/setlists/${setId}`)).json();const id=playlist.items[0].arrangementId;const session=await (await page.request.get('/api/session')).json();const meta=await (await page.request.get(`/api/arrangements/${id}/metadata`)).json();
  const removed=await page.request.delete(`/api/arrangements/${id}`,{headers:{Origin:'http://127.0.0.1:4173','X-CSRF-Token':session.csrf},data:{revision:meta.revision}});expect(removed.status()).toBe(204);
  await page.reload();await expect(page.getByText('Partial: some server songs are unavailable.')).toBeVisible();await context.setOffline(true);await page.goto(href!);await expect(page.getByText('Partial: some server songs are unavailable.')).toBeVisible();await expect(page.getByTestId('song')).toContainText('Partial Song');
});

test('changed set membership stays cached until explicit refresh', async ({page,context})=>{
  await page.goto('/setlists');await page.getByLabel('Password').fill('synthetic test password');await page.getByRole('button',{name:'Sign in'}).click();await page.getByLabel('Setlist title').fill('Changing set');await page.getByRole('button',{name:'Create setlist'}).click();
  await page.getByLabel('Choose arrangement').selectOption({label:'Player Test'});await page.getByRole('button',{name:'Add to setlist'}).click();await page.getByRole('button',{name:'Save setlist'}).click();await expect(page.getByText('Setlist saved')).toBeVisible();await page.getByRole('button',{name:'Download setlist'}).click();await expect(page.getByText('Downloaded',{exact:true})).toBeVisible();
  const href=await page.getByRole('link',{name:'Play setlist'}).getAttribute('href');const id=new URL(href!,'http://example.test').searchParams.get('id');const set=await (await page.request.get(`/api/setlists/${id}`)).json();const library=await (await page.request.get('/api/library')).json();const other=library.find((item:{title:string;source_only:boolean})=>item.title==='Browser Test'&&!item.source_only);const session=await (await page.request.get('/api/session')).json();
  const updated=await page.request.put(`/api/setlists/${id}`,{headers:{Origin:'http://127.0.0.1:4173','X-CSRF-Token':session.csrf},data:{title:set.title,revision:set.revision,items:[...set.items.map((item:{id:string;arrangementId:string})=>({id:item.id,arrangementId:item.arrangementId})),{id:crypto.randomUUID(),arrangementId:other.id}]}});expect(updated.status()).toBe(200);
  await page.reload();await expect(page.getByText('Downloaded setlist is outdated.')).toBeVisible();const cachedHref=await page.getByRole('link',{name:'Play cached setlist'}).getAttribute('href');await page.goto(cachedHref!);await expect(page.getByText('Song 1 of 1')).toBeVisible();
  await context.setOffline(true);await page.goto(href!);await expect(page.getByText('Song 1 of 1')).toBeVisible();
  await context.setOffline(false);await page.goto(`/setlists?id=${id}`);await expect(page.getByText('Downloaded setlist is outdated.')).toBeVisible();await page.getByRole('button',{name:'Refresh setlist'}).click();await expect(page.getByText('Downloaded',{exact:true})).toBeVisible();
  await context.setOffline(true);await page.goto(href!);await expect(page.getByText('Song 1 of 2')).toBeVisible();
});

test('setlist playback uses its own frozen revision when another selection is older', async ({page,context})=>{
  await page.goto('/');await page.getByLabel('Password').fill('synthetic test password');await page.getByRole('button',{name:'Sign in'}).click();
  const song=page.getByRole('listitem').filter({has:page.getByRole('link',{name:'Player Test',exact:true})}).first();await song.getByRole('button',{name:'Download for offline'}).click();await expect(song.getByText('Downloaded',{exact:true})).toBeVisible();const songHref=await song.getByRole('link',{name:'Player Test',exact:true}).getAttribute('href');const songId=new URL(songHref!,'http://example.test').searchParams.get('id');
  await page.goto('/setlists');await page.getByLabel('Setlist title').fill('Revision set');await page.getByRole('button',{name:'Create setlist'}).click();await page.getByLabel('Choose arrangement').selectOption(songId!);await page.getByRole('button',{name:'Add to setlist'}).click();await page.getByRole('button',{name:'Save setlist'}).click();await expect(page.getByText('Setlist saved')).toBeVisible();await page.getByRole('button',{name:'Download setlist'}).click();await expect(page.getByText('Downloaded',{exact:true})).toBeVisible();const setHref=await page.getByRole('link',{name:'Play setlist'}).getAttribute('href');
  const before=await (await page.request.get(`/api/arrangements/${songId}`)).json(),session=await (await page.request.get('/api/session')).json();const edit=await page.request.put(`/api/arrangements/${songId}`,{headers:{Origin:'http://127.0.0.1:4173','X-CSRF-Token':session.csrf,'If-Match':before.revision},data:{source:before.source+'\n[C]SetVersion'}});expect(edit.status()).toBe(200);
  await page.reload();await expect(page.getByText('Downloaded setlist is outdated.')).toBeVisible();await page.getByRole('button',{name:'Refresh setlist'}).click();await expect(page.getByText('Downloaded',{exact:true})).toBeVisible();
  await context.setOffline(true);await page.goto(setHref!);await expect(page.getByTestId('song')).toContainText('SetVersion');
});

test('unavailable preference sync leaves local performance settings usable', async ({page})=>{
  const {readFileSync}=await import('node:fs');const id=readFileSync('/private/tmp/songbook-auth-e2e-player-id','utf8');
  await page.goto('/');await page.getByLabel('Password').fill('synthetic test password');await page.getByRole('button',{name:'Sign in'}).click();await expect(page.getByRole('heading',{name:'Library'})).toBeVisible();
  await page.goto(`/player?id=${id}`);await page.getByLabel('Transpose semitones').fill('2');await expect(page.getByLabel('Transpose semitones')).toHaveValue('2');await page.waitForTimeout(700);
  await page.route(`**/api/preferences/${id}`,route=>route.fulfill({status:401,json:{message:'expired'}}));await page.reload();
  await expect(page.getByLabel('Transpose semitones')).toHaveValue('2');await expect(page.getByRole('alert')).toContainText('Preferences unavailable');
});

test('a deleted server setlist remains available as a marked cached set', async ({page,context})=>{
  await page.goto('/setlists');await page.getByLabel('Password').fill('synthetic test password');await page.getByRole('button',{name:'Sign in'}).click();await page.getByLabel('Setlist title').fill('Removed set');await page.getByRole('button',{name:'Create setlist'}).click();
  await page.getByLabel('Choose arrangement').selectOption({label:'Player Test'});await page.getByRole('button',{name:'Add to setlist'}).click();await page.getByRole('button',{name:'Save setlist'}).click();await expect(page.getByText('Setlist saved')).toBeVisible();await page.getByRole('button',{name:'Download setlist'}).click();await expect(page.getByText('Downloaded',{exact:true})).toBeVisible();
  const href=await page.getByRole('link',{name:'Play setlist'}).getAttribute('href');const id=new URL(href!,'http://example.test').searchParams.get('id');const set=await (await page.request.get(`/api/setlists/${id}`)).json();const session=await (await page.request.get('/api/session')).json();
  const removed=await page.request.delete(`/api/setlists/${id}`,{headers:{Origin:'http://127.0.0.1:4173','X-CSRF-Token':session.csrf},data:{revision:set.revision}});expect(removed.status()).toBe(204);
  await page.goto('/setlists');const row=page.getByRole('listitem').filter({has:page.getByRole('link',{name:'Removed set'})});await expect(row.getByText('Deleted',{exact:true})).toBeVisible();
  await context.setOffline(true);await page.goto('/setlists');await expect(page.getByText('Removed set')).toBeVisible();await page.getByRole('link',{name:'Removed set'}).click();await expect(page.getByTestId('song')).toContainText('Player Test');
});

test('download captures existing server performance preferences', async ({page,context})=>{
  await page.goto('/');await page.getByLabel('Password').fill('synthetic test password');await page.getByRole('button',{name:'Sign in'}).click();
  const song=page.getByRole('listitem').filter({has:page.getByRole('link',{name:'Player Test',exact:true})}).first();const href=await song.getByRole('link',{name:'Player Test',exact:true}).getAttribute('href');const id=new URL(href!,'http://example.test').searchParams.get('id');const session=await (await page.request.get('/api/session')).json();const response=await page.request.get(`/api/preferences/${id}`);const prefs=await response.json();prefs.groups.performance.value.semitones=5;prefs.groups.performance.updated_at=Date.now()/1000;prefs.groups.performance.device_id='other-device';
  const saved=await page.request.put(`/api/preferences/${id}`,{headers:{Origin:'http://127.0.0.1:4173','X-CSRF-Token':session.csrf,'If-Match':response.headers()['etag']},data:prefs});expect(saved.status()).toBe(200);
  await song.getByRole('button',{name:'Download for offline'}).click();await expect(song.getByText('Downloaded',{exact:true})).toBeVisible();await context.setOffline(true);await page.goto(href!);await expect(page.getByLabel('Transpose semitones')).toHaveValue('5');
});

test('equal-time conflicts converge to the lexically greater device id', async ({page,context})=>{
  await page.addInitScript(()=>{Date.now=()=>1700000000000;});
  await page.goto('/');await page.getByLabel('Password').fill('synthetic test password');await page.getByRole('button',{name:'Sign in'}).click();await page.evaluate(()=>localStorage.setItem('songbook-device-id','device-a'));
  const song=page.getByRole('listitem').filter({has:page.getByRole('link',{name:'Player Test',exact:true})}).first();await song.getByRole('button',{name:'Download for offline'}).click();await expect(song.getByText('Downloaded',{exact:true})).toBeVisible();const href=await song.getByRole('link',{name:'Player Test',exact:true}).getAttribute('href');const id=new URL(href!,'http://example.test').searchParams.get('id');
  const session=await (await page.request.get('/api/session')).json();const current=await page.request.get(`/api/preferences/${id}`);const remote=await current.json();
  await context.setOffline(true);await page.goto(href!);await page.getByLabel('Transpose semitones').fill('2');await expect(page.getByLabel('Transpose semitones')).toHaveValue('2');
  remote.groups.performance.value.semitones=7;remote.groups.performance.updated_at=1700000000;remote.groups.performance.device_id='device-z';
  const put=await page.request.put(`/api/preferences/${id}`,{headers:{Origin:'http://127.0.0.1:4173','X-CSRF-Token':session.csrf,'If-Match':current.headers()['etag']},data:remote});expect(put.status()).toBe(200);
  await context.setOffline(false);await expect(page.getByLabel('Transpose semitones')).toHaveValue('7',{timeout:10000});
  const result=await (await page.request.get(`/api/preferences/${id}`)).json();expect(result.groups.performance.value.semitones).toBe(7);expect(result.groups.performance.device_id).toBe('device-z');
});

test('individual playback prefers its own refreshed revision over an older set', async ({page,context})=>{
  await page.goto('/setlists');await page.getByLabel('Password').fill('synthetic test password');await page.getByRole('button',{name:'Sign in'}).click();await page.getByLabel('Setlist title').fill('Older set');await page.getByRole('button',{name:'Create setlist'}).click();await page.getByLabel('Choose arrangement').selectOption({label:'Player Test'});await page.getByRole('button',{name:'Add to setlist'}).click();await page.getByRole('button',{name:'Save setlist'}).click();await expect(page.getByText('Setlist saved')).toBeVisible();await page.getByRole('button',{name:'Download setlist'}).click();await expect(page.getByText('Downloaded',{exact:true})).toBeVisible();
  const setId=new URL((await page.getByRole('link',{name:'Play setlist'}).getAttribute('href'))!,'http://example.test').searchParams.get('id');const set=await (await page.request.get(`/api/setlists/${setId}`)).json();const id=set.items[0].arrangementId;const before=await (await page.request.get(`/api/arrangements/${id}`)).json(),session=await (await page.request.get('/api/session')).json();const edit=await page.request.put(`/api/arrangements/${id}`,{headers:{Origin:'http://127.0.0.1:4173','X-CSRF-Token':session.csrf,'If-Match':before.revision},data:{source:before.source+'\n[C]DirectVersion'}});expect(edit.status()).toBe(200);
  await page.goto('/');const row=page.locator('li').filter({has:page.locator(`a[href^="/player?id=${id}"]`)});await expect(row.getByText('Outdated',{exact:true})).toBeVisible();await row.getByRole('button',{name:'Download for offline'}).click();await expect(row.getByText('Downloaded',{exact:true})).toBeVisible();
  await page.reload();await expect(row.getByText('Downloaded',{exact:true})).toBeVisible();await expect(row.getByText('Outdated',{exact:true})).toHaveCount(0);
  await context.setOffline(true);await page.goto(`/player?id=${id}`);await expect(page.getByTestId('song')).toContainText('DirectVersion');
});

test('removing private downloads at sign-out also removes scoped preferences', async ({page})=>{
  await page.goto('/');await page.getByLabel('Password').fill('synthetic test password');await page.getByRole('button',{name:'Sign in'}).click();const song=page.getByRole('listitem').filter({has:page.getByRole('link',{name:'Player Test',exact:true})}).first();await song.getByRole('button',{name:'Download for offline'}).click();await expect(song.getByText('Downloaded',{exact:true})).toBeVisible();const scope=await page.evaluate(()=>localStorage.getItem('songbook-offline-scope'));const href=await song.getByRole('link',{name:'Player Test',exact:true}).getAttribute('href');
  await page.goto(href!);await page.getByLabel('Transpose semitones').fill('2');await expect(page.getByLabel('Transpose semitones')).toHaveValue('2');await page.goto('/');await page.getByRole('button',{name:'Sign out',exact:true}).click();await page.getByRole('button',{name:'Confirm sign out'}).click();await expect(page.getByRole('heading',{name:'Sign in'})).toBeVisible();
  const keys=await page.evaluate(async()=>{const db=await new Promise<IDBDatabase>((resolve,reject)=>{const req=indexedDB.open('songbook-downloads-v1');req.onsuccess=()=>resolve(req.result);req.onerror=()=>reject(req.error);});return new Promise<string[]>((resolve,reject)=>{const tx=db.transaction('meta','readonly'),req=tx.objectStore('meta').getAllKeys();tx.oncomplete=()=>{db.close();resolve(req.result.map(String));};tx.onerror=()=>reject(tx.error);});});
  expect(keys.filter(key=>key.includes(scope!))).toEqual([]);
});

test('failed refresh keeps the old copy visibly playable', async ({page})=>{
  await page.goto('/');await page.getByLabel('Password').fill('synthetic test password');await page.getByRole('button',{name:'Sign in'}).click();const song=page.getByRole('listitem').filter({has:page.getByRole('link',{name:'Player Test',exact:true})}).first();await song.getByRole('button',{name:'Download for offline'}).click();await expect(song.getByText('Downloaded',{exact:true})).toBeVisible();
  const href=await song.getByRole('link',{name:'Player Test',exact:true}).getAttribute('href');const id=new URL(href!,'http://example.test').searchParams.get('id');const before=await (await page.request.get(`/api/arrangements/${id}`)).json(),session=await (await page.request.get('/api/session')).json();const edit=await page.request.put(`/api/arrangements/${id}`,{headers:{Origin:'http://127.0.0.1:4173','X-CSRF-Token':session.csrf,'If-Match':before.revision},data:{source:before.source+'\nLater'}});expect(edit.status()).toBe(200);
  await page.reload();await expect(song.getByText('Outdated',{exact:true})).toBeVisible();await page.evaluate(id=>{const original=window.fetch.bind(window);window.fetch=(input,init)=>typeof input==='string' && input===`/api/downloads/arrangements/${id}` ? Promise.resolve(new Response(JSON.stringify({message:'expired'}),{status:401,headers:{'Content-Type':'application/json'}})) : original(input,init);},id);await song.getByRole('button',{name:'Refresh download'}).click();await expect(song.getByText('Download failed',{exact:true})).toBeVisible();await expect(song.getByRole('link',{name:'Play cached copy'})).toBeVisible();await song.getByRole('link',{name:'Play cached copy'}).click();await expect(page.getByTestId('song')).toContainText('Line-00');
});

test('set player reports server-deleted items on reconnect without reload', async ({page,context})=>{
  await page.goto('/setlists');await page.getByLabel('Password').fill('synthetic test password');await page.getByRole('button',{name:'Sign in'}).click();const isolated=await isolatedSong(page,'Reconnect Song');await page.reload();await page.getByLabel('Setlist title').fill('Reconnect set');await page.getByRole('button',{name:'Create setlist'}).click();await page.getByLabel('Choose arrangement').selectOption(isolated);await page.getByRole('button',{name:'Add to setlist'}).click();await page.getByRole('button',{name:'Save setlist'}).click();await expect(page.getByText('Setlist saved')).toBeVisible();await page.getByRole('button',{name:'Download setlist'}).click();await expect(page.getByText('Downloaded',{exact:true})).toBeVisible();const href=await page.getByRole('link',{name:'Play setlist'}).getAttribute('href');const setId=new URL(href!,'http://example.test').searchParams.get('id');const set=await (await page.request.get(`/api/setlists/${setId}`)).json();const id=set.items[0].arrangementId;const session=await (await page.request.get('/api/session')).json();await page.goto(href!);await expect(page.getByTestId('song')).toBeVisible();const meta=await (await page.request.get(`/api/arrangements/${id}/metadata`)).json();
  await context.setOffline(true);const removed=await page.request.delete(`/api/arrangements/${id}`,{headers:{Origin:'http://127.0.0.1:4173','X-CSRF-Token':session.csrf},data:{revision:meta.revision}});expect(removed.status()).toBe(204);await context.setOffline(false);
  await expect(page.getByText('Partial: some server songs are unavailable.')).toBeVisible({timeout:10000});await expect(page.getByTestId('song')).toBeVisible();
});


test('rapid changes within one preference group persist together', async ({page})=>{
  const id=readFileSync('/private/tmp/songbook-auth-e2e-player-id','utf8');await page.goto(`/player?id=${id}`);await page.getByLabel('Password').fill('synthetic test password');await page.getByRole('button',{name:'Sign in'}).click();
  await page.getByLabel(/Text size/).fill('32');await page.getByLabel('Columns').selectOption('2');await page.getByRole('button',{name:'Focus view'}).click();
  await expect(page.getByLabel(/Text size/)).toHaveValue('32');await expect(page.getByLabel('Columns')).toHaveValue('2');await page.waitForTimeout(700);await page.reload();
  await expect(page.getByLabel(/Text size/)).toHaveValue('32');await expect(page.getByLabel('Columns')).toHaveValue('2');await expect(page.getByRole('button',{name:'Exit focus'}).first()).toBeVisible();
});
