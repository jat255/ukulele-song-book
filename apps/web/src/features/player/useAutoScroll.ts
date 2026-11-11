import {useCallback, useEffect, useRef, useState} from 'react';

export function useAutoScroll(speed:number) {
  const [running,setRunning]=useState(false);
  const runningRef=useRef(false);
  const pause=useCallback(() => {runningRef.current=false;setRunning(false);}, []);
  const start=useCallback(() => {runningRef.current=true;setRunning(true);}, []);
  useEffect(() => {
    if (!running) return;
    let frame=0,last:number|undefined,carry=0;
    const step=(now:number) => {
      if (!runningRef.current) return;
      if (last !== undefined) {
        carry += Math.max(0,now-last)*speed/1000;
        const pixels=Math.floor(carry);
        if (pixels>0) {window.scrollBy(0,pixels); carry-=pixels;}
        if (window.scrollY + innerHeight >= document.documentElement.scrollHeight - 1) {pause(); return;}
      }
      last=now; frame=requestAnimationFrame(step);
    };
    frame=requestAnimationFrame(step);
    const manual=(event:Event) => {
      const target=event.target as Element|null;
      if (target?.closest?.('#player-tools, .player-tools-toggle')) return;
      pause();
    };
    const visibility=() => {if (document.hidden) pause();};
    window.addEventListener('wheel',manual,{passive:true}); window.addEventListener('touchstart',manual,{passive:true}); window.addEventListener('pointerdown',manual,{passive:true});
    document.addEventListener('visibilitychange',visibility);
    return () => {cancelAnimationFrame(frame);window.removeEventListener('wheel',manual);window.removeEventListener('touchstart',manual);window.removeEventListener('pointerdown',manual);document.removeEventListener('visibilitychange',visibility);};
  }, [running,speed,pause]);
  useEffect(() => {
    const key=(event:KeyboardEvent) => {
      const target=event.target as HTMLElement|null;
      if (['ArrowUp','ArrowDown','PageUp','PageDown','Home','End'].includes(event.key) && !['INPUT','TEXTAREA','SELECT'].includes(target?.tagName ?? '')) {pause();return;}
      if (event.code !== 'Space' || target?.isContentEditable || ['INPUT','TEXTAREA','SELECT','BUTTON'].includes(target?.tagName ?? '')) return;
      event.preventDefault(); if (runningRef.current) pause(); else start();
    };
    window.addEventListener('keydown',key); return () => window.removeEventListener('keydown',key);
  }, [pause,start]);
  return {running,start,pause};
}
