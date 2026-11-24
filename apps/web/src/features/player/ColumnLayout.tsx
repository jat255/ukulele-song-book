import {useLayoutEffect, useMemo, useRef, useState} from 'react';
import type {MusicDocument, PerformanceSettings} from '../../../../../packages/music/src/model';
import type {SectionRepeats} from '../../music/repeatSections';
import {MusicBlocks} from '../../music/MusicBlocks';
import {layoutSections, type BlockMeasurement, type ColumnPlan} from './layout';

export function ColumnLayout({document,performance,columns,width,font,density,repeats}:{document:MusicDocument;performance:PerformanceSettings;columns:number;width:number;font:number;density:string;repeats?:SectionRepeats}) {
  const root = useRef<HTMLDivElement>(null);
  const foldingRepeats = !!repeats?.size;
  const inputs = useMemo(() => ({columns}), [
    document.source, columns, width, font, density, foldingRepeats,
    performance.semitones, performance.capo, performance.spelling, performance.tuning,
  ]);
  const [layout,setLayout] = useState<{inputs:typeof inputs;plan:ColumnPlan}>();
  // An old plan can omit blocks that have just been expanded. Render all current
  // blocks for measurement on the first commit after any layout input changes.
  const plan = layout?.inputs === inputs ? layout.plan : undefined;

  useLayoutEffect(() => {
    if (inputs.columns < 2) return;
    const elements = Array.from(root.current?.querySelectorAll<HTMLElement>('[data-block-id]') ?? []);
    const measurements:BlockMeasurement[] = elements.map(element => ({
      id:element.dataset.blockId!,
      height:element.getBoundingClientRect().height,
      kind:element.dataset.blockKind as BlockMeasurement['kind'],
    }));
    if (!measurements.length) return;
    const target = measurements.reduce((sum,item) => sum + item.height,0) / inputs.columns;
    setLayout({inputs,plan:layoutSections(measurements,inputs.columns,target)});
  }, [inputs]);

  return <div ref={root}><MusicBlocks document={document} performance={performance} mode="play" measure plan={plan} repeats={repeats}/></div>;
}
