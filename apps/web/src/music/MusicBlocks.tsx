import React from 'react';
import type {MusicBlock,MusicDocument,PerformanceSettings} from '../../../../packages/music/src/model';
import './music.css';

function renderBlock(block:MusicBlock,mode:'play'|'print'):React.ReactNode {
  if(block.kind==='lyric') return <div className="lyric-line">{block.segments.map((segment,i)=>{
    if(!segment.chord) return <span className="lyric-fragment" key={i}>{segment.lyric}</span>;
    const match=segment.lyric.match(/^(\s*\S+)([\s\S]*)$/);
    const first=match?.[1] ?? segment.lyric, rest=match?.[2] ?? '';
    return <React.Fragment key={i}><span className={`segment${segment.lyric.trim() ? "" : " segment--empty"}`} data-chord={segment.chord}><span className="chord">{segment.chord}</span><span>{first || '\u00a0'}</span></span><span className="lyric-fragment">{rest}</span></React.Fragment>;
  })}</div>;
  if(block.kind==='tab') {
    if (mode==='play' || !block.groups.length) return <pre data-testid="tab" className="tab">{block.text}</pre>;
    const lines=[...block.text.matchAll(/[^\r\n]*(?:\r\n|\r|\n|$)/g)].map(match => match[0]).filter(Boolean);
    let cursor=0;
    const chunks=block.groups.map(group => {const chunk=lines.slice(cursor,group.endLine).join('');cursor=group.endLine;return chunk;});
    if (cursor<lines.length) chunks[chunks.length-1] += lines.slice(cursor).join('');
    return <>{chunks.map((chunk,index)=><pre data-testid="tab" className="tab tab--group" key={index}>{chunk}</pre>)}</>;
  }
  if(block.kind==='section' && block.action==='start') return <div className="section-label">{block.label || block.name}</div>;
  if(block.kind==='comment') return <p className="comment">{block.text}</p>;
  if(block.kind==='directive' && block.name==='title') return <h1>{block.value}</h1>;
  if(block.kind==='directive' && (block.name==='subtitle' || block.name==='artist')) return <p className="metadata">{block.value}</p>;
  if(block.kind==='directive' && block.name==='capo') return <p className="metadata">Capo {block.value}</p>;
  if(block.kind==='unsupported') return <p className="unsupported">{block.text}</p>;
  return null;
}
export function blockId(block:MusicBlock,index:number):string {return `${block.span.start}:${index}`;}
export function MusicBlocks({document,mode,measure=false,plan}:{document:MusicDocument;performance:PerformanceSettings;mode:'play'|'print';measure?:boolean;plan?:string[][]}) {
  const rendered = document.blocks.map((block,index) => ({id:blockId(block,index), block, node:renderBlock(block,mode)})).filter(item => item.node !== null);
  function element(item:typeof rendered[number]) {
    if (!measure) return <React.Fragment key={item.id}>{item.node}</React.Fragment>;
    const heading = item.block.kind === 'section' && item.block.action === 'start';
    return <div key={item.id} data-block-id={item.id} data-block-kind={heading ? 'heading' : item.block.kind === 'tab' ? 'tab' : item.block.kind === 'lyric' ? 'line' : 'other'} className={heading ? 'music-block music-block--heading' : 'music-block'}>{item.node}</div>;
  }
  const byId = new Map(rendered.map(item => [item.id,item]));
  return <article data-testid="song" className={`music music--${mode}${plan ? ' music--planned' : ''}`} style={plan ? {'--planned-columns':String(plan.length)} as React.CSSProperties : undefined}>
    {plan ? plan.map((column,index) => <div className="music-column" key={index}>{column.map(id => {const item=byId.get(id); return item ? element(item) : null;})}</div>) : rendered.map(element)}
  </article>;
}
