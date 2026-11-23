import React from 'react';
import {createRoot} from 'react-dom/client';
import {parseSource} from '../../../packages/music/src/parser';
import {derivePerformance} from '../../../packages/music/src/transpose';
import {resolveDiagram} from '../../../packages/music/src/diagrams';
import {gridChords} from '../../../packages/music/src/grid';
import type {PerformanceSettings} from '../../../packages/music/src/model';
import {MusicBlocks} from './music/MusicBlocks';
import {ChordDiagram} from './features/player/ChordDiagram';
const example='{title: Lantern}\n{sov: Verse}\n[C]Lan[D/F#]tern\n{eov}\n{sot}\nA|--0--|\nE|-----|\nC|-----|\nG|-----|\n{eot}';
const root=createRoot(document.getElementById('root')!);
function render(source:string,mode:'print'|'play',font:number,columns:number,performance:PerformanceSettings={semitones:0,spelling:'auto',capo:0,tuning:'high-g'},density='compact',diagrams=false){
  document.documentElement.dataset.renderReady='false';
  const style={"--music-size":`${font}${mode==='print'?'pt':'px'}`,"--music-columns":String(columns)} as React.CSSProperties;
  const original=parseSource(source), doc=derivePerformance(original,performance);
  const chords=[...new Set(doc.blocks.flatMap(block => block.kind === 'lyric' ? block.segments.flatMap(segment => segment.chord ? [segment.chord] : []) : block.kind==='grid' ? gridChords(block.text) : []))];
  const scope=doc.scopes[0];
  root.render(<main style={style} data-print-density={density}>{mode==='print' && (scope?.sourceKey || performance.capo !== 0) && <p className="print-keys">Source key: {scope?.sourceKey ?? 'unknown'}; shape key: {scope?.displayKey ?? 'unknown'}; sounding key: {scope?.soundingKey ?? 'unknown'}; capo: {performance.capo}</p>}<MusicBlocks document={doc} performance={performance} mode={mode}/>{mode==='print' && diagrams && <ul className="print-diagrams">{chords.map(chord => <ChordDiagram key={chord} chord={chord} diagram={resolveDiagram(chord,performance.tuning,original.definitions)}/>)}</ul>}</main>);
  requestAnimationFrame(()=>document.fonts.ready.then(()=>requestAnimationFrame(()=>document.documentElement.dataset.renderReady='true')));
}
function renderSet(songs:{source:string;performance:PerformanceSettings}[],font:number,columns:number,density:string,diagrams:boolean,songBreak:'new-page'|'pack') {
  document.documentElement.dataset.renderReady='false';
  const style={"--music-size":`${font}pt`,"--music-columns":String(columns)} as React.CSSProperties;
  root.render(<main style={style} data-print-density={density}>{songs.map((song,index) => {
    const original=parseSource(song.source), doc=derivePerformance(original,song.performance), scope=doc.scopes[0];
    const chords=[...new Set(doc.blocks.flatMap(block => block.kind === 'lyric' ? block.segments.flatMap(segment => segment.chord ? [segment.chord] : []) : block.kind==='grid' ? gridChords(block.text) : []))];
    return <section key={index} className={`set-print-song${index>0 && songBreak==='new-page' ? ' set-print-song--page' : ''}`}>{(scope?.sourceKey || song.performance.capo !== 0) && <p className="print-keys">Source key: {scope?.sourceKey ?? 'unknown'}; shape key: {scope?.displayKey ?? 'unknown'}; sounding key: {scope?.soundingKey ?? 'unknown'}; capo: {song.performance.capo}</p>}<MusicBlocks document={doc} performance={song.performance} mode="print"/>{diagrams && <ul className="print-diagrams">{chords.map(chord => <ChordDiagram key={chord} chord={chord} diagram={resolveDiagram(chord,song.performance.tuning,original.definitions)}/>)}</ul>}</section>;
  })}</main>);
  requestAnimationFrame(()=>document.fonts.ready.then(()=>requestAnimationFrame(()=>document.documentElement.dataset.renderReady='true')));
}
(window as unknown as {renderSet:typeof renderSet}).renderSet=renderSet;
(window as unknown as {renderSong:typeof render}).renderSong=render;
render(example,'play',20,1);
