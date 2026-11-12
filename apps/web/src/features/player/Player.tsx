import React, {useEffect, useRef, useState} from 'react';
import {getOfflineSnapshot,getOfflineOriginals} from '../../offline/downloads';
import {parseSource} from '../../../../../packages/music/src/parser';
import {blockId} from '../../music/MusicBlocks';
import {derivePerformance,serializePerformanceArrangement} from '../../../../../packages/music/src/transpose';
import {resolveDiagram} from '../../../../../packages/music/src/diagrams';
import type {PerformanceSettings,PlaySettings} from '../../../../../packages/music/src/model';
import {usePreferences} from '../settings/preferences';
import {ColumnLayout} from './ColumnLayout';
import {ChordDiagram} from './ChordDiagram';
import {chooseScreenColumns} from './layout';
import {useAutoScroll} from './useAutoScroll';
import {useWakeLock} from './useWakeLock';
import './player.css';

type Snapshot = {id:string; song_id:string; source:string; revision:string};

export function Player({id,csrf,forceCached=false,selectionId}: {id:string;csrf:string;forceCached?:boolean;selectionId?:string}) {
  const [snapshot,setSnapshot] = useState<Snapshot|null>(null);
  const [error,setError] = useState('');
  const [width,setWidth] = useState(320);
  const [tools,setTools] = useState(false);
  const [activeSection,setActiveSection] = useState('');
  const [originals,setOriginals]=useState<string[]>([]);
  const cachedOnly=forceCached || new URLSearchParams(location.search).get('cached')==='1';
  useEffect(()=>{if(csrf && !cachedOnly)return;let active=true;let urls:string[]=[];void getOfflineOriginals(id).then(blobs=>{if(!active)return;urls=blobs.map(blob=>URL.createObjectURL(blob));setOriginals(urls);});return()=>{active=false;urls.forEach(url=>URL.revokeObjectURL(url));};},[id,csrf,cachedOnly]);
  const preferences=usePreferences(id,csrf);
  const play=preferences.data.groups.play.value;
  const storedPerformance=preferences.data.groups.performance.value;
  const scroll=useAutoScroll(play.scrollPxPerSecond);
  const wake=useWakeLock();
  const region = useRef<HTMLDivElement>(null);
  const toggle = useRef<HTMLButtonElement>(null);
  const close = useRef<HTMLButtonElement>(null);
  const sidebar = useRef<HTMLElement>(null);
  useEffect(() => {
    let live = true;
    if(cachedOnly){void getOfflineSnapshot(id,selectionId).then(saved=>{if(live){if(saved)setSnapshot(saved);else setError('Cached arrangement unavailable.');}});return()=>{live=false;};}
    void fetch(`/api/arrangements/${id}`).then(async response => {if (!response.ok) throw new Error(); const result = await response.json() as Snapshot; if (live) setSnapshot(result);}).catch(() => {void getOfflineSnapshot(id,selectionId).then(saved=>{if(live){if(saved)setSnapshot(saved);else setError('Arrangement unavailable offline.');}});});
    if(navigator.onLine)void fetch(`/api/arrangements/${id}/played`, {method:'POST',headers:{'X-CSRF-Token':csrf}}).catch(()=>{});
    return () => {live=false;};
  }, [id,csrf,cachedOnly,selectionId]);
  useEffect(() => {
    if (!region.current) return;
    const observer = new ResizeObserver(entries => setWidth(entries[0].contentRect.width));
    observer.observe(region.current); return () => observer.disconnect();
  }, [snapshot,preferences.ready]);
  useEffect(() => {scroll.pause();}, [id,width,play.fontPx,play.density,play.columns,play.focus,storedPerformance.semitones,storedPerformance.capo,storedPerformance.spelling,storedPerformance.tuning,scroll.pause]);
  useEffect(() => {
    if (!activeSection) return;
    let second=0;
    const first=requestAnimationFrame(() => {second=requestAnimationFrame(() => {
      const target=Array.from(region.current?.querySelectorAll<HTMLElement>('[data-block-id]') ?? []).find(element => element.dataset.blockId === activeSection);
      target?.scrollIntoView({block:'start'});
    });});
    return () => {cancelAnimationFrame(first);cancelAnimationFrame(second);};
  }, [activeSection,width,play.fontPx,play.density,play.columns,storedPerformance.semitones,storedPerformance.spelling]);
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
  if (!snapshot || !preferences.ready) return <main>{error || 'Loading arrangement…'}</main>;
  const original=parseSource(snapshot.source);
  const sourceCapo=original.blocks.find(block => block.kind==='directive' && block.name==='capo');
  const parsedCapo=sourceCapo?.kind === 'directive' ? Number(sourceCapo.value) : 0;
  const performance:PerformanceSettings = preferences.data.groups.performance.updated_at === 0 && Number.isInteger(parsedCapo) && parsedCapo >= 0 && parsedCapo <= 12 ? {...storedPerformance,capo:parsedCapo} : storedPerformance;
  const doc=derivePerformance(original,performance);
  const effective = chooseScreenColumns({widthPx:width,fontPx:play.fontPx,preference:play.columns,minContentWidthPx:300});
  const style = {'--music-size':`${play.fontPx}px`, '--music-columns':String(effective)} as React.CSSProperties;
  const changePlay=(part:Partial<PlaySettings>) => preferences.change('play',{...play,...part});
  const changePerformance=(part:Partial<PerformanceSettings>) => preferences.change('performance',{...performance,...part});
  const sections=doc.blocks.flatMap((block,index) => block.kind === 'section' && block.action === 'start' ? [{id:blockId(block,index),label:block.label || block.name}] : []);
  const chords=[...new Set(doc.blocks.flatMap(block => block.kind === 'lyric' ? block.segments.flatMap(segment => segment.chord ? [segment.chord] : []) : []))];
  async function saveVariant() {
    if (!csrf || !navigator.onLine) {setError('A connection is required to save a variant.');return;}
    if (!snapshot) return;
    const result=serializePerformanceArrangement(original,performance);
    if (result.diagnostics.some(item => item.code === 'unsafe-serialization')) {setError('This source requires manual review before saving a transposed variant.');return;}
    if (result.diagnostics.some(item => item.code === 'tab-not-transposed') && !window.confirm('Tab remains unchanged. Save this variant with the original tab?')) return;
    const response=await fetch(`/api/songs/${snapshot.song_id}/arrangements`,{method:'POST',headers:{'Content-Type':'application/json','X-CSRF-Token':csrf},body:JSON.stringify({source:result.source,source_arrangement_id:id})});
    if (response.ok) {const variant=await response.json() as Snapshot;location.href=`/player?id=${encodeURIComponent(variant.id)}`;} else setError('Could not save variant.');
  }
  return <main className={`player${play.focus ? ' player--focus' : ''}`}><header className="player-header"><a href="/">Library</a> {originals.map((url,index)=><a key={url} href={url} target="_blank" rel="noreferrer">Open downloaded original{originals.length>1 ? ` ${index+1}` : ''}</a>)} <a href={`/edit?id=${encodeURIComponent(id)}`}>Edit source</a> <a href={`/print?id=${encodeURIComponent(id)}`}>Print</a>{play.focus && <button onClick={() => changePlay({focus:false})}>Exit focus</button>}<button ref={toggle} className="player-tools-toggle" aria-expanded={tools} aria-controls="player-tools" onClick={() => setTools(!tools)}>Tools</button></header><div className="player-layout"><div className="player-music" ref={region} style={style} data-density={play.density}><ColumnLayout document={doc} performance={performance} columns={effective} width={width} font={play.fontPx} density={play.density} />{doc.diagnostics.length > 0 && <details><summary>Source diagnostics</summary><ul>{doc.diagnostics.map((diagnostic,index) => <li key={index}>{diagnostic.message}</li>)}</ul><a href={`/edit?id=${encodeURIComponent(id)}`}>View source</a></details>}{(error || preferences.error) && <p role="alert">{error || preferences.error}</p>}</div><aside ref={sidebar} id="player-tools" aria-label="Player tools" className={`player-tools${tools ? ' player-tools--open' : ''}`}><button ref={close} className="player-close" onClick={() => {setTools(false);toggle.current?.focus();}}>Close tools</button><h2>Tools</h2><label htmlFor="font-size">Text size: {play.fontPx}px</label><input id="font-size" type="range" min="12" max="40" value={play.fontPx} onChange={event => changePlay({fontPx:Number(event.target.value)})} /><label htmlFor="density">Density</label><select id="density" value={play.density} onChange={event => changePlay({density:event.target.value as PlaySettings['density']})}><option value="tight">Tight</option><option value="compact">Compact</option><option value="relaxed">Relaxed</option></select><label htmlFor="columns">Columns</label><select id="columns" value={play.columns} onChange={event => changePlay({columns:event.target.value === 'auto' ? 'auto' : Number(event.target.value) as PlaySettings['columns']})}><option value="auto">Automatic</option><option value="1">1</option><option value="2">2</option><option value="3">3</option></select><p>Showing {effective} {effective === 1 ? 'column' : 'columns'}{play.columns !== 'auto' && effective < play.columns ? ' (limited by available width)' : ''}</p><button onClick={() => changePlay({focus:!play.focus})}>{play.focus ? 'Exit focus' : 'Focus view'}</button><label htmlFor="transpose">Transpose semitones</label><input id="transpose" type="number" min="-24" max="24" value={performance.semitones} onChange={event => changePerformance({semitones:Math.max(-24,Math.min(24,Number(event.target.value)))})}/><label htmlFor="spelling">Accidentals</label><select id="spelling" value={performance.spelling} onChange={event => changePerformance({spelling:event.target.value as PerformanceSettings['spelling']})}><option value="auto">Follow key</option><option value="sharps">Sharps</option><option value="flats">Flats</option></select><label htmlFor="capo">Capo</label><input id="capo" type="number" min="0" max="12" value={performance.capo} onChange={event => changePerformance({capo:Math.max(0,Math.min(12,Number(event.target.value)))})}/><label htmlFor="tuning">Tuning</label><select id="tuning" value={performance.tuning} onChange={event => changePerformance({tuning:event.target.value as PerformanceSettings['tuning']})}><option value="high-g">High G</option><option value="low-g">Low G</option></select><p>Shape key: {doc.scopes[0]?.displayKey ?? 'unknown'}; sounding key: {doc.scopes[0]?.soundingKey ?? 'unknown'}</p><button onClick={() => void saveVariant()}>Save transposed variant</button>{sections.length > 0 && <><label htmlFor="section">Section</label><select id="section" value={activeSection} onChange={event => {const value=event.target.value;setActiveSection(value);scroll.pause();const target=Array.from(region.current?.querySelectorAll<HTMLElement>('[data-block-id]') ?? []).find(element => element.dataset.blockId === value);target?.scrollIntoView({block:'start'});}}><option value="">Choose section</option>{sections.map(section => <option key={section.id} value={section.id}>{section.label}</option>)}</select></>}<label htmlFor="speed">Scroll speed</label><input id="speed" type="number" min="1" max="100" value={play.scrollPxPerSecond} onChange={event => changePlay({scrollPxPerSecond:Math.max(1,Math.min(100,Number(event.target.value)))})}/><button onClick={scroll.running ? scroll.pause : scroll.start}>{scroll.running ? 'Pause scrolling' : 'Start scrolling'}</button><button onClick={() => void (wake.status === 'on' ? wake.release() : wake.request())}>{wake.status === 'on' ? 'Allow screen sleep' : 'Keep screen awake'}</button>{wake.status === 'unavailable' && <p>Screen wake lock is unavailable.</p>}<h3>Chords</h3><ul>{chords.map(chord => {const diagram=resolveDiagram(chord,performance.tuning,original.definitions);return <ChordDiagram key={chord} chord={chord} diagram={diagram}/>;})}</ul></aside></div></main>;
}
