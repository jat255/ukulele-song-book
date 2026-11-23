import React, {useCallback, useEffect, useState} from 'react';
import {parseSource} from '../../../../../packages/music/src/parser';
import {MusicBlocks} from '../../music/MusicBlocks';

type Snapshot = {id:string; song_id:string; revision:string; source:string};
type Metadata = {revision:number;favorite:boolean;tags:string[];notes:string};
type Revision = {revision:string;created_at:string};

export function ArrangementEditor({id,csrf}: {id:string;csrf:string}) {
  const [snapshot,setSnapshot] = useState<Snapshot|null>(null);
  const [source,setSource] = useState('');
  const [revisions,setRevisions] = useState<Revision[]>([]);
  const [message,setMessage] = useState('');
  const [metadata,setMetadata] = useState<Metadata|null>(null);
  const [tags,setTags] = useState('');
  const [notes,setNotes] = useState('');
  const headers = {'Content-Type':'application/json','X-CSRF-Token':csrf};
  const history = useCallback(async () => {const response = await fetch(`/api/arrangements/${id}/revisions`); if (response.ok) setRevisions(await response.json() as Revision[]);}, [id]);
  useEffect(() => {
    let active = true;
    void fetch(`/api/arrangements/${id}`).then(async response => {if (!response.ok) throw new Error(); const data = await response.json() as Snapshot; if (active) {setSnapshot(data); setSource(data.source);}}).catch(() => {if (active) setMessage('Arrangement unavailable.');});
    void fetch(`/api/arrangements/${id}/metadata`).then(async response => {if (response.ok) {const data = await response.json() as Metadata; if (active) {setMetadata(data); setTags(data.tags.join(', ')); setNotes(data.notes);}}});
    void history(); return () => {active=false;};
  }, [id,history]);
  async function save() {
    if (!snapshot) return;
    const response = await fetch(`/api/arrangements/${id}`, {method:'PUT',headers:{...headers,'If-Match':snapshot.revision},body:JSON.stringify({source})});
    if (response.status === 409) {setMessage('Changed elsewhere. Your unsaved text is preserved; copy it before reloading.'); return;}
    if (!response.ok) {setMessage('Could not save arrangement.'); return;}
    setSnapshot(await response.json() as Snapshot); setMessage('Arrangement saved'); await history();
  }
  async function restore(target:string) {
    if (!snapshot) return;
    const response = await fetch(`/api/arrangements/${id}/restore`, {method:'POST',headers:{...headers,'If-Match':snapshot.revision},body:JSON.stringify({revision:target})});
    if (!response.ok) {setMessage(response.status === 409 ? 'Changed elsewhere. Your unsaved text is preserved.' : 'Could not restore revision.'); return;}
    const data = await response.json() as Snapshot; setSnapshot(data); setSource(data.source); setMessage('Revision restored'); await history();
  }
  async function duplicate() {
    if (!snapshot) return;
    const response = await fetch(`/api/songs/${snapshot.song_id}/arrangements`, {method:'POST',headers,body:JSON.stringify({source})});
    if (response.ok) {const result = await response.json() as Snapshot; location.href=`/edit?id=${encodeURIComponent(result.id)}`;} else setMessage('Could not create arrangement.');
  }
  async function saveMetadata() {
    if (!metadata) return;
    const response = await fetch(`/api/arrangements/${id}/metadata`, {method:'PATCH',headers,body:JSON.stringify({revision:metadata.revision,favorite:metadata.favorite,tags:tags.split(',').map(value => value.trim()).filter(Boolean),notes})});
    if (!response.ok) {setMessage('Metadata changed elsewhere; your notes and tags are preserved.'); return;}
    const data = await response.json() as Metadata; setMetadata(data); setMessage('Metadata saved');
  }
  async function remove() {
    if (!metadata || !window.confirm(`Remove ${parseSource(snapshot?.source ?? '').metadata.title?.[0] ?? 'this arrangement'} from the library? Its original and revision history will be retained.`)) return;
    const response = await fetch(`/api/arrangements/${id}`, {method:'DELETE',headers,body:JSON.stringify({revision:metadata.revision})});
    if (response.ok) location.href='/'; else setMessage('Could not remove arrangement; metadata may have changed.');
  }
  const previous = revisions.find(item => item.revision !== snapshot?.revision);
  if (!snapshot) return <section>{message || 'Loading arrangement…'}</section>;
  return <section className="arrangement-editor"><h2>Arrangement</h2><div className="editor-columns"><div className="editor-form"><a href="/">Library</a> <a href={`/player?id=${encodeURIComponent(id)}`}>Play song</a> <a href={`/print?id=${encodeURIComponent(id)}`}>Print song</a> <a href={`/api/arrangements/${id}/download`}>Download ChordPro</a><label htmlFor="source-editor">ChordPro source</label><textarea id="source-editor" rows={16} value={source} onChange={event => setSource(event.target.value)} /><div><button onClick={() => void save()}>Save arrangement</button> <button onClick={() => void duplicate()}>Duplicate arrangement</button> <button disabled={!previous || source !== snapshot.source} onClick={() => previous && void restore(previous.revision)}>Restore previous revision</button></div>{message && <p role="status">{message}</p>}{metadata && <section><h3>Library details</h3><label><input type="checkbox" checked={metadata.favorite} onChange={event => setMetadata({...metadata,favorite:event.target.checked})} />Favorite</label><label htmlFor="arrangement-tags">Tags (comma separated)</label><input id="arrangement-tags" value={tags} onChange={event => setTags(event.target.value)} /><label htmlFor="practice-notes">Practice notes</label><textarea id="practice-notes" value={notes} onChange={event => setNotes(event.target.value)} /><button onClick={() => void saveMetadata()}>Save library details</button><button onClick={() => void remove()}>Remove arrangement</button></section>}</div><section className="editor-preview"><h3>Preview</h3><MusicBlocks document={parseSource(source)} performance={{semitones:0,spelling:'auto',capo:0,tuning:'high-g'}} mode="play" /></section></div><h3>Revision history</h3><ul>{revisions.map((item,index) => <li key={`${item.revision}-${index}`}>{item.created_at} {item.revision.slice(0,12)} {item.revision !== snapshot.revision && <button disabled={source !== snapshot.source} onClick={() => void restore(item.revision)}>Restore</button>}</li>)}</ul></section>;
}
