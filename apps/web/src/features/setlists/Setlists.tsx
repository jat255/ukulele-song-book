import React, {useEffect, useState} from 'react';
import {downloadSelection,listOfflineSetlists,verifyAvailability,removeDownload} from '../../offline/downloads';
import type {DownloadManifest} from '../../offline/downloads';
import {prepareShell} from '../../offline/shell';

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
  const [includeOriginals,setIncludeOriginals]=useState(false);
  const [downloadState,setDownloadState]=useState('Online only');
  useEffect(()=>{if(!id || !csrf)return;let active=true;void verifyAvailability(`setlist:${id}`).then(status=>{if(active)setDownloadState(status==='downloaded'?'Downloaded':status==='incomplete'?'Incomplete':'Online only');});return()=>{active=false;};},[id,csrf]);
  const [savedVersion,setSavedVersion]=useState('');
  const version=(name:string,items:Item[])=>JSON.stringify([name,items.map(item=>[item.id,item.arrangementId])]);
  useEffect(() => {
    if(!csrf){void listOfflineSetlists<Setlist>().then(setSets);return;}
    void fetch('/api/setlists').then(r=>r.ok?r.json():[]).then(setSets);
    void fetch('/api/library').then(r=>r.ok?r.json():[]).then((items:Entry[])=>setEntries(items.filter(item=>!item.source_only)));
    if(id) void fetch(`/api/setlists/${id}`).then(async response=>{if(response.ok) {const data=await response.json() as Setlist;setSelected(data);setTitle(data.title);setSavedVersion(version(data.title,data.items));} else setMessage('Setlist unavailable.');});
  },[id,csrf]);
  const headers={'Content-Type':'application/json','X-CSRF-Token':csrf};
  async function download() {if(!selected)return;try {setMessage('Downloading');const response=await fetch(`/api/downloads/setlists/${selected.id}`);if(!response.ok)throw new Error();const manifest=await response.json() as DownloadManifest;if((manifest.setlist as Setlist|null)?.revision!==selected.revision){setMessage('Setlist changed. Reload before downloading.');return;}const shell=await prepareShell();await downloadSelection(manifest,includeOriginals,shell);setMessage('');setDownloadState('Downloaded');}catch{setMessage('Download failed');}}
  async function removeOffline(){if(!selected)return;try{await removeDownload(`setlist:${selected.id}`);setDownloadState('Online only');setMessage('');}catch{setMessage('Could not remove download.');}}
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
    const saved=await response.json() as Setlist;setSelected(saved);setTitle(saved.title);setSavedVersion(version(saved.title,saved.items));setMessage('Setlist saved');
  }
  async function remove() {
    if(!selected || !window.confirm(`Remove setlist ${selected.title}? Songs will be retained.`))return;
    const response=await fetch(`/api/setlists/${selected.id}`,{method:'DELETE',headers,body:JSON.stringify({revision:selected.revision})});
    if(response.ok) location.href='/setlists';else setMessage('Could not remove setlist; it may have changed.');
  }
  if(!csrf)return <section><h2>Downloaded setlists</h2><ul>{sets.map(set=><li key={set.id}><a href={`/set-player?id=${encodeURIComponent(set.id)}`}>{set.title}</a></li>)}</ul></section>;
  if(!id)return <section><h2>Setlists</h2><form onSubmit={event=>void create(event)}><label htmlFor="set-title">Setlist title</label><input id="set-title" value={title} onChange={event=>setTitle(event.target.value)} required/><button>Create setlist</button></form><ul>{sets.map(set=><li key={set.id}><a href={`/setlists?id=${encodeURIComponent(set.id)}`}>{set.title}</a></li>)}</ul>{message && <p role="status">{message}</p>}</section>;
  if(!selected)return <section>{message || 'Loading setlist…'}</section>;
  return <section><h2>Edit setlist</h2><label htmlFor="set-name">Setlist name</label><input id="set-name" value={title} onChange={event=>setTitle(event.target.value)}/><label htmlFor="arrangement">Choose arrangement</label><select id="arrangement" value={choice} onChange={event=>setChoice(event.target.value)}><option value="">Choose a song</option>{entries.map(entry=><option key={entry.id} value={entry.id}>{entry.title}</option>)}</select><button disabled={!choice} onClick={add}>Add to setlist</button><ol>{selected.items.map((item,index)=><li key={item.id} data-testid="set-occurrence" draggable onDragStart={event=>event.dataTransfer.setData('text/plain',item.id)} onDragOver={event=>event.preventDefault()} onDrop={event=>drop(event,index)}>{item.title}{!item.available && ' (unavailable)'} <button disabled={index===0} onClick={()=>move(index,-1)}>Move up</button> <button disabled={index===selected.items.length-1} onClick={()=>move(index,1)}>Move down</button> <button onClick={()=>setSelected({...selected,items:selected.items.filter(entry=>entry.id!==item.id)})}>Remove</button></li>)}</ol><button onClick={()=>void save()}>Save setlist</button> <label><input type="checkbox" checked={includeOriginals} onChange={event=>setIncludeOriginals(event.target.checked)}/>Include original PDFs</label> <button disabled={version(title,selected.items)!==savedVersion} onClick={()=>void download()}>Download setlist</button> <span>{downloadState}</span>{downloadState!=='Online only' && <button onClick={()=>void removeOffline()}>Remove setlist download</button>} <a href={`/set-player?id=${encodeURIComponent(selected.id)}`}>Play setlist</a> <a href={`/set-print?id=${encodeURIComponent(selected.id)}`}>Print setlist</a> <button onClick={()=>void remove()}>Delete setlist</button>{message && <p role="status">{message}</p>}</section>;
}
