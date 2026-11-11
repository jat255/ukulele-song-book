import type {SourceSpan} from './model.js';
export function applySourceEdits(source: string, edits: {span: SourceSpan; text: string}[]): string {
  const ordered = [...edits].sort((a,b) => b.span.start-a.span.start || b.span.end-a.span.end);
  let boundary = source.length;
  for (const {span,text} of ordered) {
    if (!Number.isInteger(span.start) || !Number.isInteger(span.end) || span.start < 0 || span.end < span.start || span.end > boundary) throw new Error('Invalid or overlapping source edits');
    source = source.slice(0,span.start)+text+source.slice(span.end);
    boundary = span.start;
  }
  return source;
}
