import React, {useState} from 'react';
import {applyChordEdit, getEditableLines} from '../../../../../packages/music/src/chordEditing';

export function ChordPlacementEditor({source, onChange}: {source:string; onChange:(source:string)=>void}) {
  const [selected, setSelected] = useState<{line:number; chord:number; source:string}|null>(null);
  const [adding, setAdding] = useState(false);
  const [name, setName] = useState('');
  const [message, setMessage] = useState('');
  const lines = getEditableLines(source);
  const current = selected?.source === source ? selected : null;

  function cancel() { setSelected(null); setAdding(false); setMessage(''); }
  function act(fn:()=>string) {
    try { onChange(fn()); cancel(); }
    catch (error) { setMessage(error instanceof Error ? error.message : 'Could not edit chord'); }
  }
  function selectChord(line:number, chord:{id:number;name:string}) {
    setSelected({line, chord:chord.id, source}); setAdding(false); setName(chord.name); setMessage('');
  }
  return <section className="chord-editor">
    <h4>Move and edit chords</h4>
    <p className="chord-editor-help">Select a chord to move, rename or remove it. To move it, select its new position in the same line.</p>
    <div className="chord-editor-toolbar">
      {!current && !adding && <button type="button" onClick={()=>{setAdding(true); setName(''); setMessage('');}}>Add chord</button>}
      {(current || adding) && <>
        <label>Chord <input value={name} onChange={event=>setName(event.target.value)} placeholder="e.g. C or Am" /></label>
        {current && <>
          <button type="button" onClick={()=>act(()=>applyChordEdit(source,lines[current.line].span,{kind:'rename',id:current.chord,name}))}>Rename</button>
          <button type="button" onClick={()=>act(()=>applyChordEdit(source,lines[current.line].span,{kind:'remove',id:current.chord}))}>Remove</button>
        </>}
        <button type="button" onClick={cancel}>Cancel</button>
      </>}
    </div>
    {(current || adding) && <p className="chord-editor-instruction" role="status">{current ? 'Choose a highlighted position in this line to move the selected chord.' : 'Enter a chord name, then choose a highlighted position in the lyrics.'}</p>}
    {message && <p className="chord-editor-error" role="alert">{message === 'Invalid chord name' ? 'Enter a chord name first.' : message}</p>}
    <div className="chord-editor-sheet">
      {lines.map((line,index)=><div className="chord-editor-line" key={`${line.span.start}-${index}`}>
        {!line.editable ? <p>{line.reason} {line.lyrics}</p> : !line.lyrics && !line.chords.length && !adding ? <div className="chord-editor-blank" aria-hidden="true" /> :
          <div className={`chord-editor-lyrics${line.lyrics.trim() ? '' : ' chord-editor-lyrics--chords-only'}`} aria-label={`Lyric line ${index+1}`}>
            {current?.line === index && !!line.lyrics.trim() && Array.from({length:4},(_,i)=>{
              const spaces=(line.lyrics.match(/^[ \t]*/)?.[0].length ?? 0)+4-i;
              return <button key={`before-${i}`} type="button" className="chord-position" aria-label={`Place chord ${spaces} ${spaces === 1 ? 'space' : 'spaces'} before lyrics`} title={`Place chord ${spaces} ${spaces === 1 ? 'space' : 'spaces'} before lyrics`} onClick={()=>act(()=>applyChordEdit(source,line.span,{kind:'move-before',id:current.chord,spaces}))}>{'\u00a0'}</button>;
            })}
            {line.boundaries.map((position,i)=>{
              const atPosition = line.chords.filter(chord=>chord.offset===position);
              const canPlace = adding || current?.line === index;
              const character = line.lyrics.slice(position,line.boundaries[i+1] ?? position);
              return <span className="chord-editor-cell" key={position}>
                <span className="chord-editor-chords">{atPosition.map(chord=><button key={chord.id} type="button" aria-pressed={current?.line===index && current.chord===chord.id} onClick={()=>selectChord(index,chord)}>{chord.name}</button>)}</span>
                {canPlace ? <button type="button" className="chord-position" aria-label={`Place chord at position ${i+1} in line ${index+1}`} title="Place chord here" onClick={()=>act(()=>current ? applyChordEdit(source,line.span,{kind:'move',id:current.chord,offset:position}) : applyChordEdit(source,line.span,{kind:'add',offset:position,name}))}>{character || '▏'}</button> : <span className="chord-editor-character">{character || '\u00a0'}</span>}
              </span>;
            })}
          </div>}
      </div>)}
    </div>
  </section>;
}
