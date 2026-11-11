import React from 'react';
import {parseSource} from '../../../../packages/music/src/parser';
import {derivePerformance} from '../../../../packages/music/src/transpose';
import {resolveDiagram} from '../../../../packages/music/src/diagrams';
import type {PerformanceSettings,PrintSettings} from '../../../../packages/music/src/model';
import {MusicBlocks} from '../music/MusicBlocks';
import {ChordDiagram} from '../features/player/ChordDiagram';

export function PrintDocument({source,performance,settings}:{source:string;performance:PerformanceSettings;settings:PrintSettings}) {
  const original=parseSource(source), doc=derivePerformance(original,performance);
  const style={'--music-size':`${settings.fontPt}pt`,'--music-columns':String(settings.columns === 'auto' ? 1 : settings.columns)} as React.CSSProperties;
  const chords=[...new Set(doc.blocks.flatMap(block => block.kind==='lyric' ? block.segments.flatMap(segment => segment.chord ? [segment.chord] : []) : []))];
  const scope=doc.scopes[0];
  return <div className="browser-print" style={style} data-print-density={settings.density}><style>{`@page {size:${settings.paper};margin:${settings.marginsMm}mm}`}</style>{(scope?.sourceKey || performance.capo !== 0) && <p className="print-keys">Source key: {scope?.sourceKey ?? 'unknown'}; shape key: {scope?.displayKey ?? 'unknown'}; sounding key: {scope?.soundingKey ?? 'unknown'}; capo: {performance.capo}</p>}<MusicBlocks document={doc} performance={performance} mode="print"/>{settings.diagrams && <ul className="print-diagrams">{chords.map(chord => <ChordDiagram key={chord} chord={chord} diagram={resolveDiagram(chord,performance.tuning,original.definitions)}/>)}</ul>}</div>;
}
