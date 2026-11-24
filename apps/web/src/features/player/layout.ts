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
  let start=0;
  for (let column=0; column<result.length-1 && start<blocks.length; column++) {
    let used=0;
    let end=start;
    let boundary=-1;
    let distance=targetHeightPx*.25;
    let fallback=-1;
    for (; end<blocks.length && used<=targetHeightPx*1.25; end++) {
      const block=blocks[end];
      const nextHeight=block.kind==='heading' ? blocks[end+1]?.height ?? 0 : 0;
      if (end>start && block.kind==='heading' && Math.abs(used-targetHeightPx)<=distance) {
        boundary=end;
        distance=Math.abs(used-targetHeightPx);
      }
      if (end>start && fallback<0 && used+block.height+nextHeight>targetHeightPx) fallback=end;
      used+=block.height;
    }
    const cut=boundary>start ? boundary : fallback>start ? fallback : end;
    result[column]=blocks.slice(start,cut).map(block=>block.id);
    start=cut;
  }
  result[result.length-1]=blocks.slice(start).map(block=>block.id);
  return result;
}
