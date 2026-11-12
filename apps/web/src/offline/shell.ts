import {registerStage,discardStage} from './downloads';
export async function prepareShell():Promise<string>{
  if(!('serviceWorker' in navigator))throw new Error('Offline downloads require a service worker');
  await navigator.serviceWorker.register('/sw.js');
  await navigator.serviceWorker.ready;
  const name=`songbook-shell-data-${crypto.randomUUID()}`;
  await registerStage(name);
  const cache=await caches.open(name);
  try{
  const urls=new Set(['/','/manifest.webmanifest','/icon.svg','/fonts/NotoSerif-Regular.ttf','/fonts/NotoSansMono-Regular.ttf']);
  for(const entry of performance.getEntriesByType('resource')){const url=new URL(entry.name);if(url.origin===location.origin && !url.pathname.startsWith('/api/') && !url.pathname.startsWith('/health'))urls.add(url.pathname+url.search);}
  await Promise.all([...urls].map(async url=>{const response=await fetch(url);if(!response.ok)throw new Error('Offline application assets unavailable');await cache.put(url,response);}));
  return name;
  }catch(error){await discardStage(name);throw error;}
}
