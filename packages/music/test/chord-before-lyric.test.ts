import {describe, expect, it} from 'vitest';
import {applyChordEdit, getEditableLines} from '../src/chordEditing';

describe('placing a chord before lyrics', () => {
  it('adds leading space while preserving other chord anchors and lines', () => {
    const source="{title: Example}\n[Em]It's [G]bigger\n[C]Next\n";
    const line=getEditableLines(source)[0];
    expect(applyChordEdit(source,line.span,{kind:'move-before',id:0,spaces:3})).toBe("{title: Example}\n[Em]   It's [G]bigger\n[C]Next\n");
  });
  it('uses existing leading space without changing the lyrics or other chords', () => {
    const source=' [Em]  Hello [G]world';
    const line=getEditableLines(source)[0];
    expect(applyChordEdit(source,line.span,{kind:'move-before',id:0,spaces:2})).toBe(' [Em]  Hello [G]world');
    expect(applyChordEdit(source,line.span,{kind:'move-before',id:0,spaces:3})).toBe('[Em]   Hello [G]world');
  });
  it('rejects invalid distances and lines without lyrics', () => {
    const line=getEditableLines('[Em]Hello')[0];
    expect(()=>applyChordEdit('[Em]Hello',line.span,{kind:'move-before',id:0,spaces:0})).toThrow();
    const chordOnly=getEditableLines('[Em]')[0];
    expect(()=>applyChordEdit('[Em]',chordOnly.span,{kind:'move-before',id:0,spaces:2})).toThrow();
  });
});
