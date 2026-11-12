import {ActionPopover} from '../ActionPopover';
import React, {useEffect, useState} from 'react';
import {ExportButtons} from '../exports/ExportButtons';
import {downloadSelection,verifyAvailability,removeDownload,listOfflineSnapshots,getOfflineSnapshot} from '../../offline/downloads';
import type {DownloadManifest} from '../../offline/downloads';
import {prepareShell} from '../../offline/shell';
import {checkDownloads,arrangementSyncStatus,refreshDownloads} from '../../offline/sync';
import {parseSource} from '../../../../../packages/music/src/parser';

type Entry = {cachedOnly?:boolean;source_only:boolean; id:string; song_id:string; revision:string; metadata_revision:number; title:string; artist:string; favorite:boolean; tags:string[]; notes:string};

export function Library({csrf}: {csrf:string}) {
  const [query,setQuery] = useState('');
  const [favorites,setFavorites] = useState(false);
  const [recent,setRecent] = useState(false);
  const [entries,setEntries] = useState<Entry[]>([]);
  const [error,setError] = useState('');
  const [tag,setTag] = useState('');
  const [downloads,setDownloads]=useState<Record<string,string>>({});
  const [downloadErrors,setDownloadErrors]=useState<Record<string,string>>({});
  const [direct,setDirect]=useState<Record<string,boolean>>({});
  const [syncStates,setSyncStates]=useState<Record<string,string>>({});
  const [syncUnavailable,setSyncUnavailable]=useState<Record<string,boolean>>({});
  const [syncCycle,setSyncCycle]=useState(0);
  useEffect(()=>{const update=()=>setSyncCycle(value=>value+1);window.addEventListener('online',update);return()=>window.removeEventListener('online',update);},[]);
  const [originals,setOriginals]=useState<Record<string,boolean>>({});
  async function download(id:string){const previous=downloads[id] ?? 'Online only';try {setDownloadErrors(old=>({...old,[id]:''}));setDownloads(old=>({...old,[id]:'Downloading'}));
    if(direct[id] && syncStates[id]==='outdated'){const report=await refreshDownloads([`arrangement:${id}`]);if(report.failed.length)throw new Error();}
    else{const response=await fetch(`/api/downloads/arrangements/${id}`);if(!response.ok)throw new Error();const manifest=await response.json() as DownloadManifest;const shell=await prepareShell();await downloadSelection(manifest,!!originals[id],shell);}
    setDownloads(old=>({...old,[id]:awaitStatus}));setDirect(old=>({...old,[id]:true}));setSyncStates(old=>({...old,[id]:'current'}));setSyncUnavailable(old=>({...old,[id]:false}));
  }catch{setDownloads(old=>({...old,[id]:previous}));setDownloadErrors(old=>({...old,[id]:'Download failed'}));}}
  const awaitStatus='Downloaded';
  useEffect(() => {
    if(!csrf){let active=true;void listOfflineSnapshots().then(items=>{if(!active)return;setEntries(items.map(item=>{const metadata=parseSource(item.source).metadata;return {cachedOnly:true,source_only:false,id:item.id,song_id:item.song_id,revision:item.revision,metadata_revision:0,title:metadata.title?.[0] ?? 'Untitled',artist:metadata.artist?.[0] ?? '',favorite:false,tags:[],notes:''};}).filter(item=>!query || item.title.toLowerCase().includes(query.toLowerCase())));setError('Offline: showing verified downloaded songs.');});return()=>{active=false;};}
    const params = new URLSearchParams({q:query, favorite:String(favorites), recent:String(recent)});
    if (tag.trim()) params.append('tag',tag.trim());
    const controller = new AbortController();
    void fetch(`/api/library?${params}`, {signal:controller.signal}).then(async response => {
      if (!response.ok) throw new Error();
      const online=await response.json() as Entry[];const cached=await listOfflineSnapshots();const known=new Set(online.map(item=>item.id));const extras=cached.filter(item=>!known.has(item.id)).map(item=>{const metadata=parseSource(item.source).metadata;return {cachedOnly:true,source_only:false,id:item.id,song_id:item.song_id,revision:item.revision,metadata_revision:0,title:metadata.title?.[0] ?? 'Untitled',artist:metadata.artist?.[0] ?? '',favorite:false,tags:[],notes:''};}).filter(item=>!favorites && !recent && !tag && (!query || item.title.toLowerCase().includes(query.toLowerCase())));setEntries([...online,...extras]); setError('');
    }).catch(e => {if (e.name !== 'AbortError') setError('Could not load library.');});
    return () => controller.abort();
  }, [query,favorites,tag,recent,csrf]);
  useEffect(()=>{let active=true;void (async()=>{if(csrf)await checkDownloads(csrf);const results=await Promise.all(entries.filter(entry=>!entry.source_only).map(async entry=>{const own=await verifyAvailability(`arrangement:${entry.id}`);const available=own==='downloaded' || !!await getOfflineSnapshot(entry.id);const sync=available?await arrangementSyncStatus(entry.id):null;return [entry.id,available?'Downloaded':own==='incomplete'?'Incomplete':'Online only',own!=='online-only',sync?.state ?? '',!!sync && !sync.available] as const;}));if(active){setDownloads(Object.fromEntries(results.map(([id,status])=>[id,status])));setDirect(Object.fromEntries(results.map(([id,,own])=>[id,own])));setSyncStates(Object.fromEntries(results.map(([id,,,state])=>[id,state])));setSyncUnavailable(Object.fromEntries(results.map(([id,,,,unavailable])=>[id,unavailable])));}})().catch(()=>{});return()=>{active=false;};},[entries,csrf,syncCycle]);
  async function removeOffline(id:string){try{await removeDownload(`arrangement:${id}`);setDirect(old=>({...old,[id]:false}));const available=!!await getOfflineSnapshot(id);setDownloads(old=>({...old,[id]:available?'Downloaded':'Online only'}));}catch{setError('Could not remove download.');}}
  async function favorite(entry:Entry) {
    const response = await fetch(`/api/arrangements/${entry.id}/metadata`, {method:'PATCH',headers:{'Content-Type':'application/json','X-CSRF-Token':csrf},body:JSON.stringify({revision:entry.metadata_revision,favorite:!entry.favorite,tags:entry.tags,notes:entry.notes})});
    if (!response.ok) {setError('Metadata changed. Refresh the library.'); return;}
    const metadata = await response.json() as {revision:number;favorite:boolean};
    setEntries(items => items.map(item => item.id === entry.id ? {...item,favorite:metadata.favorite,metadata_revision:metadata.revision}:item));
  }
  return <section className="library"><h2>Library</h2><div className="library-filters"><div><label htmlFor="search">Search</label><input id="search" type="search" placeholder="Find music…" value={query} onChange={event => setQuery(event.target.value)} /></div><div><label htmlFor="tag">Tag</label><input id="tag" value={tag} onChange={event => setTag(event.target.value)} /></div><label><input type="checkbox" checked={favorites} onChange={event => setFavorites(event.target.checked)} />Favorites only</label><label><input type="checkbox" checked={recent} onChange={event => setRecent(event.target.checked)} />Recently played</label></div><div className="library-actions"><a href="/imports">Import music</a> {csrf && <ExportButtons csrf={csrf} />}</div>{error && <p role="alert">{error}</p>}<div className="library-table-scroll" role="region" aria-label="Song library table" tabIndex={0}><table className="library-table" aria-label="Song library"><thead><tr><th scope="col" className="favorite-column">Favorite</th><th scope="col">Song</th><th scope="col">Artist</th><th scope="col">Tags</th><th scope="col">Actions</th></tr></thead><tbody>{entries.map(entry => <tr key={entry.id}><td className="favorite-column">{!entry.source_only && !entry.cachedOnly && !!csrf ? <button onClick={() => void favorite(entry)} aria-pressed={entry.favorite} aria-label={`${entry.favorite ? 'Remove favorite' : 'Favorite'} ${entry.title}`}>{entry.favorite ? '★' : '☆'}</button> : <span aria-label="Favorite unavailable">—</span>}</td><th scope="row"><a href={entry.source_only ? `/api/sources/${encodeURIComponent(entry.id)}/original` : `/player?id=${encodeURIComponent(entry.id)}${entry.cachedOnly ? '&cached=1' : ''}`}>{entry.title}</a>{entry.source_only && <span className="source-only-label">Original PDF</span>}</th><td>{entry.artist || '—'}</td><td>{entry.tags.length ? entry.tags.join(', ') : '—'}</td><td><div className="library-row-actions">{!entry.source_only && !entry.cachedOnly && !!csrf && <ExportButtons csrf={csrf} id={entry.id} />}{!entry.source_only && <ActionPopover label="More" className="offline-actions"><strong>Offline copy</strong>{downloads[entry.id] && <span>{downloads[entry.id]}</span>}{downloadErrors[entry.id] && <span role="alert">{downloadErrors[entry.id]}</span>}{syncStates[entry.id] && syncStates[entry.id]!=='current' && <span>{syncStates[entry.id]==='outdated'?'Outdated':syncStates[entry.id]==='deleted'?'Deleted':'Unavailable'}</span>}{syncUnavailable[entry.id] && <span>Sync unavailable</span>}{!!csrf && <><label><input type="checkbox" checked={!!originals[entry.id]} onChange={event=>setOriginals(old=>({...old,[entry.id]:event.target.checked}))}/>Include original PDF</label><button onClick={()=>void download(entry.id)}>{syncStates[entry.id]==='outdated' && direct[entry.id] ? 'Refresh download' : 'Download for offline'}</button>{direct[entry.id] && <button onClick={()=>void removeOffline(entry.id)}>Remove download</button>}</>}{downloads[entry.id]==='Downloaded' && <a href={`/player?id=${encodeURIComponent(entry.id)}&cached=1`}>Play cached copy</a>}{!navigator.locks && <small>Shared download files may remain until you remove private downloads when signing out.</small>}</ActionPopover>}</div></td></tr>)}</tbody></table>{!entries.length && <p className="library-empty">No matching songs.</p>}</div></section>;
}
