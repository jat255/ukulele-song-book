import React from 'react';
import type {MusicDocument,PerformanceSettings} from '../../../../packages/music/src/model';
import './music.css';
export function MusicBlocks({document,mode}:{document:MusicDocument;performance:PerformanceSettings;mode:'play'|'print'}) {
  return <article data-testid="song" className={`music music--${mode}`}>
    {document.blocks.map((block,index) => {
      if(block.kind==='lyric') return <div className="lyric-line" key={index}>{block.segments.map((segment,i)=>{
        if(!segment.chord) return <span className="lyric-fragment" key={i}>{segment.lyric}</span>;
        const match=segment.lyric.match(/^(\s*\S+)([\s\S]*)$/);
        const first=match?.[1] ?? segment.lyric, rest=match?.[2] ?? '';
        return <React.Fragment key={i}><span className={`segment${segment.lyric.trim() ? "" : " segment--empty"}`} data-chord={segment.chord}><span className="chord">{segment.chord}</span><span>{first || '\u00a0'}</span></span><span className="lyric-fragment">{rest}</span></React.Fragment>;
      })}</div>;
      if(block.kind==='tab') return <pre data-testid="tab" className="tab" key={index}>{block.text}</pre>;
      if(block.kind==='section' && block.action==='start') return <div className="section-label" key={index}>{block.label || block.name}</div>;
      if(block.kind==='comment') return <p className="comment" key={index}>{block.text}</p>;
      if(block.kind==='directive' && block.name==='title') return <h1 key={index}>{block.value}</h1>;
      if(block.kind==='directive' && block.name==='subtitle') return <p className="metadata" key={index}>{block.value}</p>;
      if(block.kind==='directive' && block.name==='artist') return <p className="metadata" key={index}>{block.value}</p>;
      if(block.kind==='directive' && block.name==='capo') return <p className="metadata" key={index}>Capo {block.value}</p>;
      if(block.kind==='unsupported') return <p className="unsupported" key={index}>{block.text}</p>;
      return null;
    })}
  </article>;
}
