import React, {useEffect, useState} from 'react';

type Entry = {source_only:boolean; id:string; song_id:string; revision:string; metadata_revision:number; title:string; artist:string; favorite:boolean; tags:string[]; notes:string};

export function Library({csrf}: {csrf:string}) {
  const [query,setQuery] = useState('');
  const [favorites,setFavorites] = useState(false);
  const [recent,setRecent] = useState(false);
  const [entries,setEntries] = useState<Entry[]>([]);
  const [error,setError] = useState('');
  const [tag,setTag] = useState('');
  useEffect(() => {
    const params = new URLSearchParams({q:query, favorite:String(favorites), recent:String(recent)});
    if (tag.trim()) params.append('tag',tag.trim());
    const controller = new AbortController();
    void fetch(`/api/library?${params}`, {signal:controller.signal}).then(async response => {
      if (!response.ok) throw new Error();
      setEntries(await response.json() as Entry[]); setError('');
    }).catch(e => {if (e.name !== 'AbortError') setError('Could not load library.');});
    return () => controller.abort();
  }, [query,favorites,tag,recent]);
  async function favorite(entry:Entry) {
    const response = await fetch(`/api/arrangements/${entry.id}/metadata`, {method:'PATCH',headers:{'Content-Type':'application/json','X-CSRF-Token':csrf},body:JSON.stringify({revision:entry.metadata_revision,favorite:!entry.favorite,tags:entry.tags,notes:entry.notes})});
    if (!response.ok) {setError('Metadata changed. Refresh the library.'); return;}
    const metadata = await response.json() as {revision:number;favorite:boolean};
    setEntries(items => items.map(item => item.id === entry.id ? {...item,favorite:metadata.favorite,metadata_revision:metadata.revision}:item));
  }
  return <section><h2>Library</h2><label htmlFor="search">Search</label><input id="search" value={query} onChange={event => setQuery(event.target.value)} /><label htmlFor="tag">Tag</label><input id="tag" value={tag} onChange={event => setTag(event.target.value)} /><label><input type="checkbox" checked={favorites} onChange={event => setFavorites(event.target.checked)} />Favorites only</label><label><input type="checkbox" checked={recent} onChange={event => setRecent(event.target.checked)} />Recently played</label><p><a href="/imports">Import music</a></p>{error && <p role="alert">{error}</p>}<ul>{entries.map(entry => <li key={entry.id}><a href={entry.source_only ? `/api/sources/${encodeURIComponent(entry.id)}/original` : `/player?id=${encodeURIComponent(entry.id)}`}>{entry.title}</a>{entry.source_only && " (original only)"}{entry.artist && ` — ${entry.artist}`} {!entry.source_only && <button onClick={() => void favorite(entry)} aria-label={`${entry.favorite ? 'Remove favorite' : 'Favorite'} ${entry.title}`}>{entry.favorite ? '★' : '☆'}</button>}{entry.tags.length > 0 && ` ${entry.tags.join(', ')}`}</li>)}</ul></section>;
}
