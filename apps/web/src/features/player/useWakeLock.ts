import {useCallback, useEffect, useRef, useState} from 'react';

export function useWakeLock() {
  const [status,setStatus]=useState<'off'|'on'|'unavailable'>('off');
  const sentinel=useRef<WakeLockSentinel|null>(null);
  const release=useCallback(async () => {await sentinel.current?.release();sentinel.current=null;setStatus('off');}, []);
  const request=useCallback(async () => {
    try {
      if (!('wakeLock' in navigator)) {setStatus('unavailable');return;}
      const lock=await navigator.wakeLock.request('screen'); sentinel.current=lock; setStatus('on');
      lock.addEventListener('release',() => {sentinel.current=null;setStatus('off');});
    } catch {setStatus('unavailable');}
  }, []);
  useEffect(() => {
    const visibility=() => {if (document.hidden) void release();};
    document.addEventListener('visibilitychange',visibility);
    return () => {document.removeEventListener('visibilitychange',visibility);void sentinel.current?.release();};
  },[release]);
  return {status,request,release};
}
