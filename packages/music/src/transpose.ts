import type {Diagnostic, MusicDocument, PerformanceSettings} from './model.js';
import {applySourceEdits} from './source.js';

const sharp=['C','C#','D','D#','E','F','F#','G','G#','A','A#','B'];
const flat=['C','Db','D','Eb','E','F','Gb','G','Ab','A','Bb','B'];
const pitches:Record<string,number> = {C:0,'B#':0,'C#':1,Db:1,D:2,'D#':3,Eb:3,E:4,Fb:4,'E#':5,F:5,'F#':6,Gb:6,G:7,'G#':8,Ab:8,A:9,'A#':10,Bb:10,B:11,Cb:11};
type Spelling = 'auto'|'sharps'|'flats';
const warning=(code:string,message:string):Diagnostic => ({code,severity:'warning',message});
function prefersFlats(key?:string):boolean {
  if (!key) return false;
  return /b/.test(key) || /^(F|Dm|Gm|Cm|Fm)$/.test(key);
}
function shift(note:string, amount:number, flats:boolean):string {
  const pitch=pitches[note]; return (flats ? flat : sharp)[((pitch + amount) % 12 + 12) % 12];
}
export function transposeChord(token:string, semitones:number, spelling:Spelling, key?:string):{token:string;diagnostic?:Diagnostic} {
  if (/^(?:N\.?C\.?|x)$/i.test(token)) return {token};
  const match=token.match(/^([A-G](?:#|b)?)([^/]*)(?:\/([A-G](?:#|b)?))?$/);
  if (!match || pitches[match[1]] === undefined || (match[3] && pitches[match[3]] === undefined) || !/^(?:(?:maj|min|dim|aug|sus|add|omit|no|m|M|°|ø)|[0-9+#b()\-])*$/.test(match[2]) || !Number.isInteger(semitones)) return {token,diagnostic:warning('unknown-chord',`Cannot transpose chord: ${token}`)};
  const useFlat=spelling === 'flats' || (spelling === 'auto' && (key ? prefersFlats(key) : match[1].includes('b')));
  return {token:shift(match[1],semitones,useFlat)+match[2]+(match[3] ? '/'+shift(match[3],semitones,useFlat) : '')};
}
export type KeyScope = {sourceKey:string|null;displayKey:string|null;soundingKey:string|null};
export type PerformanceDocument = MusicDocument & {scopes:KeyScope[]};
export function derivePerformance(document:MusicDocument, settings:PerformanceSettings):PerformanceDocument {
  let key:string|undefined, sourceOffset=0, sourceSpelling:Spelling='auto';
  const transposeStack:{offset:number;spelling:Spelling}[]=[];
  const currentSpelling=():Spelling => settings.spelling === 'auto' && sourceSpelling !== 'auto' ? sourceSpelling : settings.spelling;
  const diagnostics=[...document.diagnostics]; const scopes:KeyScope[]=[];
  function recordScope() {
    if (!key) {scopes.push({sourceKey:null,displayKey:null,soundingKey:null}); return;}
    const display=transposeChord(key,sourceOffset+settings.semitones,currentSpelling(),key);
    const sounding=transposeChord(key,sourceOffset+settings.semitones+settings.capo,currentSpelling(),key);
    if (display.diagnostic || sounding.diagnostic) {diagnostics.push(warning('unknown-key','Key could not be resolved')); scopes.push({sourceKey:key,displayKey:null,soundingKey:null});}
    else scopes.push({sourceKey:key,displayKey:display.token,soundingKey:sounding.token});
  }
  const blocks=document.blocks.map(block => {
    if (block.kind==='directive' && block.name==='key') {
      key=block.value;
      recordScope();
      return {...block};
    }
    if (block.kind==='directive' && block.name==='transpose') {
      const value=block.value.trim();
      if (value === '') {const previous=transposeStack.pop(); sourceOffset=previous?.offset ?? 0; sourceSpelling=previous?.spelling ?? 'auto';}
      else {
        const match=value.match(/^([+-]?\d+)([sfk])?$/i);
        if (match) {transposeStack.push({offset:sourceOffset,spelling:sourceSpelling}); sourceOffset=Number(match[1]); sourceSpelling=match[2]?.toLowerCase() === 's' ? 'sharps' : match[2]?.toLowerCase() === 'f' ? 'flats' : 'auto';}
        else diagnostics.push(warning('unknown-transpose','Unsupported source transpose directive'));
      }
      recordScope();
      return {...block};
    }
    if (block.kind==='tab' && (sourceOffset+settings.semitones)!==0) diagnostics.push(warning('tab-not-transposed','Tab remains in its original tuning and pitch'));
    if (block.kind!=='lyric') return {...block};
    return {...block,segments:block.segments.map(segment => {
      if (!segment.chord) return {...segment};
      const result=transposeChord(segment.chord,sourceOffset+settings.semitones,currentSpelling(),key);
      if(result.diagnostic) diagnostics.push(result.diagnostic);
      return {...segment,chord:result.token};
    })};
  });
  if (!scopes.length) scopes.push({sourceKey:null,displayKey:null,soundingKey:null});
  return {...document,blocks,diagnostics,scopes};
}
export function serializePerformanceArrangement(document:MusicDocument, settings:PerformanceSettings):{source:string;diagnostics:Diagnostic[]} {
  if (document.blocks.some(block=>block.kind==='directive' && block.name==='transpose' && block.value.trim() !== '' && block.value.trim() !== '0')) return {source:document.source,diagnostics:[warning('unsafe-serialization','Scoped transpose must be resolved manually before saving a variant')]};
  if (document.definitions.length && settings.semitones !== 0) return {source:document.source,diagnostics:[warning('unsafe-serialization','Custom chord definitions require manual review before transposition')]};
  const derived=derivePerformance(document,settings);
  const edits:{span:{start:number;end:number};text:string}[]=[];
  for (let i=0;i<document.blocks.length;i++) {
    const original=document.blocks[i], transformed=derived.blocks[i];
    if (original.kind==='lyric' && transformed.kind==='lyric') original.segments.forEach((segment,index) => {
      if (segment.chord) edits.push({span:{start:segment.span.start,end:segment.span.start+segment.chord.length+2},text:`[${transformed.segments[index].chord}]`});
    });
    if (original.kind==='directive' && (original.name==='key' || original.name==='capo')) {
      const raw=document.source.slice(original.span.start,original.span.end);
      const value=original.name==='key' ? transposeChord(original.value,settings.semitones,settings.spelling,original.value).token : String(settings.capo);
      const changed=raw.replace(/^(\s*\{\s*[\w-]+\s*:\s*)([^}]*?)(\s*\})/,(_,prefix,_old,suffix)=>prefix+value+suffix);
      edits.push({span:original.span,text:changed});
    }
  }
  let source=applySourceEdits(document.source,edits);
  if (settings.capo !== 0 && !document.blocks.some(block => block.kind === 'directive' && block.name === 'capo')) source=`{capo: ${settings.capo}}${source.includes('\r\n') ? '\r\n' : '\n'}` + source;
  return {source,diagnostics:derived.diagnostics};
}
