import React, {useEffect, useRef, useState} from 'react';
import {parseSource} from '../../../../../packages/music/src/parser';
import {ColumnLayout} from './ColumnLayout';
import {chooseScreenColumns} from './layout';
import './player.css';

type Snapshot = {id:string; source:string; revision:string};
type Density = 'tight'|'compact'|'relaxed';
type Columns = 'auto'|1|2|3;

export function Player({id,csrf}: {id:string;csrf:string}) {
  const [snapshot,setSnapshot] = useState<Snapshot|null>(null);
  const [error,setError] = useState('');
  const [font,setFont] = useState(20);
  const [density,setDensity] = useState<Density>('compact');
  const [columns,setColumns] = useState<Columns>('auto');
  const [width,setWidth] = useState(320);
  const [tools,setTools] = useState(false);
  const [focus,setFocus] = useState(false);
  const region = useRef<HTMLDivElement>(null);
  const toggle = useRef<HTMLButtonElement>(null);
  const close = useRef<HTMLButtonElement>(null);
  const sidebar = useRef<HTMLElement>(null);
  useEffect(() => {
    let live = true;
    void fetch(`/api/arrangements/${id}`).then(async response => {if (!response.ok) throw new Error(); const result = await response.json() as Snapshot; if (live) setSnapshot(result);}).catch(() => {if (live) setError('Arrangement unavailable.');});
    void fetch(`/api/arrangements/${id}/played`, {method:'POST',headers:{'X-CSRF-Token':csrf}});
    return () => {live=false;};
  }, [id,csrf]);
  useEffect(() => {
    if (!region.current) return;
    const observer = new ResizeObserver(entries => setWidth(entries[0].contentRect.width));
    observer.observe(region.current); return () => observer.disconnect();
  }, [snapshot]);
  useEffect(() => {
    if (!tools) return;
    if (matchMedia('(max-width: 699px)').matches) close.current?.focus();
    const key = (event:KeyboardEvent) => {
      if (event.key === 'Escape') {setTools(false); toggle.current?.focus(); return;}
      if (event.key === 'Tab' && matchMedia('(max-width: 699px)').matches) {
        const items = Array.from(sidebar.current?.querySelectorAll<HTMLElement>('button:not([disabled]), input:not([disabled]), select:not([disabled]), a[href]') ?? []);
        if (!items.length) return;
        const first=items[0], last=items[items.length-1];
        if (event.shiftKey && document.activeElement === first) {event.preventDefault();last.focus();}
        else if (!event.shiftKey && document.activeElement === last) {event.preventDefault();first.focus();}
      }
    };
    window.addEventListener('keydown', key); return () => window.removeEventListener('keydown', key);
  }, [tools]);
  if (!snapshot) return <main>{error || 'Loading arrangement…'}</main>;
  const effective = chooseScreenColumns({widthPx:width,fontPx:font,preference:columns,minContentWidthPx:300});
  const style = {'--music-size':`${font}px`, '--music-columns':String(effective)} as React.CSSProperties;
  const doc = parseSource(snapshot.source);
  return <main className={`player${focus ? ' player--focus' : ''}`}><header className="player-header"><a href="/">Library</a> <a href={`/edit?id=${encodeURIComponent(id)}`}>Edit source</a>{focus && <button onClick={() => setFocus(false)}>Exit focus</button>}<button ref={toggle} className="player-tools-toggle" aria-expanded={tools} aria-controls="player-tools" onClick={() => setTools(!tools)}>Tools</button></header><div className="player-layout"><div className="player-music" ref={region} style={style} data-density={density}><ColumnLayout document={doc} performance={{semitones:0,spelling:'auto',capo:0,tuning:'high-g'}} columns={effective} width={width} font={font} density={density} />{doc.diagnostics.length > 0 && <details><summary>Source diagnostics</summary><ul>{doc.diagnostics.map((diagnostic,index) => <li key={index}>{diagnostic.message}</li>)}</ul><a href={`/edit?id=${encodeURIComponent(id)}`}>View source</a></details>}</div><aside ref={sidebar} id="player-tools" aria-label="Player tools" className={`player-tools${tools ? ' player-tools--open' : ''}`}><button ref={close} className="player-close" onClick={() => {setTools(false);toggle.current?.focus();}}>Close tools</button><h2>Tools</h2><label htmlFor="font-size">Text size: {font}px</label><input id="font-size" type="range" min="14" max="36" value={font} onChange={event => setFont(Number(event.target.value))} /><label htmlFor="density">Density</label><select id="density" value={density} onChange={event => setDensity(event.target.value as Density)}><option value="tight">Tight</option><option value="compact">Compact</option><option value="relaxed">Relaxed</option></select><label htmlFor="columns">Columns</label><select id="columns" value={columns} onChange={event => setColumns(event.target.value === 'auto' ? 'auto' : Number(event.target.value) as Columns)}><option value="auto">Automatic</option><option value="1">1</option><option value="2">2</option><option value="3">3</option></select><p>Showing {effective} {effective === 1 ? 'column' : 'columns'}{columns !== 'auto' && effective < columns ? ' (limited by available width)' : ''}</p><button onClick={() => setFocus(!focus)}>{focus ? 'Exit focus' : 'Focus view'}</button></aside></div></main>;
}
