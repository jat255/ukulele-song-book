import type {ChordDefinition} from './model.js';

export type DiagramResult = {status:'known';frets:number[];fingers:number[]|null;pitches:number[];source:'builtin'|'custom'} | {status:'unknown';reason:string};
const shapes:Record<string,number[]> = {C:[0,0,0,3],G:[0,2,3,2],F:[2,0,1,0],Am:[2,0,0,0],A:[2,1,0,0],D:[2,2,2,0],Em:[0,4,3,2]};
const note:Record<string,number>={C:0,'B#':0,'C#':1,Db:1,D:2,'D#':3,Eb:3,E:4,Fb:4,F:5,'E#':5,'F#':6,Gb:6,G:7,'G#':8,Ab:8,A:9,'A#':10,Bb:10,B:11,Cb:11};
function required(chord:string):{classes:Set<number>;bass:number|null}|null {
  const match=chord.match(/^([A-G](?:#|b)?)(m|maj7|m7|7)?(?:\/([A-G](?:#|b)?))?$/);
  if (!match || note[match[1]] === undefined || (match[3] && note[match[3]] === undefined)) return null;
  const intervals=match[2] === 'm' ? [0,3,7] : match[2] === 'm7' ? [0,3,7,10] : match[2] === '7' ? [0,4,7,10] : match[2] === 'maj7' ? [0,4,7,11] : [0,4,7];
  return {classes:new Set(intervals.map(value => (note[match[1]]+value)%12)),bass:match[3] ? note[match[3]] : null};
}
export function resolveDiagram(chord:string, tuning:'high-g'|'low-g', definitions:ChordDefinition[]):DiagramResult {
  const expected=required(chord);
  if (!expected) return {status:'unknown',reason:'Chord quality or bass is not supported'};
  const definition=definitions.find(item => item.name === chord);
  let frets:number[]|undefined, fingers:number[]|null=null;
  if (definition) {
    if (/\bbase-fret\b/.test(definition.value)) return {status:'unknown',reason:'Base fret definitions need review'};
    const match=definition.value.match(/\bfrets\s+(.+?)(?=\s+fingers\b|$)/);
    const values=match?.[1].trim().split(/\s+/) ?? [];
    if (values.length !== 4 || values.some(value => !/^\d+$/.test(value) || Number(value)>24)) return {status:'unknown',reason:'Definition must have four valid frets'};
    frets=values.map(Number);
    const fingerMatch=definition.value.match(/\bfingers\s+(.+)$/);
    if (fingerMatch) {
      const values=fingerMatch[1].trim().split(/\s+/);
      if (values.length !== 4 || values.some(value => !/^[0-4]$/.test(value))) return {status:'unknown',reason:'Invalid fingering'};
      fingers=values.map(Number);
    }
  } else frets=shapes[chord];
  if (!frets) return {status:'unknown',reason:'No validated voicing is available'};
  const open=tuning==='high-g' ? [67,60,64,69] : [55,60,64,69];
  const pitches=frets.map((fret,index) => open[index]+fret);
  const actual=new Set(pitches.map(pitch=>pitch%12));
  if (actual.size !== expected.classes.size || [...actual].some(pitch=>!expected.classes.has(pitch)) || (expected.bass !== null && Math.min(...pitches)%12 !== expected.bass)) return {status:'unknown',reason:'Frets do not match chord pitches and bass'};
  return {status:'known',frets:[...frets],fingers,pitches,source:definition ? 'custom' : 'builtin'};
}
