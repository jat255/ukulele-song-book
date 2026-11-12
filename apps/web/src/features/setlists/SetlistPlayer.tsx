import React, {useEffect,useState} from 'react';
import {getOfflineSetlist,verifyAvailability,getOfflineSnapshot} from '../../offline/downloads';
import {Player} from '../player/Player';
import type {Setlist} from './Setlists';
import {setlistSyncStatus} from '../../offline/sync';

export function SetlistPlayer({id,csrf}:{id:string;csrf:string}) {
  const [set,setSet]=useState<Setlist|null>(null);
  const cachedOnly=new URLSearchParams(location.search).get('cached')==='1';
  const [index,setIndex]=useState(0);
  const [error,setError]=useState('');
  const [partial,setPartial]=useState(false);const [serverPartial,setServerPartial]=useState(false);const [cached,setCached]=useState<Record<string,boolean>>({});
  useEffect(()=>{let active=true;const update=()=>{void setlistSyncStatus(id).then(status=>{if(active)setServerPartial(status.partial);});};update();window.addEventListener('songbook-sync-complete',update);return()=>{active=false;window.removeEventListener('songbook-sync-complete',update);};},[id]);
  useEffect(()=>{if(!set)return;let active=true;void Promise.all(set.items.map(async item=>[item.id,!!await getOfflineSnapshot(item.arrangementId,`setlist:${id}`)] as const)).then(results=>{if(active)setCached(Object.fromEntries(results));});return()=>{active=false;};},[set,id]);
  useEffect(()=>{if(!csrf)void verifyAvailability(`setlist:${id}`).then(status=>setPartial(status==='incomplete'));},[id,csrf]);
  useEffect(()=>{if(cachedOnly){void getOfflineSetlist<Setlist>(id).then(saved=>{if(saved)setSet(saved);else setError('Cached setlist unavailable.');});return;}void fetch(`/api/setlists/${id}`).then(async response=>{if(!response.ok)throw new Error();setSet(await response.json() as Setlist);}).catch(()=>{void getOfflineSetlist<Setlist>(id).then(saved=>{if(saved)setSet(saved);else setError('Setlist unavailable offline.');});});},[id,cachedOnly]);
  if(!set)return <main>{error || 'Loading setlist…'}</main>;
  const item=set.items[index];
  if(!item)return <main><a href={`/setlists?id=${encodeURIComponent(id)}`}>Edit setlist</a><p>This setlist has no songs.</p></main>;
  const change=(next:number)=>{setIndex(next);window.scrollTo(0,0);};
  return <div><header className="setlist-navigation"><a href={`/setlists?id=${encodeURIComponent(id)}`}>Setlist</a> <span>Song {index+1} of {set.items.length}</span> {partial && <span>Partial download: some content is unavailable.</span>}{serverPartial && <span>Partial: some server songs are unavailable.</span>} <button disabled={index===0} onClick={()=>change(index-1)}>Previous song</button> <button disabled={index===set.items.length-1} onClick={()=>change(index+1)}>Next song</button></header>{item.available || cached[item.id] ? <Player key={item.id} id={item.arrangementId} csrf={csrf} forceCached={cachedOnly || !item.available} selectionId={`setlist:${id}`}/> : <main><p>{item.title} is unavailable.</p><a href={`/setlists?id=${encodeURIComponent(id)}`}>Review setlist</a></main>}</div>;
}
