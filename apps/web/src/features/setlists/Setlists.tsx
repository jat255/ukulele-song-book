import React, {useEffect, useState} from 'react';

type Entry={id:string;title:string;source_only:boolean};
export type Item={id:string;arrangementId:string;title:string;available:boolean};
export type Setlist={id:string;title:string;revision:string;items:Item[]};

export function Setlists({csrf,id}:{csrf:string;id:string|null}) {
  const [sets,setSets]=useState<Setlist[]>([]);
  const [selected,setSelected]=useState<Setlist|null>(null);
  const [entries,setEntries]=useState<Entry[]>([]);
  const [title,setTitle]=useState('');
  const [choice,setChoice]=useState('');
  const [message,setMessage]=useState('');
  useEffect(() => {
    void fetch('/api/setlists').then(r=>r.ok?r.json():[]).then(setSets);
    void fetch('/api/library').then(r=>r.ok?r.json():[]).then((items:Entry[])=>setEntries(items.filter(item=>!item.source_only)));
    if(id) void fetch(`/api/setlists/${id}`).then(async response=>{if(response.ok) {const data=await response.json() as Setlist;setSelected(data);setTitle(data.title);} else setMessage('Setlist unavailable.');});
  },[id]);
  const headers={'Content-Type':'application/json','X-CSRF-Token':csrf};
  async function create(event:React.FormEvent) {
    event.preventDefault();const response=await fetch('/api/setlists',{method:'POST',headers,body:JSON.stringify({title})});
    if (!response.ok) {setMessage('Could not create setlist.');return;}
    const result=await response.json() as Setlist;location.href=`/setlists?id=${encodeURIComponent(result.id)}`;
  }
  function add() {if(!selected || !choice)return;const item=entries.find(entry=>entry.id===choice);if(item)setSelected({...selected,items:[...selected.items,{id:crypto.randomUUID(),arrangementId:item.id,title:item.title,available:true}]});}
  function move(index:number,delta:number) {if(!selected)return;const target=index+delta;if(target<0 || target>=selected.items.length)return;const items=[...selected.items];[items[index],items[target]]=[items[target],items[index]];setSelected({...selected,items});}
  function drop(event:React.DragEvent, target:number) {
    event.preventDefault();
    if(!selected)return;
    const source=selected.items.findIndex(item=>item.id===event.dataTransfer.getData('text/plain'));
    if(source<0 || source===target)return;
    const items=[...selected.items];
    const [item]=items.splice(source,1);
    items.splice(target,0,item);
    setSelected({...selected,items});
  }
  async function save() {
    if(!selected)return;
    const response=await fetch(`/api/setlists/${selected.id}`,{method:'PUT',headers,body:JSON.stringify({title,revision:selected.revision,items:selected.items.map(item=>({id:item.id,arrangementId:item.arrangementId}))})});
    if (!response.ok) {setMessage(response.status===409?'Setlist changed elsewhere. Your edits are preserved.':'Could not save setlist.');return;}
    setSelected(await response.json() as Setlist);setMessage('Setlist saved');
  }
  async function remove() {
    if(!selected || !window.confirm(`Remove setlist ${selected.title}? Songs will be retained.`))return;
    const response=await fetch(`/api/setlists/${selected.id}`,{method:'DELETE',headers,body:JSON.stringify({revision:selected.revision})});
    if(response.ok) location.href='/setlists';else setMessage('Could not remove setlist; it may have changed.');
  }
  if(!id)return <section><h2>Setlists</h2><form onSubmit={event=>void create(event)}><label htmlFor="set-title">Setlist title</label><input id="set-title" value={title} onChange={event=>setTitle(event.target.value)} required/><button>Create setlist</button></form><ul>{sets.map(set=><li key={set.id}><a href={`/setlists?id=${encodeURIComponent(set.id)}`}>{set.title}</a></li>)}</ul>{message && <p role="status">{message}</p>}</section>;
  if(!selected)return <section>{message || 'Loading setlist…'}</section>;
  return <section><h2>Edit setlist</h2><label htmlFor="set-name">Setlist name</label><input id="set-name" value={title} onChange={event=>setTitle(event.target.value)}/><label htmlFor="arrangement">Choose arrangement</label><select id="arrangement" value={choice} onChange={event=>setChoice(event.target.value)}><option value="">Choose a song</option>{entries.map(entry=><option key={entry.id} value={entry.id}>{entry.title}</option>)}</select><button disabled={!choice} onClick={add}>Add to setlist</button><ol>{selected.items.map((item,index)=><li key={item.id} data-testid="set-occurrence" draggable onDragStart={event=>event.dataTransfer.setData('text/plain',item.id)} onDragOver={event=>event.preventDefault()} onDrop={event=>drop(event,index)}>{item.title}{!item.available && ' (unavailable)'} <button disabled={index===0} onClick={()=>move(index,-1)}>Move up</button> <button disabled={index===selected.items.length-1} onClick={()=>move(index,1)}>Move down</button> <button onClick={()=>setSelected({...selected,items:selected.items.filter(entry=>entry.id!==item.id)})}>Remove</button></li>)}</ol><button onClick={()=>void save()}>Save setlist</button> <a href={`/set-player?id=${encodeURIComponent(selected.id)}`}>Play setlist</a> <a href={`/set-print?id=${encodeURIComponent(selected.id)}`}>Print setlist</a> <button onClick={()=>void remove()}>Delete setlist</button>{message && <p role="status">{message}</p>}</section>;
}
