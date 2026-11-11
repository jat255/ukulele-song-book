export type BlockMeasurement = {id:string; height:number; kind:'line'|'heading'|'tab'|'other'};
export type ColumnPlan = string[][];

export function chooseScreenColumns(input:{widthPx:number; fontPx:number; preference:'auto'|1|2|3; minContentWidthPx:number}): number {
  const gap = 46;
  const minimum = Math.max(input.minContentWidthPx, input.fontPx * 14);
  const fitting = Math.max(1, Math.min(3, Math.floor((input.widthPx + gap) / (minimum + gap))));
  return input.preference === 'auto' ? fitting : Math.min(input.preference, fitting);
}

export function layoutSections(blocks:BlockMeasurement[], columns:number, targetHeightPx:number):ColumnPlan {
  const result:ColumnPlan = Array.from({length:Math.max(1, Math.floor(columns))}, () => []);
  let column=0, used=0;
  for (let index=0; index<blocks.length; index++) {
    const block=blocks[index];
    const nextHeight=block.kind==='heading' && index+1<blocks.length ? blocks[index+1].height : 0;
    if (column < result.length-1 && used > 0 && used + block.height + nextHeight > targetHeightPx) {column++; used=0;}
    result[column].push(block.id); used += block.height;
  }
  return result;
}
