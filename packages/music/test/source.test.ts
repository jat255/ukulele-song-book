import { it, expect } from 'vitest';
import { applySourceEdits } from '../src/source';
it('applies UTF-16 offsets without corrupting Unicode', () => {
  expect(applySourceEdits('🌻abc', [{span:{start:2,end:3},text:'A'}])).toBe('🌻Abc');
});
it('rejects overlapping edits', () => {
  expect(() => applySourceEdits('abcd', [{span:{start:0,end:2},text:''},{span:{start:1,end:3},text:''}])).toThrow();
});
