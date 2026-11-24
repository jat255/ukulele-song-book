import {describe, expect, it} from 'vitest';
import {chooseScreenColumns, layoutSections} from './layout';

describe('responsive song layout', () => {
  it('reduces requested columns when readable width cannot fit', () => {
    expect(chooseScreenColumns({widthPx:320,fontPx:28,preference:3,minContentWidthPx:260})).toBe(1);
    expect(chooseScreenColumns({widthPx:1440,fontPx:20,preference:'auto',minContentWidthPx:360})).toBe(3);
  });
  it('keeps headings with the next line and reads down then across', () => {
    const plan = layoutSections([
      {id:'a',height:80,kind:'line'}, {id:'heading',height:25,kind:'heading'},
      {id:'b',height:50,kind:'line'}, {id:'c',height:50,kind:'line'},
      {id:'tab',height:180,kind:'tab'},
    ], 3, 120);
    expect(plan.flat()).toEqual(['a','heading','b','c','tab']);
    expect(plan[0]).toEqual(['a']);
    expect(plan[1]).toEqual(['heading','b']);
    expect(plan[2]).toEqual(['c','tab']);
  });
});

it('prefers a section boundary near the balanced column break', () => {
  const blocks = Array.from({length:10}, (_,index) => ({
    id:String(index), height:20, kind:index===6 ? 'heading' as const : 'line' as const,
  }));
  expect(layoutSections(blocks,2,100).map(column=>column.length)).toEqual([6,4]);
});
