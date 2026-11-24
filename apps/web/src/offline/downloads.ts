import {openDb,transaction,metaRequest} from './db';
import {fromServerEnvelope,mergeLocalPreference} from './preferences';
export {openDb,transaction,metaRequest} from './db';
export type Snapshot={id:string; song_id:string; revision:string; source:string; sha256:string; size:number; mime:string; source_refs?:{source_id:string;crop_asset_id?:string|null}[]};
export type Asset={id:string;url:string;sha256:string;size:number|null;mime:string;optional:boolean;available:boolean};
export type DownloadManifest={schemaVersion:number;libraryId:string;principalId:string;selectionId:string;snapshots:Snapshot[];assets:Asset[];setlist:unknown};
export type Selection={key:string;manifest:DownloadManifest;includeOriginals:boolean;cacheName:string;shellCache:string;shellUrls:string[];shellHashes:Record<string,string>;setlistHash:string|null};
type Stage={cacheName:string;startedAt:number};
function stageRequest<T>(mode:IDBTransactionMode,action:(store:IDBObjectStore)=>IDBRequest<T>):Promise<T>{return openDb().then(db=>new Promise<T>((resolve,reject)=>{const tx=db.transaction('staging',mode),req=action(tx.objectStore('staging'));tx.oncomplete=()=>{db.close();resolve(req.result);};tx.onerror=()=>{db.close();reject(tx.error);};tx.onabort=()=>{db.close();reject(tx.error);};}));}
async function publish(selection:Selection):Promise<void>{const db=await openDb();await new Promise<void>((resolve,reject)=>{const tx=db.transaction(['selections','staging','meta'],'readwrite');tx.objectStore('selections').put(selection);tx.objectStore('meta').put({key:'activeShell',value:selection.shellCache,urls:selection.shellUrls,hashes:selection.shellHashes});tx.objectStore('meta').delete(`attempt:${selection.key}`);tx.objectStore('staging').delete(selection.cacheName);tx.objectStore('staging').delete(selection.shellCache);tx.oncomplete=()=>resolve();tx.onerror=()=>reject(tx.error);tx.onabort=()=>reject(tx.error);});db.close();}
export async function reconcileStaging():Promise<void>{const stages=await stageRequest<Stage[]>('readonly',store=>store.getAll());for(const stage of stages){if(Date.now()-stage.startedAt<3600000)continue;try{await caches.delete(stage.cacheName);await stageRequest<undefined>('readwrite',store=>store.delete(stage.cacheName));}catch{ /* retry on next startup */ }}}
async function digest(data:BufferSource):Promise<string>{return Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',data)),b=>b.toString(16).padStart(2,'0')).join('');}
export async function verifySnapshot(snapshot:Snapshot):Promise<boolean>{const bytes=new TextEncoder().encode(snapshot.source);return bytes.length===snapshot.size && snapshot.revision===snapshot.sha256 && await digest(bytes)===snapshot.sha256;}
function sharedCache(manifest:DownloadManifest){return `songbook-private-shared-${manifest.libraryId}-${manifest.principalId}`;}
function assetKey(asset:Asset){return `/__songbook_asset__/${asset.sha256}`;}
type StorageLease={key:string;owner:string;expires:number};
async function leaseUpdate(owner:string,operation:'acquire'|'renew'|'release'):Promise<boolean>{
  const db=await openDb();
  return new Promise<boolean>((resolve,reject)=>{let success=false;const tx=db.transaction('meta','readwrite'),store=tx.objectStore('meta'),request=store.get('storageLease');
    request.onsuccess=()=>{const current=request.result as StorageLease|undefined;const now=Date.now();
      if(operation==='acquire' && (!current || current.expires<now)){store.put({key:'storageLease',owner,expires:now+120000} satisfies StorageLease);success=true;}
      else if(operation==='renew' && current?.owner===owner){store.put({...current,expires:now+120000});success=true;}
      else if(operation==='release' && current?.owner===owner){store.delete('storageLease');success=true;}
    };
    tx.oncomplete=()=>{db.close();resolve(success);};tx.onerror=()=>{db.close();reject(tx.error);};tx.onabort=()=>{db.close();reject(tx.error);};
  });
}
async function locked<T>(action:()=>Promise<T>):Promise<T>{
  if(navigator.locks)return navigator.locks.request('songbook-private-storage',action);
  const owner=crypto.randomUUID(),deadline=Date.now()+30000;
  while(!await leaseUpdate(owner,'acquire')){if(Date.now()>deadline)throw new Error('Browser storage is busy');await new Promise(resolve=>setTimeout(resolve,100));}
  let lost=false;const timer=setInterval(()=>{void leaseUpdate(owner,'renew').then(ok=>{if(!ok)lost=true;}).catch(()=>{lost=true;});},10000);
  try{const result=await action();if(lost)throw new Error('Browser storage coordination expired');return result;}
  finally{clearInterval(timer);await leaseUpdate(owner,'release');}
}
function key(manifest:DownloadManifest){return `${manifest.libraryId}:${manifest.principalId}:${manifest.selectionId}`;}
async function collectUnused(scope:string,old:Selection):Promise<void>{
  const others=(await transaction<Selection[]>('readonly',store=>store.getAll())).filter(item=>item.key.startsWith(`${scope}:`));
  const used=new Set(others.flatMap(item=>item.manifest.assets.filter(asset=>!asset.optional || item.includeOriginals).map(asset=>asset.sha256)));
  const shared=await caches.open(sharedCache(old.manifest));
  for(const asset of old.manifest.assets)if(!used.has(asset.sha256))await shared.delete(assetKey(asset));
}
export async function registerStage(cacheName:string):Promise<void>{await stageRequest<IDBValidKey>('readwrite',store=>store.put({cacheName,startedAt:Date.now()} satisfies Stage));}
export async function discardStage(cacheName:string):Promise<void>{await caches.delete(cacheName);await stageRequest<undefined>('readwrite',store=>store.delete(cacheName));}
export async function downloadSelection(manifest:DownloadManifest,includeOriginals=false,shellCache=localStorage.getItem('songbook-active-shell') ?? ''):Promise<void>{
  if(manifest.schemaVersion!==1)throw new Error('Unsupported download schema');
  await metaRequest<IDBValidKey>('readwrite',store=>store.put({key:`attempt:${key(manifest)}`}));
  const previous=await transaction<Selection|undefined>('readonly',s=>s.get(key(manifest)));
  const cacheName=`songbook-private-${crypto.randomUUID()}`;
  await stageRequest<IDBValidKey>('readwrite',store=>store.put({cacheName,startedAt:Date.now()} satisfies Stage));
  const cache=await caches.open(cacheName);
  try {
    for(const snapshot of manifest.snapshots)if(!await verifySnapshot(snapshot))throw new Error('Snapshot hash mismatch');
    for(const snapshot of manifest.snapshots){const response=await fetch(`/api/preferences/${encodeURIComponent(snapshot.id)}`);if(!response.ok)throw new Error('Preferences unavailable');const prefs=await response.json() as {groups:Record<string,import('./preferences').ServerEnvelope<unknown>>};for(const group of ['play','performance','print'])await mergeLocalPreference(snapshot.id,group,fromServerEnvelope(prefs.groups[group]));}
    for(const asset of manifest.assets){if(asset.optional && !includeOriginals)continue;if(!asset.available)throw new Error('Requested original unavailable');const response=await fetch(asset.url);if(!response.ok)throw new Error('Download failed');const bytes=await response.arrayBuffer();if(bytes.byteLength!==asset.size || await digest(bytes)!==asset.sha256)throw new Error('Asset hash mismatch');await cache.put(asset.url,new Response(bytes,{headers:{'Content-Type':asset.mime}}));}
    if(!shellCache || !await caches.has(shellCache))throw new Error('Offline shell unavailable');
    const shellStore=await caches.open(shellCache);
    const shellUrls=(await shellStore.keys()).map(request=>request.url);
    const setlistHash=manifest.setlist ? await digest(new TextEncoder().encode(JSON.stringify(manifest.setlist))) : null;
    const shellHashes:Record<string,string>={};for(const url of shellUrls){const response=await shellStore.match(url,{ignoreVary:true});if(!response)throw new Error('Shell asset missing');shellHashes[url]=await digest(await response.arrayBuffer());}
    if(!shellUrls.includes(new URL('/fonts/NotoSerif-Regular.ttf',location.origin).href) || !shellUrls.includes(new URL('/fonts/NotoSansMono-Regular.ttf',location.origin).href))throw new Error('Offline fonts unavailable');
    await locked(async()=>{
      const shared=await caches.open(sharedCache(manifest));
      for(const asset of manifest.assets){if(asset.optional && !includeOriginals)continue;const data=await cache.match(asset.url);if(!data)throw new Error('Staged asset missing');await shared.put(assetKey(asset),data);await cache.delete(asset.url);}
      await publish({key:key(manifest),manifest,includeOriginals,cacheName,shellCache,shellUrls,shellHashes,setlistHash});
      try{localStorage.setItem('songbook-active-shell',shellCache);}catch{/* selection remains safely published */}
      if(previous){void caches.delete(previous.cacheName).catch(()=>{});if(navigator.locks)await collectUnused(`${manifest.libraryId}:${manifest.principalId}`,previous).catch(()=>{});}
    });
    try{localStorage.setItem('songbook-offline-scope',`${manifest.libraryId}:${manifest.principalId}`);}catch{/* report scope issue on next visit */}
    if(navigator.storage?.persist)void navigator.storage.persist().catch(()=>{});
  } catch(error){try{await discardStage(cacheName);if(shellCache && shellCache!==localStorage.getItem('songbook-active-shell'))await discardStage(shellCache);}catch{ /* retain intent for reconciliation */ }throw error;}
}
type ShellRecord={value:string;urls:string[];hashes:Record<string,string>};
async function verifyShellCache(name:string,urls:string[],hashes:Record<string,string>):Promise<boolean>{
  if(!name || !urls?.length || !await caches.has(name))return false;
  const shell=await caches.open(name);
  for(const url of urls){const response=await shell.match(url,{ignoreVary:true});if(!response || !hashes?.[url] || await digest(await response.arrayBuffer())!==hashes[url])return false;}
  return true;
}
function shellVerifier(){
  const results=new Map<string,Promise<boolean>>();
  const verify=(name:string,urls:string[],hashes:Record<string,string>)=>{
    const key=JSON.stringify([name,urls,hashes]);
    let result=results.get(key);
    if(!result){result=verifyShellCache(name,urls,hashes);results.set(key,result);}
    return result;
  };
  let activeVerified:Promise<boolean>|undefined;
  return async (selection:Selection):Promise<boolean>=>{
    if(selection.manifest.schemaVersion!==1 || !await caches.has(selection.cacheName))return false;
    activeVerified ??= metaRequest<ShellRecord|undefined>('readonly',store=>store.get('activeShell'))
      .then(active=>active ? verify(active.value,active.urls,active.hashes) : false);
    return await activeVerified && verify(selection.shellCache,selection.shellUrls,selection.shellHashes);
  };
}
function verifyShell(selection:Selection):Promise<boolean>{return shellVerifier()(selection);}
async function verifySetlist(selection:Selection):Promise<boolean>{
  if(!selection.manifest.setlist)return true;
  return !!selection.setlistHash && await digest(new TextEncoder().encode(JSON.stringify(selection.manifest.setlist)))===selection.setlistHash;
}
async function playableSnapshot(selection:Selection,snapshot:Snapshot,checkShell=verifyShell):Promise<boolean>{
  if(!await checkShell(selection) || !await verifySnapshot(snapshot))return false;
  const crops=(snapshot.source_refs ?? []).flatMap(ref=>ref.crop_asset_id?[ref.crop_asset_id]:[]);
  if(!crops.length)return true;
  const cache=await caches.open(sharedCache(selection.manifest));
  for(const id of crops){const asset=selection.manifest.assets.find(item=>item.id===id && !item.optional);if(!asset)return false;const response=await cache.match(assetKey(asset));if(!response)return false;const bytes=await response.arrayBuffer();if(bytes.byteLength!==asset.size || await digest(bytes)!==asset.sha256)return false;}
  return true;
}
export async function verifyAvailability(selectionId:string):Promise<'online-only'|'downloaded'|'incomplete'>{
  const scope=localStorage.getItem('songbook-current-scope') ?? localStorage.getItem('songbook-offline-scope');if(!scope)return 'online-only';
  const selection=await transaction<Selection|undefined>('readonly',s=>s.get(`${scope}:${selectionId}`));if(!selection){const attempt=await metaRequest<unknown>('readonly',store=>store.get(`attempt:${scope}:${selectionId}`));return attempt?'incomplete':'online-only';}
  if(!await verifyShell(selection))return 'incomplete';
  if(!await verifySetlist(selection))return 'incomplete';
  const cache=await caches.open(sharedCache(selection.manifest));
  for(const snapshot of selection.manifest.snapshots)if(!await verifySnapshot(snapshot))return 'incomplete';
  for(const asset of selection.manifest.assets){if(asset.optional && !selection.includeOriginals)continue;const response=await cache.match(assetKey(asset));if(!response)return 'incomplete';const bytes=await response.arrayBuffer();if(bytes.byteLength!==asset.size || await digest(bytes)!==asset.sha256)return 'incomplete';}
  return 'downloaded';
}
export async function getOfflineSnapshot(id:string,selectionId?:string):Promise<Snapshot|null>{
  const scope=localStorage.getItem('songbook-offline-scope');if(!scope)return null;
  const rows=await transaction<Selection[]>('readonly',s=>s.getAll());
  for(const row of rows){if(!row.key.startsWith(`${scope}:`) || (selectionId && row.manifest.selectionId!==selectionId))continue;const snapshot=row.manifest.snapshots.find(item=>item.id===id);if(snapshot && await playableSnapshot(row,snapshot))return snapshot;}
  return null;
}
async function removeUnlocked(scope:string,selectionId:string):Promise<void>{
  const id=`${scope}:${selectionId}`;const row=await transaction<Selection|undefined>('readonly',s=>s.get(id));
  if(!row){await metaRequest<undefined>('readwrite',store=>store.delete(`attempt:${id}`));return;}
  await caches.delete(row.cacheName);
  await transaction<undefined>('readwrite',s=>s.delete(id));
  if(!navigator.locks)return;
  await collectUnused(scope,row);
}
export async function removeDownload(selectionId:string):Promise<void>{
  const scope=localStorage.getItem('songbook-current-scope') ?? localStorage.getItem('songbook-offline-scope');if(!scope)return;
  await locked(()=>removeUnlocked(scope,selectionId));
}
async function clearScopedMetadata(scope:string):Promise<void>{
  const db=await openDb();await new Promise<void>((resolve,reject)=>{const tx=db.transaction('meta','readwrite'),store=tx.objectStore('meta'),cursor=store.openCursor();cursor.onsuccess=()=>{const row=cursor.result;if(!row)return;const key=String(row.key);if(['preference:','clock:','sync:','attempt:'].some(prefix=>key.startsWith(`${prefix}${scope}:`)))row.delete();row.continue();};tx.oncomplete=()=>resolve();tx.onerror=()=>reject(tx.error);tx.onabort=()=>reject(tx.error);});db.close();
}
export async function removeAllDownloads():Promise<void>{
  const scope=localStorage.getItem('songbook-offline-scope');if(!scope)return;
  await locked(async()=>{
    const rows=await transaction<Selection[]>('readonly',s=>s.getAll());
    const scoped=rows.filter(row=>row.key.startsWith(`${scope}:`));
    for(const row of scoped)await removeUnlocked(scope,row.manifest.selectionId);
    const separator=scope.lastIndexOf(':');if(separator>=0)await caches.delete(`songbook-private-shared-${scope.slice(0,separator)}-${scope.slice(separator+1)}`);
    await clearScopedMetadata(scope);
    localStorage.removeItem('songbook-offline-scope');localStorage.removeItem('songbook-current-scope');
  });
}
export async function getOfflineSetlist<T>(id:string):Promise<T|null>{
  const scope=localStorage.getItem('songbook-offline-scope');if(!scope)return null;
  const selectionId=`setlist:${id}`;
  const row=await transaction<Selection|undefined>('readonly',s=>s.get(`${scope}:${selectionId}`));
  if(!row || !await verifyShell(row) || !await verifySetlist(row))return null;
  return (row.manifest.setlist as T|null) ?? null;
}
export async function listOfflineSnapshots():Promise<Snapshot[]>{
  const scope=localStorage.getItem('songbook-offline-scope');if(!scope)return [];
  const rows=await transaction<Selection[]>('readonly',s=>s.getAll());
  const snapshots=new Map<string,Snapshot>();
  const checkShell=shellVerifier();
  for(const row of rows){if(!row.key.startsWith(`${scope}:`))continue;for(const item of row.manifest.snapshots)if(!snapshots.has(item.id) && await playableSnapshot(row,item,checkShell))snapshots.set(item.id,item);}
  return [...snapshots.values()];
}
export async function listOfflineSetlists<T>():Promise<T[]>{
  const scope=localStorage.getItem('songbook-offline-scope');if(!scope)return [];
  const rows=await transaction<Selection[]>('readonly',s=>s.getAll());const result:T[]=[];
  for(const row of rows){if(row.key.startsWith(`${scope}:`) && row.manifest.setlist && await verifyShell(row) && await verifySetlist(row))result.push(row.manifest.setlist as T);}
  return result;
}
export async function selectAuthenticatedScope(libraryId:string,principalId:string):Promise<void>{
  const scope=`${libraryId}:${principalId}`;
  localStorage.setItem('songbook-current-scope',scope);
  const rows=await transaction<Selection[]>('readonly',store=>store.getAll());
  if(rows.some(row=>row.key.startsWith(`${scope}:`)))localStorage.setItem('songbook-offline-scope',scope);
  else localStorage.removeItem('songbook-offline-scope');
}

export async function getOfflineOriginals(id:string):Promise<Blob[]>{
  const scope=localStorage.getItem('songbook-offline-scope');if(!scope)return [];
  const rows=await transaction<Selection[]>('readonly',store=>store.getAll());
  const result:Blob[]=[];const seen=new Set<string>();
  for(const row of rows){if(!row.key.startsWith(`${scope}:`) || !row.includeOriginals || await verifyAvailability(row.manifest.selectionId)!=='downloaded')continue;
    const snapshot=row.manifest.snapshots.find(item=>item.id===id);if(!snapshot)continue;
    const ids=new Set((snapshot.source_refs ?? []).map(ref=>ref.source_id));const cache=await caches.open(sharedCache(row.manifest));
    for(const asset of row.manifest.assets){if(!asset.optional || !ids.has(asset.id) || seen.has(asset.sha256))continue;const response=await cache.match(assetKey(asset));if(response){result.push(await response.blob());seen.add(asset.sha256);}}
  }return result;
}

export async function getScopedSelections():Promise<Selection[]>{const scope=localStorage.getItem('songbook-current-scope') ?? localStorage.getItem('songbook-offline-scope');if(!scope)return [];return (await transaction<Selection[]>('readonly',store=>store.getAll())).filter(row=>row.key.startsWith(`${scope}:`));}
