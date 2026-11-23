import {describe,expect,it} from 'vitest';
import {resolveDiagram} from '../src/diagrams.js';

describe('ukulele diagrams', () => {
  it('validates authored GCEA shapes and tuning distinction', () => {
    const high=resolveDiagram('C','high-g',[]), low=resolveDiagram('C','low-g',[]);
    expect(high.status).toBe('known');
    if (high.status === 'known' && low.status === 'known') {
      expect(high.frets).toEqual([0,0,0,3]);
      expect(high.pitches[0]-low.pitches[0]).toBe(12);
    }
    expect(resolveDiagram('C13','high-g',[]).status).toBe('unknown');
  });
  it('rejects invalid custom definitions and six string guitar shapes', () => {
    expect(resolveDiagram('C','high-g',[{name:'C',value:'C frets 0 0 0 3',span:{start:0,end:0}}]).status).toBe('known');
    expect(resolveDiagram('C','high-g',[{name:'C',value:'C frets 3 2 0 0 1 0',span:{start:0,end:0}}]).status).toBe('unknown');
    expect(resolveDiagram('C','high-g',[{name:'C',value:'C frets 0 0 0 2',span:{start:0,end:0}}]).status).toBe('unknown');
  });
});

describe('UkeBuddy chart coverage', () => {
  it('provides correctly voiced chart chords in both GCEA tunings', () => {
    const roots = ['C','C#','D','Eb','E','F','F#','G','Ab','A','Bb','B'];
    const qualities: Record<string, number[]> = {
      '':[0,4,7], m:[0,3,7], '7':[0,4,7,10], m7:[0,3,7,10],
      maj7:[0,4,7,11], '6':[0,4,7,9], '9':[0,4,10,2],
      add9:[0,4,7,2], sus2:[0,2,7], sus4:[0,5,7], dim:[0,3,6], aug:[0,4,8],
    };
    for (const [rootIndex, root] of roots.entries()) for (const [quality, intervals] of Object.entries(qualities)) {
      for (const tuning of ['high-g','low-g'] as const) {
        const result = resolveDiagram(root + quality, tuning, []);
        expect(result.status, `${root + quality} ${tuning}`).toBe('known');
        if (result.status === 'known') {
          expect([...new Set(result.pitches.map(p => (p-rootIndex+12)%12))].sort((a,b)=>a-b)).toEqual([...intervals].sort((a,b)=>a-b));
        }
      }
    }
  });
});

describe('requested chord diagrams', () => {
  it('resolves Cadd9 and G/F# with the correct notes and bass in both tunings', () => {
    for (const tuning of ['high-g', 'low-g'] as const) {
      const add9 = resolveDiagram('Cadd9', tuning, []);
      expect(add9.status).toBe('known');
      if (add9.status === 'known') expect([...new Set(add9.pitches.map(p => p % 12))].sort((a,b) => a-b)).toEqual([0,2,4,7]);
      const slash = resolveDiagram('G/F#', tuning, []);
      expect(slash.status).toBe('known');
      if (slash.status === 'known') {
        expect([...new Set(slash.pitches.map(p => p % 12))].sort((a,b) => a-b)).toEqual([2,6,7,11]);
        expect(Math.min(...slash.pitches) % 12).toBe(6);
      }
    }
  });
});

it('resolves parenthesized chords using the same shape and custom definitions', () => {
  expect(resolveDiagram('(F#)','high-g',[])).toEqual(resolveDiagram('F#','high-g',[]));
  const definitions=[{name:'C',value:'C frets 0 0 0 3',span:{start:0,end:0}}];
  expect(resolveDiagram('(C)','high-g',definitions)).toEqual(resolveDiagram('C','high-g',definitions));
  expect(resolveDiagram('(unknown)','high-g',[]).status).toBe('unknown');
});
