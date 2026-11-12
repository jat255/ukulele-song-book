import {test,expect} from '@playwright/test';

test('downloaded song opens and transposes after a cold offline reload', async ({page,context}) => {
  await page.goto('/');
  await page.getByLabel('Password').fill('synthetic test password');
  await page.getByRole('button',{name:'Sign in'}).click();
  const song=page.getByRole('listitem').filter({has:page.getByRole('link',{name:'Player Test',exact:true})}).first();
  await song.getByRole('button',{name:'Download for offline'}).click();
  await expect(song.getByText('Downloaded', {exact:true})).toBeVisible();
  const href=await song.getByRole('link',{name:'Player Test',exact:true}).getAttribute('href');
  const failedAssets:string[]=[];page.on('requestfailed',request=>{if(!new URL(request.url()).pathname.startsWith('/api/'))failedAssets.push(request.url());});
  await context.setOffline(true);
  await page.goto(href!);
  await expect(page.getByTestId('song')).toContainText('Player Test');
  await page.getByLabel('Transpose semitones').fill('2');
  await expect(page.getByTestId('song')).toContainText('D');
  await expect(page.getByRole('heading',{name:'Chords'})).toBeVisible();
  await page.getByRole('button',{name:'Start scrolling'}).click();
  await expect(page.getByRole('button',{name:'Pause scrolling'})).toBeVisible();
  expect(failedAssets).toEqual([]);
});

test('reports incomplete after browser cache eviction', async ({page}) => {
  await page.goto('/');
  await page.getByLabel('Password').fill('synthetic test password');
  await page.getByRole('button',{name:'Sign in'}).click();
  const song=page.getByRole('listitem').filter({has:page.getByRole('link',{name:'Player Test',exact:true})}).first();
  await song.getByRole('button',{name:'Download for offline'}).click();
  await expect(song.getByText('Downloaded',{exact:true})).toBeVisible();
  await page.evaluate(async()=>{for(const name of await caches.keys())if(name.startsWith('songbook-private-'))await caches.delete(name);});
  await page.reload();
  await expect(song.getByText('Incomplete',{exact:true})).toBeVisible();
});

test('failed refresh preserves the previous verified download', async ({page}) => {
  await page.goto('/');
  await page.getByLabel('Password').fill('synthetic test password');
  await page.getByRole('button',{name:'Sign in'}).click();
  const song=page.getByRole('listitem').filter({has:page.getByRole('link',{name:'Player Test',exact:true})}).first();
  await song.getByRole('button',{name:'Download for offline'}).click();
  await expect(song.getByText('Downloaded',{exact:true})).toBeVisible();
  await page.route('**/api/downloads/arrangements/*',async route=>{
    const response=await route.fetch();const data=await response.json();data.snapshots[0].source+='corruption';
    await route.fulfill({response,json:data});
  });
  await song.getByRole('button',{name:'Download for offline'}).click();
  await expect(song.getByText('Download failed',{exact:true})).toBeVisible();
  await page.unrouteAll();
  await page.reload();
  await expect(song.getByText('Downloaded',{exact:true})).toBeVisible();
});

test('sign out removes private downloads by default', async ({page}) => {
  await page.goto('/');
  await page.getByLabel('Password').fill('synthetic test password');
  await page.getByRole('button',{name:'Sign in'}).click();
  const song=page.getByRole('listitem').filter({has:page.getByRole('link',{name:'Player Test',exact:true})}).first();
  await song.getByRole('button',{name:'Download for offline'}).click();
  await expect(song.getByText('Downloaded',{exact:true})).toBeVisible();
  await page.getByRole('button',{name:'Sign out',exact:true}).click();
  await expect(page.getByLabel('Remove private downloads')).toBeChecked();
  await page.getByRole('button',{name:'Confirm sign out'}).click();
  await expect(page.getByRole('heading',{name:'Sign in'})).toBeVisible();
  expect(await page.evaluate(()=>localStorage.getItem('songbook-offline-scope'))).toBeNull();
});

test('downloaded setlist retains repeated occurrences offline', async ({page,context}) => {
  await page.goto('/setlists');
  await page.getByLabel('Password').fill('synthetic test password');
  await page.getByRole('button',{name:'Sign in'}).click();
  await page.getByLabel('Setlist title').fill('Offline set');
  await page.getByRole('button',{name:'Create setlist'}).click();
  await page.getByLabel('Choose arrangement').selectOption({label:'Player Test'});
  await page.getByRole('button',{name:'Add to setlist'}).click();
  await page.getByRole('button',{name:'Add to setlist'}).click();
  await page.getByRole('button',{name:'Save setlist'}).click();
  await expect(page.getByText('Setlist saved')).toBeVisible();
  await page.getByRole('button',{name:'Download setlist'}).click();
  await expect(page.getByText('Downloaded',{exact:true})).toBeVisible();
  const href=await page.getByRole('link',{name:'Play setlist'}).getAttribute('href');
  await context.setOffline(true);
  await page.goto('/setlists');
  await expect(page.getByRole('link',{name:'Offline set'})).toBeVisible();
  await page.goto(href!);
  await expect(page.getByText('Song 1 of 2')).toBeVisible();
  await expect(page.getByTestId('song')).toContainText('Player Test');
  await page.getByRole('button',{name:'Next song'}).click();
  await expect(page.getByText('Song 2 of 2')).toBeVisible();
  await expect(page.getByTestId('song')).toContainText('Player Test');
});

test('reports incomplete after a required shell font is evicted', async ({page}) => {
  await page.goto('/');
  await page.getByLabel('Password').fill('synthetic test password');
  await page.getByRole('button',{name:'Sign in'}).click();
  const song=page.getByRole('listitem').filter({has:page.getByRole('link',{name:'Player Test',exact:true})}).first();
  await song.getByRole('button',{name:'Download for offline'}).click();
  await expect(song.getByText('Downloaded',{exact:true})).toBeVisible();
  await page.evaluate(async()=>{const shell=localStorage.getItem('songbook-active-shell')!;await (await caches.open(shell)).delete('/fonts/NotoSerif-Regular.ttf');});
  await page.reload();
  await expect(song.getByText('Incomplete',{exact:true})).toBeVisible();
});

test('cleanup failure after publishing a refresh leaves the new download intact', async ({page}) => {
  await page.goto('/');
  await page.getByLabel('Password').fill('synthetic test password');
  await page.getByRole('button',{name:'Sign in'}).click();
  const song=page.getByRole('listitem').filter({has:page.getByRole('link',{name:'Player Test',exact:true})}).first();
  await song.getByRole('button',{name:'Download for offline'}).click();
  await expect(song.getByText('Downloaded',{exact:true})).toBeVisible();
  await page.evaluate(()=>{const original=caches.delete.bind(caches);let failed=false;caches.delete=async name=>{if(!failed && name.startsWith('songbook-private-')){failed=true;throw new Error('cleanup failed');}return original(name);};});
  await song.getByRole('button',{name:'Download for offline'}).click();
  await expect(song.getByText('Downloaded',{exact:true})).toBeVisible();
  await page.reload();
  await expect(song.getByText('Downloaded',{exact:true})).toBeVisible();
});

test('startup reconciles an abandoned staged download', async ({page}) => {
  await page.goto('/');
  await page.getByLabel('Password').fill('synthetic test password');
  await page.getByRole('button',{name:'Sign in'}).click();
  const song=page.getByRole('listitem').filter({has:page.getByRole('link',{name:'Player Test',exact:true})}).first();
  await song.getByRole('button',{name:'Download for offline'}).click();
  await expect(song.getByText('Downloaded',{exact:true})).toBeVisible();
  await page.evaluate(async()=>{
    await caches.open('songbook-private-abandoned');
    const db=await new Promise<IDBDatabase>((resolve,reject)=>{const r=indexedDB.open('songbook-downloads-v1');r.onsuccess=()=>resolve(r.result);r.onerror=()=>reject(r.error);});
    await new Promise<void>((resolve,reject)=>{const tx=db.transaction('staging','readwrite');tx.objectStore('staging').put({cacheName:'songbook-private-abandoned',startedAt:0});tx.oncomplete=()=>resolve();tx.onerror=()=>reject(tx.error);});db.close();
  });
  await page.reload();
  await expect.poll(()=>page.evaluate(()=>caches.has('songbook-private-abandoned'))).toBe(false);
  await expect(song.getByText('Downloaded',{exact:true})).toBeVisible();
});

test('offline editing requires connection and downloaded song can browser print', async ({page,context}) => {
  await page.goto('/');
  await page.getByLabel('Password').fill('synthetic test password');
  await page.getByRole('button',{name:'Sign in'}).click();
  const song=page.getByRole('listitem').filter({has:page.getByRole('link',{name:'Player Test',exact:true})}).first();
  await song.getByRole('button',{name:'Download for offline'}).click();
  await expect(song.getByText('Downloaded',{exact:true})).toBeVisible();
  const href=await song.getByRole('link',{name:'Player Test',exact:true}).getAttribute('href');
  const id=new URL(href!, 'http://example.test').searchParams.get('id');
  await context.setOffline(true);
  await page.goto(`/edit?id=${id}`);
  await expect(page.getByText('A connection is required for editing.')).toBeVisible();
  await page.goto(`/print?id=${id}`);
  await expect(page.getByText('Server PDF generation requires a connection.')).toBeVisible();
  await expect(page.getByRole('button',{name:'Browser print'})).toBeEnabled();
  await page.emulateMedia({media:'print'});
  const pdf=await page.pdf({preferCSSPageSize:true});
  expect(pdf.length).toBeGreaterThan(1000);
});

test('can include a verified original PDF explicitly', async ({page}) => {
  const {readFileSync}=await import('node:fs');
  const id=readFileSync('/private/tmp/songbook-auth-e2e-arrangement-id','utf8');
  await page.goto('/');
  await page.getByLabel('Password').fill('synthetic test password');
  await page.getByRole('button',{name:'Sign in'}).click();
  const song=page.locator('li').filter({has:page.locator(`a[href="/player?id=${id}"]`)});
  await song.getByLabel('Include original PDF').check();
  await song.getByRole('button',{name:'Download for offline'}).click();
  await expect(song.getByText('Downloaded',{exact:true})).toBeVisible();
  const count=await page.evaluate(async()=>{const names=(await caches.keys()).filter(name=>name.startsWith('songbook-private-'));let count=0;for(const name of names)count+=(await (await caches.open(name)).keys()).length;return count;});
  expect(count).toBe(1);
});

test('removing a download makes it online-only again', async ({page}) => {
  await page.goto('/');
  await page.getByLabel('Password').fill('synthetic test password');
  await page.getByRole('button',{name:'Sign in'}).click();
  const song=page.getByRole('listitem').filter({has:page.getByRole('link',{name:'Player Test',exact:true})}).first();
  await song.getByRole('button',{name:'Download for offline'}).click();
  await expect(song.getByText('Downloaded',{exact:true})).toBeVisible();
  await song.getByRole('button',{name:'Remove download'}).click();
  await expect(song.getByText('Online only',{exact:true})).toBeVisible();
  await page.reload();
  await expect(song.getByText('Online only',{exact:true})).toBeVisible();
});

test('shared originals are deduplicated and survive removing one selection', async ({page}) => {
  const {readFileSync}=await import('node:fs');
  const id=readFileSync('/private/tmp/songbook-auth-e2e-arrangement-id','utf8');
  await page.goto('/');
  await page.getByLabel('Password').fill('synthetic test password');
  await page.getByRole('button',{name:'Sign in'}).click();
  const song=page.locator('li').filter({has:page.locator(`a[href="/player?id=${id}"]`)});
  await song.getByLabel('Include original PDF').check();
  await song.getByRole('button',{name:'Download for offline'}).click();
  await expect(song.getByText('Downloaded',{exact:true})).toBeVisible();
  const result=await page.evaluate(async id=>{
    const api=await import('/src/offline/downloads.ts');
    const manifest=await (await fetch(`/api/downloads/arrangements/${id}`)).json();
    await api.downloadSelection({...manifest,selectionId:'another-selection'},true);
    const names=(await caches.keys()).filter(name=>name.startsWith('songbook-private-'));
    let total=0;for(const name of names)total+=(await (await caches.open(name)).keys()).length;
    await api.removeDownload(`arrangement:${id}`);
    return {total,status:await api.verifyAvailability('another-selection')};
  },id);
  expect(result.total).toBe(1);
  expect(result.status).toBe('downloaded');
});

test('offline library lists downloaded songs after a cold reload', async ({page,context}) => {
  await page.goto('/');
  await page.getByLabel('Password').fill('synthetic test password');
  await page.getByRole('button',{name:'Sign in'}).click();
  const song=page.getByRole('listitem').filter({has:page.getByRole('link',{name:'Player Test',exact:true})}).first();
  await song.getByRole('button',{name:'Download for offline'}).click();
  await expect(song.getByText('Downloaded',{exact:true})).toBeVisible();
  await context.setOffline(true);
  await page.goto('/');
  await expect(page.getByRole('link',{name:'Player Test',exact:true})).toBeVisible();
  await page.getByRole('link',{name:'Player Test',exact:true}).click();
  await expect(page.getByTestId('song')).toContainText('Player Test');
});

test('a different library identity cannot read prior private downloads', async ({page,context}) => {
  await page.goto('/');
  await page.getByLabel('Password').fill('synthetic test password');
  await page.getByRole('button',{name:'Sign in'}).click();
  const song=page.getByRole('listitem').filter({has:page.getByRole('link',{name:'Player Test',exact:true})}).first();
  await song.getByRole('button',{name:'Download for offline'}).click();
  await expect(song.getByText('Downloaded',{exact:true})).toBeVisible();
  await page.route('**/api/downloads/identity',route=>route.fulfill({json:{libraryId:'different-library',principalId:'owner'}}));
  await page.reload();
  await expect(song.getByText('Online only',{exact:true})).toBeVisible();
  await context.setOffline(true);
  await page.goto('/');
  await expect(page.getByRole('heading',{name:'Sign in'})).toBeVisible();
});

test('quota failure never publishes a partial download', async ({page}) => {
  await page.goto('/');
  await page.getByLabel('Password').fill('synthetic test password');
  await page.getByRole('button',{name:'Sign in'}).click();
  const song=page.getByRole('listitem').filter({has:page.getByRole('link',{name:'Player Test',exact:true})}).first();
  await page.evaluate(()=>{const original=IDBObjectStore.prototype.put;IDBObjectStore.prototype.put=function(...args){if(this.name==='selections')throw new DOMException('quota','QuotaExceededError');return original.apply(this,args);};});
  await song.getByRole('button',{name:'Download for offline'}).click();
  await expect(song.getByText('Download failed',{exact:true})).toBeVisible();
  await page.reload();
  await expect(song.getByText('Incomplete',{exact:true})).toBeVisible();
  await song.getByRole('button',{name:'Remove download'}).click();
  await expect(song.getByText('Online only',{exact:true})).toBeVisible();
  await page.reload();await expect(song.getByText('Online only',{exact:true})).toBeVisible();
});

test('a clean browser is not promised offline first login', async ({page,context}) => {
  await context.setOffline(true);
  await expect(page.goto('/')).rejects.toThrow();
});

test('a song downloaded through a setlist is shown as available', async ({page}) => {
  await page.goto('/setlists');
  await page.getByLabel('Password').fill('synthetic test password');
  await page.getByRole('button',{name:'Sign in'}).click();
  await page.getByLabel('Setlist title').fill('Shared set');
  await page.getByRole('button',{name:'Create setlist'}).click();
  await page.getByLabel('Choose arrangement').selectOption({label:'Player Test'});
  await page.getByRole('button',{name:'Add to setlist'}).click();
  await page.getByRole('button',{name:'Save setlist'}).click();
  await expect(page.getByText('Setlist saved')).toBeVisible();
  await page.getByRole('button',{name:'Download setlist'}).click();
  await expect(page.getByText('Downloaded',{exact:true})).toBeVisible();
  await page.goto('/');
  const song=page.getByRole('listitem').filter({has:page.getByRole('link',{name:'Player Test',exact:true})}).first();
  await expect(song.getByText('Downloaded',{exact:true})).toBeVisible();
});

test('a failed refresh does not replace the working offline shell', async ({page,context}) => {
  await page.goto('/');
  await page.getByLabel('Password').fill('synthetic test password');
  await page.getByRole('button',{name:'Sign in'}).click();
  const song=page.getByRole('listitem').filter({has:page.getByRole('link',{name:'Player Test',exact:true})}).first();
  await song.getByRole('button',{name:'Download for offline'}).click();
  await expect(song.getByText('Downloaded',{exact:true})).toBeVisible();
  await page.route('**/api/downloads/arrangements/*',async route=>{const response=await route.fetch();const data=await response.json();data.snapshots[0].source+='corrupt';await route.fulfill({response,json:data});});
  await page.evaluate(()=>{const original=window.fetch.bind(window);window.fetch=(input,init)=>input==='/' ? Promise.resolve(new Response('<h1>new shell unavailable</h1>',{headers:{'Content-Type':'text/html'}})) : original(input,init);});
  await song.getByRole('button',{name:'Download for offline'}).click();
  await expect(song.getByText('Download failed',{exact:true})).toBeVisible();
  await page.unrouteAll();
  await context.setOffline(true);
  await page.goto('/');
  await expect(page.getByRole('link',{name:'Player Test',exact:true})).toBeVisible();
});

test('missing active shell makes all offline status incomplete', async ({page}) => {
  await page.goto('/');
  await page.getByLabel('Password').fill('synthetic test password');
  await page.getByRole('button',{name:'Sign in'}).click();
  const song=page.getByRole('listitem').filter({has:page.getByRole('link',{name:'Player Test',exact:true})}).first();
  await song.getByRole('button',{name:'Download for offline'}).click();
  await expect(song.getByText('Downloaded',{exact:true})).toBeVisible();
  const other=page.getByRole('listitem').filter({has:page.getByRole('link',{name:'Browser Test',exact:true})}).first();
  await other.getByRole('button',{name:'Download for offline'}).click();
  await expect(other.getByText('Downloaded',{exact:true})).toBeVisible();
  await page.evaluate(async()=>{const name=localStorage.getItem('songbook-active-shell');if(name)await caches.delete(name);});
  await page.reload();
  await expect(song.getByText('Incomplete',{exact:true})).toBeVisible();
});

test('sign out removes originals when browser locks are unavailable', async ({page}) => {
  const {readFileSync}=await import('node:fs');const id=readFileSync('/private/tmp/songbook-auth-e2e-arrangement-id','utf8');
  await page.goto('/');
  await page.getByLabel('Password').fill('synthetic test password');
  await page.getByRole('button',{name:'Sign in'}).click();
  await page.evaluate(()=>Object.defineProperty(navigator,'locks',{value:undefined,configurable:true}));
  const song=page.locator('li').filter({has:page.locator(`a[href="/player?id=${id}"]`)});
  await song.getByLabel('Include original PDF').check();
  await song.getByRole('button',{name:'Download for offline'}).click();
  await expect(song.getByText('Downloaded',{exact:true})).toBeVisible();
  await page.getByRole('button',{name:'Sign out',exact:true}).click();
  await page.getByRole('button',{name:'Confirm sign out'}).click();
  await expect(page.getByRole('heading',{name:'Sign in'})).toBeVisible();
  const count=await page.evaluate(async()=>{let total=0;for(const name of await caches.keys())if(name.startsWith('songbook-private-'))total+=(await (await caches.open(name)).keys()).length;return total;});
  expect(count).toBe(0);
});

test('sign-out reports local cleanup failure after revoking session', async ({page}) => {
  await page.goto('/');
  await page.getByLabel('Password').fill('synthetic test password');
  await page.getByRole('button',{name:'Sign in'}).click();
  const song=page.getByRole('listitem').filter({has:page.getByRole('link',{name:'Player Test',exact:true})}).first();
  await song.getByRole('button',{name:'Download for offline'}).click();
  await expect(song.getByText('Downloaded',{exact:true})).toBeVisible();
  await page.evaluate(()=>{caches.delete=async()=>{throw new Error('blocked');};});
  await page.getByRole('button',{name:'Sign out',exact:true}).click();
  await page.getByRole('button',{name:'Confirm sign out'}).click();
  await expect(page.getByRole('heading',{name:'Sign in'})).toBeVisible();
  await expect(page.getByRole('alert')).toContainText('could not remove');
  expect((await page.request.get('/api/session')).status()).toBe(401);
});

test('reports incomplete when a cached font is corrupted', async ({page}) => {
  await page.goto('/');
  await page.getByLabel('Password').fill('synthetic test password');
  await page.getByRole('button',{name:'Sign in'}).click();
  const song=page.getByRole('listitem').filter({has:page.getByRole('link',{name:'Player Test',exact:true})}).first();
  await song.getByRole('button',{name:'Download for offline'}).click();
  await expect(song.getByText('Downloaded',{exact:true})).toBeVisible();
  await page.evaluate(async()=>{const name=localStorage.getItem('songbook-active-shell')!;await (await caches.open(name)).put('/fonts/NotoSerif-Regular.ttf',new Response('corrupt'));});
  await page.reload();
  await expect(song.getByText('Incomplete',{exact:true})).toBeVisible();
});

test('sign out removes shared leftovers after individual removal without locks', async ({page}) => {
  const {readFileSync}=await import('node:fs');const id=readFileSync('/private/tmp/songbook-auth-e2e-arrangement-id','utf8');
  await page.goto('/');await page.getByLabel('Password').fill('synthetic test password');await page.getByRole('button',{name:'Sign in'}).click();
  await page.evaluate(()=>Object.defineProperty(navigator,'locks',{value:undefined,configurable:true}));
  const song=page.locator('li').filter({has:page.locator(`a[href="/player?id=${id}"]`)});
  await song.getByLabel('Include original PDF').check();await song.getByRole('button',{name:'Download for offline'}).click();
  await expect(song.getByText('Downloaded',{exact:true})).toBeVisible();await song.getByRole('button',{name:'Remove download'}).click();
  await expect(song.getByText('Online only',{exact:true})).toBeVisible();
  await page.getByRole('button',{name:'Sign out',exact:true}).click();await page.getByRole('button',{name:'Confirm sign out'}).click();
  await expect(page.getByRole('heading',{name:'Sign in'})).toBeVisible();
  const count=await page.evaluate(async()=>{let total=0;for(const name of await caches.keys())if(name.startsWith('songbook-private-'))total+=(await (await caches.open(name)).keys()).length;return total;});
  expect(count).toBe(0);
});

test('an explicitly downloaded original is accessible offline', async ({page,context}) => {
  const {readFileSync}=await import('node:fs');const id=readFileSync('/private/tmp/songbook-auth-e2e-arrangement-id','utf8');
  await page.goto('/');await page.getByLabel('Password').fill('synthetic test password');await page.getByRole('button',{name:'Sign in'}).click();
  const song=page.locator('li').filter({has:page.locator(`a[href="/player?id=${id}"]`)});
  await song.getByLabel('Include original PDF').check();await song.getByRole('button',{name:'Download for offline'}).click();
  await expect(song.getByText('Downloaded',{exact:true})).toBeVisible();await context.setOffline(true);await page.goto(`/player?id=${id}`);
  const link=page.getByRole('link',{name:'Open downloaded original'});await expect(link).toBeVisible();
  const size=await link.evaluate(async node=>(await (await fetch((node as HTMLAnchorElement).href)).blob()).size);
  expect(size).toBeGreaterThan(0);
});

test('service worker update preserves verified downloads', async ({page,context}) => {
  await page.goto('/');await page.getByLabel('Password').fill('synthetic test password');await page.getByRole('button',{name:'Sign in'}).click();
  const song=page.getByRole('listitem').filter({has:page.getByRole('link',{name:'Player Test',exact:true})}).first();
  await song.getByRole('button',{name:'Download for offline'}).click();await expect(song.getByText('Downloaded',{exact:true})).toBeVisible();
  const href=await song.getByRole('link',{name:'Player Test',exact:true}).getAttribute('href');
  await page.evaluate(async()=>{await navigator.serviceWorker.register('/sw.js?version=2');await new Promise<void>(resolve=>{if(navigator.serviceWorker.controller?.scriptURL.includes('version=2'))resolve();else navigator.serviceWorker.addEventListener('controllerchange',()=>resolve(),{once:true});});});
  await context.setOffline(true);await page.goto(href!);await expect(page.getByTestId('song')).toContainText('Player Test');
});

test('sign-out cleanup cannot delete an asset another tab is publishing', async ({page,context}) => {
  const {readFileSync}=await import('node:fs');const id=readFileSync('/private/tmp/songbook-auth-e2e-arrangement-id','utf8');
  await page.goto('/');await page.getByLabel('Password').fill('synthetic test password');await page.getByRole('button',{name:'Sign in'}).click();
  const song=page.locator('li').filter({has:page.locator(`a[href="/player?id=${id}"]`)});await song.getByLabel('Include original PDF').check();await song.getByRole('button',{name:'Download for offline'}).click();await expect(song.getByText('Downloaded',{exact:true})).toBeVisible();
  const other=await context.newPage();await other.goto('/');
  await page.evaluate(async()=>{const api=await import('/src/offline/downloads.ts');const real=caches.delete.bind(caches);(window as any).blocked=false;caches.delete=async name=>{if(name.startsWith('songbook-private-shared-') && !(window as any).blocked){(window as any).blocked=true;await new Promise<void>(resolve=>(window as any).releaseCleanup=resolve);}return real(name);};(window as any).cleanup=api.removeAllDownloads();});
  await expect.poll(()=>page.evaluate(()=>(window as any).blocked)).toBe(true);
  const pending=other.evaluate(async id=>{const api=await import('/src/offline/downloads.ts');const manifest=await (await fetch(`/api/downloads/arrangements/${id}`)).json();await api.downloadSelection({...manifest,selectionId:'race'},true);return api.verifyAvailability('race');},id);
  await page.waitForTimeout(300);
  await page.evaluate(()=>(window as any).releaseCleanup());
  await page.evaluate(()=>(window as any).cleanup);
  await pending;
  expect(await other.evaluate(async()=>{const api=await import('/src/offline/downloads.ts');return api.verifyAvailability('race');})).toBe('downloaded');
  await other.close();
});

test('setlist download requires saving pending edits', async ({page}) => {
  await page.goto('/setlists');await page.getByLabel('Password').fill('synthetic test password');await page.getByRole('button',{name:'Sign in'}).click();
  await page.getByLabel('Setlist title').fill('Unsaved set');await page.getByRole('button',{name:'Create setlist'}).click();
  await page.getByLabel('Choose arrangement').selectOption({label:'Player Test'});await page.getByRole('button',{name:'Add to setlist'}).click();
  await expect(page.getByRole('button',{name:'Download setlist'})).toBeDisabled();
  await page.getByRole('button',{name:'Save setlist'}).click();await expect(page.getByText('Setlist saved')).toBeVisible();
  await expect(page.getByRole('button',{name:'Download setlist'})).toBeEnabled();
});

test('offline player cannot save a source variant', async ({page,context}) => {
  const {readFileSync}=await import('node:fs');const id=readFileSync('/private/tmp/songbook-auth-e2e-arrangement-id','utf8');
  await page.goto('/');await page.getByLabel('Password').fill('synthetic test password');await page.getByRole('button',{name:'Sign in'}).click();
  const song=page.locator('li').filter({has:page.locator(`a[href="/player?id=${id}"]`)});await song.getByRole('button',{name:'Download for offline'}).click();await expect(song.getByText('Downloaded',{exact:true})).toBeVisible();
  await context.setOffline(true);await page.goto(`/player?id=${id}`);await page.getByRole('button',{name:'Save transposed variant'}).click();
  await expect(page.getByRole('alert')).toContainText('connection');
});

test('a downloaded setlist can be removed from offline storage', async ({page}) => {
  await page.goto('/setlists');await page.getByLabel('Password').fill('synthetic test password');await page.getByRole('button',{name:'Sign in'}).click();
  await page.getByLabel('Setlist title').fill('Remove set');await page.getByRole('button',{name:'Create setlist'}).click();
  await page.getByLabel('Choose arrangement').selectOption({label:'Player Test'});await page.getByRole('button',{name:'Add to setlist'}).click();
  await page.getByRole('button',{name:'Save setlist'}).click();await expect(page.getByText('Setlist saved')).toBeVisible();
  await page.getByRole('button',{name:'Download setlist'}).click();await expect(page.getByText('Downloaded',{exact:true})).toBeVisible();
  await page.getByRole('button',{name:'Remove setlist download'}).click();await expect(page.getByText('Online only',{exact:true})).toBeVisible();
  await page.reload();await expect(page.getByText('Online only',{exact:true})).toBeVisible();
});

test('setlist download reports a revision changed on the server', async ({page}) => {
  await page.goto('/setlists');await page.getByLabel('Password').fill('synthetic test password');await page.getByRole('button',{name:'Sign in'}).click();
  await page.getByLabel('Setlist title').fill('Stale set');await page.getByRole('button',{name:'Create setlist'}).click();
  await page.getByLabel('Choose arrangement').selectOption({label:'Player Test'});await page.getByRole('button',{name:'Add to setlist'}).click();await page.getByRole('button',{name:'Save setlist'}).click();await expect(page.getByText('Setlist saved')).toBeVisible();
  await page.route('**/api/downloads/setlists/*',async route=>{const response=await route.fetch();const body=await response.json();body.setlist.revision='changed';await route.fulfill({response,json:body});});
  await page.getByRole('button',{name:'Download setlist'}).click();await expect(page.getByText('Setlist changed. Reload before downloading.')).toBeVisible();
});

test('cleanup serializes across tabs without browser locks', async ({page,context}) => {
  const {readFileSync}=await import('node:fs');const id=readFileSync('/private/tmp/songbook-auth-e2e-arrangement-id','utf8');
  await page.goto('/');await page.getByLabel('Password').fill('synthetic test password');await page.getByRole('button',{name:'Sign in'}).click();
  const song=page.locator('li').filter({has:page.locator(`a[href="/player?id=${id}"]`)});await song.getByLabel('Include original PDF').check();await song.getByRole('button',{name:'Download for offline'}).click();await expect(song.getByText('Downloaded',{exact:true})).toBeVisible();
  const other=await context.newPage();await other.goto('/');await page.evaluate(()=>Object.defineProperty(navigator,'locks',{value:undefined,configurable:true}));await other.evaluate(()=>Object.defineProperty(navigator,'locks',{value:undefined,configurable:true}));
  await page.evaluate(async()=>{const api=await import('/src/offline/downloads.ts');const real=caches.delete.bind(caches);(window as any).blocked=false;caches.delete=async name=>{if(name.startsWith('songbook-private-shared-') && !(window as any).blocked){(window as any).blocked=true;await new Promise<void>(resolve=>(window as any).releaseCleanup=resolve);}return real(name);};(window as any).cleanup=api.removeAllDownloads();});
  await expect.poll(()=>page.evaluate(()=>(window as any).blocked)).toBe(true);
  const pending=other.evaluate(async id=>{const api=await import('/src/offline/downloads.ts');const manifest=await (await fetch(`/api/downloads/arrangements/${id}`)).json();await api.downloadSelection({...manifest,selectionId:'race'},true);return api.verifyAvailability('race');},id);
  await page.waitForTimeout(300);
  await page.evaluate(()=>(window as any).releaseCleanup());
  await page.evaluate(()=>(window as any).cleanup);
  await pending;
  expect(await other.evaluate(async()=>{const api=await import('/src/offline/downloads.ts');return api.verifyAvailability('race');})).toBe('downloaded');
  await other.close();
});


test('refresh without originals removes an unreferenced shared original', async ({page}) => {
  const {readFileSync}=await import('node:fs');const id=readFileSync('/private/tmp/songbook-auth-e2e-arrangement-id','utf8');
  await page.goto('/');await page.getByLabel('Password').fill('synthetic test password');await page.getByRole('button',{name:'Sign in'}).click();
  const song=page.locator('li').filter({has:page.locator(`a[href="/player?id=${id}"]`)});
  await song.getByLabel('Include original PDF').check();await song.getByRole('button',{name:'Download for offline'}).click();await expect(song.getByText('Downloaded',{exact:true})).toBeVisible();
  await song.getByLabel('Include original PDF').uncheck();await song.getByRole('button',{name:'Download for offline'}).click();await expect(song.getByText('Downloaded',{exact:true})).toBeVisible();
  const count=await page.evaluate(async()=>{let total=0;for(const name of await caches.keys())if(name.startsWith('songbook-private-shared-'))total+=(await (await caches.open(name)).keys()).length;return total;});expect(count).toBe(0);
});

test('sign-out can explicitly retain a local private copy', async ({page,context}) => {
  await page.goto('/');await page.getByLabel('Password').fill('synthetic test password');await page.getByRole('button',{name:'Sign in'}).click();
  const song=page.getByRole('listitem').filter({has:page.getByRole('link',{name:'Player Test',exact:true})}).first();await song.getByRole('button',{name:'Download for offline'}).click();await expect(song.getByText('Downloaded',{exact:true})).toBeVisible();
  await page.getByRole('button',{name:'Sign out',exact:true}).click();await expect(page.getByText('Retained downloads remain private copies on this device.')).toBeVisible();await page.getByLabel('Remove private downloads').uncheck();await page.getByRole('button',{name:'Confirm sign out'}).click();await expect(page.getByRole('heading',{name:'Sign in'})).toBeVisible();
  await context.setOffline(true);await page.goto('/');await expect(page.getByRole('link',{name:'Player Test',exact:true})).toBeVisible();
});
