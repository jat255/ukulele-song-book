import React, {useEffect, useRef, useState} from 'react';
import type {MusicDocument, PerformanceSettings} from '../../../../../packages/music/src/model';
import {MusicBlocks} from '../../music/MusicBlocks';
import {layoutSections, type BlockMeasurement} from './layout';

export function ColumnLayout({document,performance,columns,width,font,density}:{document:MusicDocument;performance:PerformanceSettings;columns:number;width:number;font:number;density:string}) {
  const root = useRef<HTMLDivElement>(null);
  const [plan,setPlan] = useState<string[][]|undefined>();
  useEffect(() => {
    setPlan(undefined);
    const handle = requestAnimationFrame(() => {
      const elements = Array.from(root.current?.querySelectorAll<HTMLElement>('[data-block-id]') ?? []);
      const measurements:BlockMeasurement[] = elements.map(element => ({id:element.dataset.blockId!,height:element.getBoundingClientRect().height,kind:element.dataset.blockKind as BlockMeasurement['kind']}));
      if (columns < 2 || !measurements.length) return;
      const target = measurements.reduce((sum,item) => sum + item.height,0) / columns;
      setPlan(layoutSections(measurements,columns,target));
    });
    return () => cancelAnimationFrame(handle);
  }, [document.source, columns, width, font, density]);
  return <div ref={root}><MusicBlocks document={document} performance={performance} mode="play" measure plan={plan}/></div>;
}
