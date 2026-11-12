import {expect,test} from 'vitest';
import {resolveDiagram} from '../src/diagrams';
test('chromatic common qualities have validated shapes',()=>{
 for(const root of ['C','C#','Db','D','D#','Eb','E','F','F#','Gb','G','G#','Ab','A','A#','Bb','B'])
 for(const quality of ['','m','7','m7','maj7','dim','aug','sus2','sus4','6','m6'])
 expect(resolveDiagram(root+quality,'high-g',[]).status,root+quality).toBe('known');
});
test('slash chords include non-triad bass and enforce the lowest pitch',()=>{
 for(const [chord,classes,bass] of [['Am/D',[9,0,4,2],2],['C/D',[0,4,7,2],2],['G/B',[7,11,2],11]] as const){
  const shape=resolveDiagram(chord,'high-g',[]);expect(shape.status,chord).toBe('known');
  if(shape.status==='known'){expect(new Set(shape.pitches.map(p=>p%12))).toEqual(new Set(classes));expect(Math.min(...shape.pitches)%12).toBe(bass);}
 }
 expect(resolveDiagram('Am/D','high-g',[{name:'Am/D',value:'Am/D frets 2 0 0 0',span:{start:0,end:0}}]).status).toBe('unknown');
});
