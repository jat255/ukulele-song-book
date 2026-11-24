import type {MusicDocument} from '../../../../packages/music/src/model';

export type SectionRepeats = ReadonlyMap<number, {end:number; label:string}>;

/** Fold complete, flat sections only when their source and sounding content match. */
export function repeatSections(document: MusicDocument): SectionRepeats {
  const seen = new Set<string>();
  const repeats = new Map<number, {end:number; label:string}>();
  const {blocks,source} = document;
  let start = -1;
  let depth = 0;
  let nested = false;

  for (const [index, block] of blocks.entries()) {
    if (block.kind !== 'section') continue;
    if (block.action === 'start') {
      if (depth === 0) {
        start = index;
        nested = false;
      } else {
        nested = true;
      }
      depth++;
      continue;
    }
    if (depth === 0 || --depth > 0 || nested) continue;

    const heading = blocks[start];
    if (heading.kind !== 'section' || heading.name !== block.name) continue;
    const body = blocks.slice(start + 1,index);
    if (!body.length || body.some(item => item.kind === 'directive' || item.kind === 'unsupported')) continue;
    const key = JSON.stringify(
      [source.slice(heading.span.start, block.span.end).trimEnd(), body],
      (name, value) => name === 'span' || name === 'contentSpan' ? undefined : value,
    );
    if (seen.has(key)) repeats.set(start,{end:index,label:heading.label || heading.name});
    else seen.add(key);
  }
  return repeats;
}
