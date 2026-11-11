import React from 'react';
import {createRoot} from 'react-dom/client';
import {parseSource} from '../../../packages/music/src/parser';
import {MusicBlocks} from './music/MusicBlocks';
const example='{title: Lantern}\n{sov: Verse}\n[C]Lan[D/F#]tern\n{eov}\n{sot}\nA|--0--|\nE|-----|\nC|-----|\nG|-----|\n{eot}';
const root=createRoot(document.getElementById('root')!);
function render(source:string,mode:'print'|'play',font:number,columns:number){
  document.documentElement.dataset.renderReady='false';
  const style={"--music-size":`${font}${mode==='print'?'pt':'px'}`,"--music-columns":String(columns)} as React.CSSProperties;
  root.render(<main style={style}><MusicBlocks document={parseSource(source)} performance={{semitones:0,spelling:"auto",capo:0,tuning:"high-g"}} mode={mode}/></main>);
  requestAnimationFrame(()=>document.fonts.ready.then(()=>requestAnimationFrame(()=>document.documentElement.dataset.renderReady='true')));
}
(window as unknown as {renderSong:typeof render}).renderSong=render;
render(example,'play',20,1);
