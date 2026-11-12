import React, {useEffect,useState} from 'react';
import {getOfflineSetlist} from '../../offline/downloads';
import {Player} from '../player/Player';
import type {Setlist} from './Setlists';

export function SetlistPlayer({id,csrf}:{id:string;csrf:string}) {
  const [set,setSet]=useState<Setlist|null>(null);
  const [index,setIndex]=useState(0);
  const [error,setError]=useState('');
  useEffect(()=>{void fetch(`/api/setlists/${id}`).then(async response=>{if(!response.ok)throw new Error();setSet(await response.json() as Setlist);}).catch(()=>{void getOfflineSetlist<Setlist>(id).then(saved=>{if(saved)setSet(saved);else setError('Setlist unavailable offline.');});});},[id]);
  if(!set)return <main>{error || 'Loading setlist…'}</main>;
  const item=set.items[index];
  if(!item)return <main><a href={`/setlists?id=${encodeURIComponent(id)}`}>Edit setlist</a><p>This setlist has no songs.</p></main>;
  const change=(next:number)=>{setIndex(next);window.scrollTo(0,0);};
  return <div><header className="setlist-navigation"><a href={`/setlists?id=${encodeURIComponent(id)}`}>Setlist</a> <span>Song {index+1} of {set.items.length}</span> <button disabled={index===0} onClick={()=>change(index-1)}>Previous song</button> <button disabled={index===set.items.length-1} onClick={()=>change(index+1)}>Next song</button></header>{item.available ? <Player key={item.id} id={item.arrangementId} csrf={csrf}/> : <main><p>{item.title} is unavailable.</p><a href={`/setlists?id=${encodeURIComponent(id)}`}>Review setlist</a></main>}</div>;
}
