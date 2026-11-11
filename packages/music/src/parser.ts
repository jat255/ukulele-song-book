import type {MusicDocument, Segment} from './model.js';

const aliases: Record<string,string> = {sov:'start_of_verse',eov:'end_of_verse',soc:'start_of_chorus',eoc:'end_of_chorus',sot:'start_of_tab',eot:'end_of_tab',sog:'start_of_grid',eog:'end_of_grid',t:'title',st:'subtitle',c:'comment'};
const metadata = new Set(['title','subtitle','artist','composer','lyricist','album','year','copyright','duration']);
const directives = new Set(['key','capo','transpose',...metadata]);
function tabGroups(text: string): {startLine: number; endLine: number}[] {
  const lines = text.split(/\r\n|\r|\n/), groups: {startLine: number; endLine: number}[] = [];
  let start = -1;
  for (let i=0;i<=lines.length;i++) {
    const stringLine = i<lines.length && /^\s*[A-Ga-g](?:#|b)?\s*\|/.test(lines[i]);
    if (stringLine && start<0) start=i;
    if (!stringLine && start>=0) { if (i-start===4 || i-start===6) groups.push({startLine:start,endLine:i}); start=-1; }
  }
  return groups;
}
export function parseSource(source: string): MusicDocument {
  const doc: MusicDocument = {schemaVersion:1,source,metadata:{},blocks:[],definitions:[],diagnostics:[]};
  const lines = [...source.matchAll(/[^\r\n]*(?:\r\n|\r|\n|$)/g)].filter(m => m[0].length);
  let tab: {start:number; contentStart:number; label?:string}|undefined;
  const sections: string[] = [];
  let unsupportedEnv: {name:string;start:number}|undefined;
  for (let i=0;i<lines.length;i++) {
    const raw=lines[i][0], start=lines[i].index!, end=start+raw.length, content=raw.replace(/\r\n$|[\r\n]$/,'');
    const match=content.match(/^\s*\{\s*([\w-]+)(?:\s*:\s*([^}]*?)|\s+([^}]*?))?\s*\}\s*$/);
    const name=match ? (aliases[match[1].toLowerCase()] ?? match[1].toLowerCase()) : '';
    const value=match ? (match[2] ?? match[3] ?? '').trim() : '';
    if (tab) {
      if (name==='end_of_tab') { doc.blocks.push({kind:'tab',text:source.slice(tab.contentStart,start),groups:tabGroups(source.slice(tab.contentStart,start)),label:tab.label,span:{start:tab.start,end}}); tab=undefined; }
      continue;
    }
    if (unsupportedEnv) {
      if (name===`end_of_${unsupportedEnv.name}`) {doc.blocks.push({kind:'unsupported',text:source.slice(unsupportedEnv.start,end),span:{start:unsupportedEnv.start,end}}); unsupportedEnv=undefined;}
      continue;
    }
    if (name==='start_of_grid' || name==='start_of_abc' || name==='start_of_ly') {
      unsupportedEnv={name:name.slice(9),start}; doc.diagnostics.push({code:'unsupported-environment',severity:'warning',message:`Unsupported environment: ${name}`,line:i+1}); continue;
    }
    if (!match && content.trimStart().startsWith('{')) { doc.blocks.push({kind:'unsupported',text:content,span:{start,end}}); doc.diagnostics.push({code:'malformed-directive',severity:'warning',message:'Malformed directive',line:i+1}); continue; }
    if (name==='start_of_tab') { tab={start,contentStart:end,label:value || undefined}; continue; }
    if (name.startsWith('start_of_') || name.startsWith('end_of_')) {
      const action=name.startsWith('start_of_') ? 'start' : 'end'; const section=name.slice(action==='start'?9:7);
      if (action==='start') sections.push(section); else if (sections.pop()!==section) doc.diagnostics.push({code:'unmatched-section',severity:'warning',message:'Unmatched section boundary',line:i+1});
      doc.blocks.push({kind:'section',name:section,action,label:(value.match(/^label="([^"]*)"$/)?.[1] ?? value) || undefined,span:{start,end}}); continue;
    }
    if (match) {
      if (name==='comment') doc.blocks.push({kind:'comment',text:value,span:{start,end}});
      else if (name==='define') { const chord=value.split(/\s+/)[0]; doc.definitions.push({name:chord,value,span:{start,end}}); doc.diagnostics.push({code:'unvalidated-definition',severity:'warning',message:'Chord definition retained without shape validation',line:i+1}); doc.blocks.push({kind:'directive',name,value,span:{start,end}}); }
      else if (directives.has(name)) { if (metadata.has(name)) (doc.metadata[name] ??= []).push(value); doc.blocks.push({kind:'directive',name,value,span:{start,end}}); }
      else { doc.blocks.push({kind:'unsupported',text:content,span:{start,end}}); doc.diagnostics.push({code:'unsupported-directive',severity:'warning',message:`Unsupported directive: ${name}`,line:i+1}); }
      continue;
    }
    const segments: Segment[]=[]; const chords=[...content.matchAll(/\[([^\]]+)\]/g)];
    if (!chords.length) segments.push({lyric:content,span:{start,end:start+content.length}});
    else {
      if (chords[0].index!>0) segments.push({lyric:content.slice(0,chords[0].index),span:{start,end:start+chords[0].index!}});
      chords.forEach((chord,j) => { const from=chord.index!+chord[0].length, to=chords[j+1]?.index ?? content.length; segments.push({chord:chord[1],lyric:content.slice(from,to),span:{start:start+chord.index!,end:start+to}}); });
    }
    doc.blocks.push({kind:'lyric',segments,span:{start,end}});
  }
  if (unsupportedEnv) doc.blocks.push({kind:'unsupported',text:source.slice(unsupportedEnv.start),span:{start:unsupportedEnv.start,end:source.length}});
  if (tab) {doc.blocks.push({kind:'tab',text:source.slice(tab.contentStart),groups:tabGroups(source.slice(tab.contentStart)),label:tab.label,span:{start:tab.start,end:source.length}}); doc.diagnostics.push({code:'unmatched-tab',severity:'warning',message:'Unclosed tab section'});}
  if (sections.length) doc.diagnostics.push({code:'unmatched-section',severity:'warning',message:'Unclosed section'});
  return doc;
}
export function exportSource(document: MusicDocument): string { return document.source; }
