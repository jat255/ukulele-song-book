import {resolveDiagram} from '../../../../packages/music/src/diagrams';
import {transposeChord} from '../../../../packages/music/src/transpose';
import {ChordHint} from '../features/player/ChordHint';
import React from 'react';
import type {MusicBlock,MusicDocument,PerformanceSettings} from '../../../../packages/music/src/model';
import type {SectionRepeats} from './repeatSections';
import './music.css';

function renderBlock(block:MusicBlock,mode:'play'|'print',document:MusicDocument,performance:PerformanceSettings,compact:boolean):React.ReactNode {
  if(block.kind==='grid') return <div className="chord-grid">{block.label && <div className="section-label">{block.label}</div>}{block.text.split(/\r\n|\r|\n/).filter(Boolean).map((line,i)=>{
    const tokens=line.split(/(:\|:\d*>?|:\|\d*>?|\|\||\|(?::|\.|\d+>?)?|\s+)/).filter(token=>token && !/^\s+$/.test(token));
    const first=tokens.findIndex(token=>token.includes('|')), last=tokens.reduce((index,token,i)=>token.includes('|') ? i : index,-1);
    return <div className="chord-grid-line" key={i}>{tokens.map((token,j)=>{
      if (token.includes('|')) return <span key={j} className="chord-grid-bar">{token}</span>;
      const parts=token.split('~');
      const chords=j>first && j<last && parts.every(part=>/^[A-G]/.test(part) && !transposeChord(part,0,'auto').diagnostic);
      return <span key={j} className="chord-grid-cell">{chords ? parts.map((chord,k)=><React.Fragment key={k}>{k>0 && '~'}{mode==='play' ? <ChordHint chord={chord} diagram={resolveDiagram(chord,performance.tuning,document.definitions)}/> : <span className="chord">{chord}</span>}</React.Fragment>) : token}</span>;
    })}</div>;
  })}</div>;
  if (compact && block.kind==='lyric' && block.segments.every(segment=>!segment.lyric.trim())) {
    const chords=block.segments.flatMap(segment=>segment.chord ? [segment.chord] : []);
    return chords.length ? <div className="chord-only">{chords.map((chord,index)=>
      <ChordHint key={index} chord={chord} diagram={resolveDiagram(chord,performance.tuning,document.definitions)}/>
    )}</div> : <div className="score-space" aria-hidden="true"/>;
  }
  if(block.kind==='lyric') return <div className="lyric-line">{block.segments.map((segment,i)=>{
    if(!segment.chord) return <span className="lyric-fragment" key={i}>{segment.lyric}</span>;
    const match=segment.lyric.match(/^(\s*\S+)([\s\S]*)$/);
    const first=match?.[1] ?? segment.lyric, rest=match?.[2] ?? '';
    return <React.Fragment key={i}><span className={`segment${segment.lyric.trim() ? "" : " segment--empty"}`} data-chord={segment.chord}>{mode==='play' ? <ChordHint chord={segment.chord} diagram={resolveDiagram(segment.chord,performance.tuning,document.definitions)}/> : <span className="chord">{segment.chord}</span>}<span>{first || '\u00a0'}</span></span><span className="lyric-fragment">{rest}</span></React.Fragment>;
  })}</div>;
  if(block.kind==='tab') {
    if (mode==='play' || !block.groups.length) return <pre data-testid="tab" className="tab">{block.text}</pre>;
    const lines=[...block.text.matchAll(/[^\r\n]*(?:\r\n|\r|\n|$)/g)].map(match => match[0]).filter(Boolean);
    let cursor=0;
    const chunks=block.groups.map(group => {const chunk=lines.slice(cursor,group.endLine).join('');cursor=group.endLine;return chunk;});
    if (cursor<lines.length) chunks[chunks.length-1] += lines.slice(cursor).join('');
    return <>{chunks.map((chunk,index)=><pre data-testid="tab" className="tab tab--group" key={index}>{chunk}</pre>)}</>;
  }
  if(block.kind==='section' && block.action==='start') return <div className="section-label" data-section={block.name}>{block.label || block.name}</div>;
  if(block.kind==='comment') return <p className="comment">{block.text}</p>;
  if(block.kind==='directive' && block.name==='title') return <h1>{block.value}</h1>;
  if(block.kind==='directive' && (block.name==='subtitle' || block.name==='artist')) return <p className="metadata">{block.value}</p>;
  if(block.kind==='directive' && block.name==='capo') return <p className="metadata">Capo {block.value}</p>;
  if(block.kind==='unsupported') return <p className="unsupported">{block.text}</p>;
  return null;
}
export function blockId(block:MusicBlock,index:number):string {return `${block.span.start}:${index}`;}
export function MusicBlocks({document,performance,mode,measure=false,plan,repeats}:{document:MusicDocument;performance:PerformanceSettings;mode:'play'|'print';measure?:boolean;plan?:string[][];repeats?:SectionRepeats}) {
  const compact = mode==='play' && measure;
  let through = -1;
  const header: React.ReactNode[] = [];
  const sections: string[] = [];
  let started = false;
  const rendered = document.blocks.flatMap<{id:string;block:MusicBlock;node:React.ReactNode;chorus:boolean}>((block,index) => {
    if (index <= through) return [];
    const id=blockId(block,index);
    const repeat=compact ? repeats?.get(index) : undefined;
    if (repeat) {
      through=repeat.end;
      return [{id,block,chorus:block.kind==='section' && block.name==='chorus',node:<div className="repeat-cue">Repeat {repeat.label}</div>}];
    }
    if (compact && block.kind==='section') {
      if (block.action==='start') sections.push(block.name);
      else if (sections.at(-1)===block.name) sections.pop();
    }
    const node=renderBlock(block,mode,document,performance,compact);
    if (node===null) return [];
    const blank=block.kind==='lyric' && block.segments.every(segment=>!segment.lyric.trim() && !segment.chord);
    if (compact && !started) {
      if (blank) return [];
      if (block.kind==='directive' && ['title','subtitle','artist'].includes(block.name)) {
        header.push(<React.Fragment key={id}>{node}</React.Fragment>);
        return [];
      }
    }
    started=true;
    return [{id,block,node,chorus:sections.includes('chorus')}];
  });
  function element(item:typeof rendered[number]) {
    if (!measure) return <React.Fragment key={item.id}>{item.node}</React.Fragment>;
    const heading = item.block.kind === 'section' && item.block.action === 'start';
    const className = `music-block${heading ? ' music-block--heading' : ''}${item.chorus ? ' music-block--chorus' : ''}`;
    return <div key={item.id} data-block-id={item.id} data-block-kind={heading ? 'heading' : item.block.kind === 'tab' ? 'tab' : item.block.kind === 'lyric' ? 'line' : 'other'} className={className}>{item.node}</div>;
  }
  const byId = new Map(rendered.map(item => [item.id,item]));
  const article = <article data-testid={!compact ? 'song' : undefined} className={`music music--${mode}${plan ? ' music--planned' : ''}`} style={plan ? {'--planned-columns':String(plan.length)} as React.CSSProperties : undefined}>
    {plan ? plan.map((column,index) => <div className="music-column" key={index}>{column.map(id => {const item=byId.get(id); return item ? element(item) : null;})}</div>) : rendered.map(element)}
  </article>;
  if (!compact) return article;
  return <div data-testid="song" className="score">{header.length>0 && <header className="score-heading">{header}</header>}{article}</div>;
}
