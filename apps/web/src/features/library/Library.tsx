import {ActionPopover} from '../ActionPopover';
import React, {useEffect, useMemo, useState} from 'react';
import {ExportButtons} from '../exports/ExportButtons';
import {downloadSelection,verifyAvailability,removeDownload,listOfflineSnapshots,getOfflineSnapshot} from '../../offline/downloads';
import type {DownloadManifest} from '../../offline/downloads';
import {prepareShell} from '../../offline/shell';
import {checkDownloads,arrangementSyncStatus,refreshDownloads} from '../../offline/sync';
import {parseSource} from '../../../../../packages/music/src/parser';

type Entry = {cachedOnly?:boolean;source_only:boolean; id:string; song_id:string; revision:string; metadata_revision:number; title:string; artist:string; favorite:boolean; tags:string[]; notes:string};
export function Library({csrf}: {csrf:string}) {
  const [query,setQuery] = useState('');
  const [artistFilter,setArtistFilter] = useState('');
  const [sort,setSort] = useState('title-asc');
  const [favorites,setFavorites] = useState(false);
  const [recent,setRecent] = useState(false);
  const [onlineEntries,setEntries] = useState<Entry[]>([]);
  const [cachedEntries,setCachedEntries] = useState<Entry[]>([]);
  const [cacheCycle,setCacheCycle] = useState(0);
  const hiddenKey='songbook-hidden-library:'+ (localStorage.getItem('songbook-offline-scope') ?? 'online');
  const [hidden,setHidden]=useState<string[]>(()=>{try{const value=JSON.parse(localStorage.getItem(hiddenKey) ?? '[]');return Array.isArray(value)?value.filter((id:unknown)=>typeof id==='string'):[];}catch{return [];}});
  const [error,setError] = useState('');
  const [tag,setTag] = useState('');
  const [tagFilter,setTagFilter] = useState('');
  const [downloads,setDownloads]=useState<Record<string,string>>({});
  const [downloadErrors,setDownloadErrors]=useState<Record<string,string>>({});
  const [direct,setDirect]=useState<Record<string,boolean>>({});
  const [syncStates,setSyncStates]=useState<Record<string,string>>({});
  const [syncUnavailable,setSyncUnavailable]=useState<Record<string,boolean>>({});
  const [syncCycle,setSyncCycle]=useState(0);
  useEffect(() => {
    const update = () => {
      setSyncCycle(value => value+1);
      setCacheCycle(value => value+1);
    };
    window.addEventListener('songbook-sync-complete',update);
    return () => window.removeEventListener('songbook-sync-complete',update);
  }, []);
  useEffect(() => {
    if (!csrf) return;
    let active=true;
    const update=()=>{if(active)setSyncCycle(value=>value+1);};
    void checkDownloads(csrf).then(update,update);
    return ()=>{active=false;};
  }, [csrf]);
  const [originals,setOriginals]=useState<Record<string,boolean>>({});
  async function download(id:string){const previous=downloads[id] ?? 'Online only';try {setDownloadErrors(old=>({...old,[id]:''}));setDownloads(old=>({...old,[id]:'Downloading'}));
    if(direct[id] && syncStates[id]==='outdated'){const report=await refreshDownloads([`arrangement:${id}`]);if(report.failed.length)throw new Error();}
    else{const response=await fetch(`/api/downloads/arrangements/${id}`);if(!response.ok)throw new Error();const manifest=await response.json() as DownloadManifest;const shell=await prepareShell();await downloadSelection(manifest,!!originals[id],shell);}
    setDownloads(old=>({...old,[id]:awaitStatus}));setDirect(old=>({...old,[id]:true}));setSyncStates(old=>({...old,[id]:'current'}));setSyncUnavailable(old=>({...old,[id]:false}));setCacheCycle(value=>value+1);
  }catch{setDownloads(old=>({...old,[id]:previous}));setDownloadErrors(old=>({...old,[id]:'Download failed'}));}}
  const awaitStatus='Downloaded';

  useEffect(() => {
    let active=true;
    void listOfflineSnapshots().then(items=>{
      if (!active) return;
      setCachedEntries(items.map(item=>{
        const metadata=parseSource(item.source).metadata;
        return {cachedOnly:true,source_only:false,id:item.id,song_id:item.song_id,revision:item.revision,metadata_revision:0,title:metadata.title?.[0] ?? 'Untitled',artist:metadata.artist?.[0] ?? '',favorite:false,tags:[],notes:''};
      }));
    }).catch(()=>{if(active)setCachedEntries([]);});
    return ()=>{active=false;};
  }, [csrf,cacheCycle]);

  useEffect(() => {
    if (!csrf) return;
    const params = new URLSearchParams({q:query, favorite:String(favorites), recent:String(recent)});
    if (tag.trim()) params.append('tag',tag.trim());
    if (tagFilter) params.append('tag',tagFilter);
    const controller = new AbortController();
    void fetch(`/api/library?${params}`, {signal:controller.signal}).then(async response => {
      if (!response.ok) throw new Error();
      const online=await response.json() as Entry[];
      if (controller.signal.aborted) return;
      setEntries(online);
      setError('');
    }).catch(e => {if (e.name !== 'AbortError' && !controller.signal.aborted) setError('Could not load library.');});
    return () => controller.abort();
  }, [query,favorites,tag,tagFilter,recent,csrf]);

  const cachedIds=useMemo(()=>new Set(cachedEntries.map(entry=>entry.id)),[cachedEntries]);
  const entries=useMemo(()=>{
    const online=csrf ? onlineEntries : [];
    if (tag || tagFilter || (csrf && (favorites || recent))) return online;
    const known=new Set(online.map(entry=>entry.id));
    const search=query.toLowerCase();
    const extras=cachedEntries.filter(entry=>
      !known.has(entry.id) && !hidden.includes(entry.id) && entry.title.toLowerCase().includes(search)
    );
    return [...online,...extras];
  },[cachedEntries,csrf,favorites,hidden,onlineEntries,query,recent,tag,tagFilter]);

  useEffect(()=>{
    if (csrf && syncCycle===0) return;
    let active=true;
    void Promise.all(entries.filter(entry=>!entry.source_only).map(async entry=>{
      const own=await verifyAvailability(`arrangement:${entry.id}`);
      const available=own==='downloaded' || cachedIds.has(entry.id);
      const sync=available?await arrangementSyncStatus(entry.id):null;
      return [entry.id,available?'Downloaded':own==='incomplete'?'Incomplete':'Online only',own!=='online-only',sync?.state ?? '',!!sync && !sync.available] as const;
    })).then(results=>{
      if (!active) return;
      setDownloads(Object.fromEntries(results.map(([id,status])=>[id,status])));
      setDirect(Object.fromEntries(results.map(([id,,own])=>[id,own])));
      setSyncStates(Object.fromEntries(results.map(([id,,,state])=>[id,state])));
      setSyncUnavailable(Object.fromEntries(results.map(([id,,,,unavailable])=>[id,unavailable])));
    }).catch(()=>{});
    return ()=>{active=false;};
  },[cachedIds,csrf,entries,syncCycle]);

  async function removeOffline(id:string){try{await removeDownload(`arrangement:${id}`);setDirect(old=>({...old,[id]:false}));const available=!!await getOfflineSnapshot(id);setDownloads(old=>({...old,[id]:available?'Downloaded':'Online only'}));setCacheCycle(value=>value+1);}catch{setError('Could not remove download.');}}
  async function deleteEntry(entry:Entry){
    if(!window.confirm(`Delete ${entry.title} from the library? Originals and revision/import history are retained. Downloaded copies on other devices may remain.`))return;
    try {
      const response=await fetch(entry.source_only ? `/api/sources/${encodeURIComponent(entry.id)}/library` : `/api/arrangements/${encodeURIComponent(entry.id)}`,{method:'DELETE',headers:{'Content-Type':'application/json','X-CSRF-Token':csrf},body:JSON.stringify({revision:entry.metadata_revision})});
      if(!response.ok){setError(response.status===409?'This entry changed. Refresh the library before deleting.':'Could not delete this library entry.');return;}
      setEntries(old=>old.filter(item=>item.id!==entry.id));
      if(!entry.source_only){const next=[...new Set([...hidden,entry.id])];setHidden(next);try{localStorage.setItem(hiddenKey,JSON.stringify(next));}catch{setError('Deleted from the server library. This browser could not remember hiding its cached copy.');}}
    }catch{setError('Could not confirm deletion. Refresh the library before trying again.');}
  }
  async function favorite(entry:Entry) {
    const response = await fetch(`/api/arrangements/${entry.id}/metadata`, {method:'PATCH',headers:{'Content-Type':'application/json','X-CSRF-Token':csrf},body:JSON.stringify({revision:entry.metadata_revision,favorite:!entry.favorite,tags:entry.tags,notes:entry.notes})});
    if (!response.ok) {setError('Metadata changed. Refresh the library.'); return;}
    const metadata = await response.json() as {revision:number;favorite:boolean};
    setEntries(items => items.map(item => item.id === entry.id ? {...item,favorite:metadata.favorite,metadata_revision:metadata.revision}:item));
  }
  const compare=(a:string,b:string)=>a.replace(/[()]/g,'').localeCompare(b.replace(/[()]/g,''),undefined,{sensitivity:'base'});
  const visibleEntries=entries.filter(entry=>!artistFilter || entry.artist.toLocaleLowerCase()===artistFilter.toLocaleLowerCase());
  if(sort!=='recent') {const [field,direction]=sort.split('-') as ['title'|'artist',string];visibleEntries.sort((a,b)=>(direction==='desc'?-1:1)*compare(a[field],b[field]) || compare(a.title,b.title) || a.id.localeCompare(b.id));}
  function sortBy(field:'title'|'artist'){setSort(current=>current===`${field}-asc`?`${field}-desc`:`${field}-asc`);}
  return <section className="library"><div className="library-heading"><h2>Library</h2><div className="library-actions"><a href="/imports">Import music</a> {csrf && <ExportButtons csrf={csrf} />}</div></div><div className="library-filters"><div><label htmlFor="search">Search</label><div className="library-search-field">{artistFilter && <span className="library-artist-chip"><span>Artist: {artistFilter}</span><button type="button" onClick={()=>setArtistFilter('')} aria-label="Clear artist filter">×</button></span>}<input id="search" type="search" placeholder="Find music…" value={query} onChange={event => setQuery(event.target.value)} /></div></div><div><label htmlFor="tag">Tag</label><div className="library-search-field library-tag-field">{tagFilter && <span className="library-artist-chip"><span>{tagFilter}</span><button type="button" onClick={()=>setTagFilter('')} aria-label="Clear tag filter">×</button></span>}<input id="tag" value={tag} onChange={event => setTag(event.target.value)} /></div></div><label><input type="checkbox" checked={favorites} onChange={event => setFavorites(event.target.checked)} />Favorites only</label><label><input type="checkbox" checked={recent} onChange={event => {setRecent(event.target.checked);setSort(event.target.checked?'recent':'title-asc');}} />Recently played</label><div className="library-mobile-sort"><label htmlFor="library-sort">Sort library</label><select id="library-sort" value={sort} onChange={event=>setSort(event.target.value)}><option value="title-asc">Song A–Z</option><option value="title-desc">Song Z–A</option><option value="artist-asc">Artist A–Z</option><option value="artist-desc">Artist Z–A</option>{recent && <option value="recent">Recently played</option>}</select></div></div>{(error || !csrf) && <p role="alert">{error || 'Offline: showing verified downloaded songs.'}</p>}<div className="library-table-scroll" role="region" aria-label="Song library table" tabIndex={0}><table className="library-table" aria-label="Song library"><thead><tr><th scope="col" className="favorite-column">Favorite</th><th scope="col" aria-label="Song" aria-sort={sort.startsWith('title-')?(sort.endsWith('asc')?'ascending':'descending'):undefined}><button className="library-sort-button" aria-label="Sort by Song" onClick={()=>sortBy('title')}>Song {sort.startsWith('title-') && <span aria-hidden="true">{sort.endsWith('asc')?'▲':'▼'}</span>}</button></th><th scope="col" aria-label="Artist" aria-sort={sort.startsWith('artist-')?(sort.endsWith('asc')?'ascending':'descending'):undefined}><button className="library-sort-button" aria-label="Sort by Artist" onClick={()=>sortBy('artist')}>Artist {sort.startsWith('artist-') && <span aria-hidden="true">{sort.endsWith('asc')?'▲':'▼'}</span>}</button></th><th scope="col">Tags</th><th scope="col" className="actions-column">Actions</th></tr></thead><tbody>{visibleEntries.map(entry => <tr key={entry.id}><td className="favorite-column">{!entry.source_only && !entry.cachedOnly && !!csrf ? <button onClick={() => void favorite(entry)} aria-pressed={entry.favorite} aria-label={`${entry.favorite ? 'Remove favorite' : 'Favorite'} ${entry.title}`}>{entry.favorite ? '★' : '☆'}</button> : <span aria-label="Favorite unavailable">—</span>}</td><th scope="row"><a href={entry.source_only ? `/api/sources/${encodeURIComponent(entry.id)}/original` : `/player?id=${encodeURIComponent(entry.id)}${entry.cachedOnly ? '&cached=1' : ''}`}>{entry.title}</a>{entry.source_only && <span className="source-only-label">Original PDF</span>}</th><td>{entry.artist ? <button className="library-artist-button" aria-label={`Filter by ${entry.artist}`} onClick={()=>setArtistFilter(entry.artist)}>{entry.artist}</button> : '—'}</td><td>{entry.tags.length ? entry.tags.map((item,index)=><React.Fragment key={item}>{index>0 && ', '}<button className="library-artist-button" aria-label={`Filter by tag ${item}`} onClick={()=>setTagFilter(item)}>{item}</button></React.Fragment>) : '—'}</td><td><div className="library-row-actions">{!entry.source_only && !entry.cachedOnly && !!csrf && <ExportButtons csrf={csrf} id={entry.id} />}{(!entry.source_only || (!!csrf && !entry.cachedOnly)) && <ActionPopover label="More" className="offline-actions">{!entry.source_only && <><strong>Offline copy</strong>{downloads[entry.id] && <span>{downloads[entry.id]}</span>}{downloadErrors[entry.id] && <span role="alert">{downloadErrors[entry.id]}</span>}{syncStates[entry.id] && syncStates[entry.id]!=='current' && <span>{syncStates[entry.id]==='outdated'?'Outdated':syncStates[entry.id]==='deleted'?'Deleted':'Unavailable'}</span>}{syncUnavailable[entry.id] && <span>Sync unavailable</span>}{!!csrf && <><label><input type="checkbox" checked={!!originals[entry.id]} onChange={event=>setOriginals(old=>({...old,[entry.id]:event.target.checked}))}/>Include original PDF</label><button onClick={()=>void download(entry.id)}>{syncStates[entry.id]==='outdated' && direct[entry.id] ? 'Refresh download' : 'Download for offline'}</button>{direct[entry.id] && <button onClick={()=>void removeOffline(entry.id)}>Remove download</button>}</>}{downloads[entry.id]==='Downloaded' && <a href={`/player?id=${encodeURIComponent(entry.id)}&cached=1`}>Play cached copy</a>}{!navigator.locks && <small>Shared download files may remain until you remove private downloads when signing out.</small>}</>}{!!csrf && !entry.cachedOnly && <button className="library-delete" onClick={()=>void deleteEntry(entry)}>Delete from library</button>}</ActionPopover>}</div></td></tr>)}</tbody></table>{!visibleEntries.length && <p className="library-empty">No matching songs.</p>}</div></section>;
}
