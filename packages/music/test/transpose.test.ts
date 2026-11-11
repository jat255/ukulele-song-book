import {describe,expect,it} from 'vitest';
import {parseSource} from '../src/parser.js';
import {derivePerformance,serializePerformanceArrangement,transposeChord} from '../src/transpose.js';

describe('performance transposition', () => {
  it('transposes roots and slash bass while preserving quality', () => {
    expect(transposeChord('D/F#',2,'sharps').token).toBe('E/G#');
    expect(transposeChord('Bbmaj7/D',2,'flats').token).toBe('Cmaj7/E');
    expect(transposeChord('F#m7b5',-1,'sharps').token).toBe('Fm7b5');
    expect(transposeChord('N.C.',5,'auto').token).toBe('N.C.');
    expect(transposeChord('not-a-chord',2,'auto').diagnostic?.severity).toBe('warning');
  });
  it('handles all pitch classes and negative offsets', () => {
    const notes=['C','C#','D','D#','E','F','F#','G','G#','A','A#','B'];
    for (let i=0;i<12;i++) expect(transposeChord(notes[i],-1,'sharps').token).toBe(notes[(i+11)%12]);
    expect(transposeChord('Bb',2,'flats').token).toBe('C');
  });
  it('leaves source and tabs unchanged and reports sounding keys', () => {
    const source='{key: C}\n{capo: 2}\n[C]Hi\n{start_of_tab}\nA|--0--|\nE|-----|\nC|-----|\nG|-----|\n{end_of_tab}\n{future: retain}';
    const doc=parseSource(source), before=JSON.stringify(doc);
    const result=derivePerformance(doc,{semitones:0,spelling:'sharps',capo:2,tuning:'high-g'});
    expect(result.scopes[0]).toMatchObject({sourceKey:'C',displayKey:'C',soundingKey:'D'});
    const changed=derivePerformance(doc,{semitones:2,spelling:'sharps',capo:3,tuning:'high-g'});
    expect(changed.blocks.find(block => block.kind==='lyric')).toMatchObject({segments:[{chord:'D'}]});
    expect(changed.blocks.find(block => block.kind==='tab')).toEqual(doc.blocks.find(block => block.kind==='tab'));
    expect(changed.diagnostics.some(item=>item.code==='tab-not-transposed')).toBe(true);
    expect(JSON.stringify(doc)).toBe(before);
  });
  it('serializes explicit variants without dropping unknown directives', () => {
    const doc=parseSource('{title: Test}\n[C]Hello\n{future: preserve}\n');
    const result=serializePerformanceArrangement(doc,{semitones:2,spelling:'sharps',capo:0,tuning:'high-g'});
    expect(result.source).toContain('[D]Hello');
    expect(result.source).toContain('{future: preserve}');
  });
});

describe('source transpose scopes', () => {
  it('applies source directives once and updates key scopes', () => {
    const doc=parseSource('{key: Am}\n{transpose: 2}\n[Am]First\n{transpose: -1}\n[Am]Second\n{transpose}\n[Am]Third');
    const result=derivePerformance(doc,{semitones:1,spelling:'sharps',capo:0,tuning:'high-g'});
    const chords=result.blocks.filter(block => block.kind==='lyric').map(block => block.kind==='lyric' ? block.segments[0].chord : '');
    expect(chords).toEqual(['Cm','Am','Cm']);
    expect(result.scopes.map(scope => scope.displayKey)).toEqual(['A#m','Cm','Am','Cm']);
  });
});

describe('saving performance variants', () => {
  it('adds the requested capo when the source has none', () => {
    const doc=parseSource('{title: Test}\n[C]Hello\n');
    const result=serializePerformanceArrangement(doc,{semitones:0,spelling:'auto',capo:3,tuning:'high-g'});
    expect(result.source).toContain('{capo: 3}');
    expect(result.source).toContain('[C]Hello');
  });
  it('declines serialization when scoped transpose cannot be safely rewritten', () => {
    const source='{transpose: 2}\n[C]Hello\n{transpose}\n';
    const result=serializePerformanceArrangement(parseSource(source),{semitones:2,spelling:'auto',capo:0,tuning:'high-g'});
    expect(result.source).toBe(source);
    expect(result.diagnostics.some(item=>item.code==='unsafe-serialization')).toBe(true);
  });
});
