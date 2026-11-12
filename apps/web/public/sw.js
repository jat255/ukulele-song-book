self.addEventListener('install',event=>event.waitUntil(self.skipWaiting()));
self.addEventListener('activate',event=>event.waitUntil(self.clients.claim()));
async function shell(){
  const name=await new Promise(resolve=>{const open=indexedDB.open('songbook-downloads-v1');open.onerror=()=>resolve(null);open.onupgradeneeded=()=>open.transaction.abort();open.onsuccess=()=>{const db=open.result;if(!db.objectStoreNames.contains('meta')){db.close();resolve(null);return;}const tx=db.transaction('meta','readonly'),request=tx.objectStore('meta').get('activeShell');request.onsuccess=()=>resolve(request.result?.value ?? null);request.onerror=()=>resolve(null);tx.oncomplete=()=>db.close();};});
  if(!name || !await caches.has(name))return null;
  return caches.open(name);
}
self.addEventListener('fetch',event=>{
  const url=new URL(event.request.url);
  if(event.request.method!=='GET' || url.origin!==self.location.origin || url.pathname.startsWith('/api/') || url.pathname.startsWith('/health'))return;
  event.respondWith(fetch(event.request).catch(async()=>{const cache=await shell();if(!cache)return Response.error();return await cache.match(event.request.mode==='navigate'?'/':event.request,{ignoreVary:true}) || Response.error();}));
});
