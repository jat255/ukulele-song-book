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
