import React,{useEffect,useState} from 'react';
import {listOfflineSnapshots} from '../../offline/downloads';
import {parseSource} from '../../../../../packages/music/src/parser';

type Choice={id:string;title:string;artist?:string;source_only?:boolean};
export function SongChooser({destination,csrf}:{destination:'player'|'print';csrf:string}) {
 const [songs,setSongs]=useState<Choice[]>([]),[query,setQuery]=useState(''),[error,setError]=useState('');
 useEffect(()=>{let active=true;void(async()=>{
  try{let entries:Choice[];
   if(csrf){const response=await fetch('/api/library');if(!response.ok)throw new Error();entries=await response.json();}
   else entries=(await listOfflineSnapshots()).map(song=>({id:song.id,title:parseSource(song.source).metadata.title?.[0] ?? 'Untitled'}));
   if(active)setSongs(entries.filter(song=>!song.source_only));
  }catch{if(active)setError('Could not load songs. Return to the library and try again.');}
 })();return()=>{active=false;};},[csrf]);
 const filtered=songs.filter(song=>(song.title+' '+(song.artist ?? '')).toLowerCase().includes(query.toLowerCase()));
 return <section className="song-chooser"><h2>Choose a song to {destination==='player'?'play':'print'}</h2><p>{destination==='player'?'Open a song to tune your view and start playing.':'Choose an arrangement to preview and print.'}</p><label htmlFor="choose-song">Find a song</label><input id="choose-song" type="search" value={query} onChange={event=>setQuery(event.target.value)}/>{error && <p role="alert">{error}</p>}<ul>{filtered.map(song=><li key={song.id}><a href={`/${destination}?id=${encodeURIComponent(song.id)}`}><strong>{song.title}</strong>{song.artist && <span>{song.artist}</span>}<span aria-hidden="true">{destination==='player'?'Play':'Print'} →</span></a></li>)}</ul>{!error && !filtered.length && <p>No matching songs. <a href="/imports">Import music</a> or change your search.</p>}</section>;
}
