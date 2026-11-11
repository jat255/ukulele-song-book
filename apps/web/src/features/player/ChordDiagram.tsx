import React from 'react';
import type {DiagramResult} from '../../../../../packages/music/src/diagrams';

export function ChordDiagram({chord,diagram}:{chord:string;diagram:DiagramResult}) {
  if (diagram.status === 'unknown') return <li><strong>{chord}</strong>: {diagram.reason}</li>;
  const positive=diagram.frets.filter(fret => fret > 0);
  const base=positive.length ? Math.max(1,Math.min(...positive)) : 1;
  const top=base > 1 ? base : 1;
  const count=Math.max(4,...positive.map(fret => fret-top+1));
  const height=30+count*18;
  return <li className="chord-diagram"><strong>{chord}</strong><svg role="img" aria-label={`${chord}, frets ${diagram.frets.join(', ')}`} width="100" height={height} viewBox={`0 0 100 ${height}`}>
    {top > 1 && <text x="1" y="32" fontSize="10">{top}fr</text>}
    {[0,1,2,3].map(string => <line key={`s${string}`} x1={25+string*17} x2={25+string*17} y1="20" y2={20+count*18} stroke="currentColor" />)}
    {Array.from({length:count+1},(_,fret) => <line key={`f${fret}`} x1="25" x2="76" y1={20+fret*18} y2={20+fret*18} stroke="currentColor" />)}
    {diagram.frets.map((fret,string) => fret === 0 ? <circle key={string} cx={25+string*17} cy="10" r="4" fill="none" stroke="currentColor" /> : <circle key={string} cx={25+string*17} cy={29+(fret-top)*18} r="5" fill="currentColor" />)}
  </svg></li>;
}
