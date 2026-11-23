import { describe, it, expect } from 'vitest';
import { parseSource, exportSource } from '../src/parser';

describe('source preservation', () => {
  it('preserves unknown directives, Unicode, and CRLF', () => {
    const source = '{title: 🌻}\r\n{future: yes}\r\n[C]Hello\r\n';
    expect(exportSource(parseSource(source))).toBe(source);
    expect(parseSource(source).diagnostics.length).toBeGreaterThan(0);
  });
  it('parses anchored chords', () => {
    expect(parseSource('[C]Lan[D/F#]tern').blocks[0]).toMatchObject({kind:'lyric',segments:[{chord:'C',lyric:'Lan'},{chord:'D/F#',lyric:'tern'}]});
  });
  it('keeps directives and chords literal inside tab', () => {
    expect(parseSource('{start_of_tab}\nA|--[C]--  |\n{key: Z}\n{end_of_tab}').blocks[0]).toMatchObject({kind:'tab',text:'A|--[C]--  |\n{key: Z}\n'});
  });
});

it('retains ordered scoped directives and repeated metadata', () => {
  const doc = parseSource('{title: First}\n{title: Second}\n{key: G}\n{capo: 2}\n{transpose: -2}\n{transpose: 0}\n');
  expect(doc.metadata.title).toEqual(['First','Second']);
  expect(doc.blocks.slice(2).map(b => b.kind === 'directive' && [b.name,b.value])).toEqual([['key','G'],['capo','2'],['transpose','-2'],['transpose','0']]);
});
it('handles section aliases and adjacent chords', () => {
  const doc = parseSource('{sov: Verse}\n[C][G]word\n{eov}\n');
  expect(doc.blocks[0]).toMatchObject({kind:'section',action:'start',name:'verse'});
  expect(doc.blocks[1]).toMatchObject({kind:'lyric',segments:[{chord:'C',lyric:''},{chord:'G',lyric:'word'}]});
  expect(doc.diagnostics).toEqual([]);
});
it('warns about unmatched sections and tab', () => {
  expect(parseSource('{sov}\nHi').diagnostics.map(d => d.code)).toContain('unmatched-section');
  expect(parseSource('{sot}\nA|---').diagnostics.map(d => d.code)).toContain('unmatched-tab');
});
it('preserves labels, definitions, comments and chord-only lines', () => {
  const doc = parseSource('{soc: label="Refrain"}\n{define: C base-fret 1 frets 0 0 0 3}\n{comment: softly}\n[C][G]\n{eoc}\n');
  expect(doc.blocks[0]).toMatchObject({kind:'section',name:'chorus',label:'Refrain'});
  expect(doc.definitions[0]).toMatchObject({name:'C'});
  expect(doc.blocks[2]).toMatchObject({kind:'comment',text:'softly'});
  expect(doc.blocks[3]).toMatchObject({kind:'lyric',segments:[{chord:'C',lyric:''},{chord:'G',lyric:''}]});
});
it('warns on malformed directives rather than silently interpreting them as lyrics', () => {
  const doc = parseSource('{include: ../../secret}\n{incomplete\n');
  expect(doc.blocks.every(b => b.kind === 'unsupported')).toBe(true);
  expect(doc.diagnostics).toHaveLength(2);
});
it('marks complete four and six string tab groups without modifying literal text', () => {
  const doc = parseSource('{sot}\nA|--0--|\nE|--0--|\nC|--0--|\nG|--0--|\n\ne|--0--|\nB|--0--|\nG|--0--|\nD|--0--|\nA|--0--|\nE|--0--|\n{eot}');
  expect(doc.blocks[0]).toMatchObject({kind:'tab',groups:[{startLine:0,endLine:4},{startLine:5,endLine:11}]});
});
it('retains four and six string custom definitions', () => {
  const doc = parseSource('{define: C base-fret 1 frets 0 0 0 3}\n{define: D base-fret 1 frets x x 0 2 3 2}\n');
  expect(doc.definitions).toHaveLength(2);
  expect(doc.definitions[0].value).toContain('0 0 0 3');
  expect(doc.definitions[1].value).toContain('x x 0 2 3 2');
});
it('reports unvalidated chord definitions as preserved-only', () => {
  expect(parseSource('{define: C base-fret 1 frets 0 0 0 3}').diagnostics.map(d => d.code)).toContain('unvalidated-definition');
});
it('parses grids as musical blocks and retains their source', () => {
  const doc = parseSource('{start_of_grid}\n| C . G . |\n{end_of_grid}\n');
  expect(doc.diagnostics).toEqual([]);
  expect(doc.blocks[0]).toMatchObject({kind:'grid',text:'| C . G . |\n'});
});
it('keeps grid markers literal inside tablature', () => {
  expect(parseSource('{sot}\n{start_of_grid}\nA|---|\n{eot}').blocks[0]).toMatchObject({kind:'tab',text:'{start_of_grid}\nA|---|\n'});
});
