import {useCallback, useEffect, useRef, useState} from 'react';
import type {PerformanceSettings,PlaySettings,PrintSettings} from '../../../../../packages/music/src/model';

type Envelope<T> = {value:T; updated_at:number; device_id:string};
type Groups = {play:Envelope<PlaySettings>; performance:Envelope<PerformanceSettings>; print:Envelope<PrintSettings>};
type Preferences = {schema_version:1;groups:Groups};
export const defaults:Preferences = {schema_version:1,groups:{
  play:{value:{fontPx:20,density:'compact',columns:'auto',scrollPxPerSecond:15,focus:false},updated_at:0,device_id:'server'},
  performance:{value:{semitones:0,spelling:'auto',capo:0,tuning:'high-g'},updated_at:0,device_id:'server'},
  print:{value:{paper:'Letter',fontPt:12,density:'compact',marginsMm:8,columns:'auto',diagrams:false},updated_at:0,device_id:'server'},
}};
export function usePreferences(id:string,csrf:string) {
  const [data,setData]=useState<Preferences>(defaults);
  const [ready,setReady]=useState(false);
  const [error,setError]=useState('');
  const [dirty,setDirty]=useState(false);
  const etag=useRef(''); const chain=useRef<Promise<void>>(Promise.resolve()); const conflict=useRef(false);
  const device=useRef(crypto.randomUUID());
  useEffect(() => {
    let active=true; setReady(false); setDirty(false); conflict.current=false;
    void fetch(`/api/preferences/${id}`).then(async response => {
      if (!response.ok) throw new Error();
      const value=await response.json() as Preferences;
      if (active) {etag.current=response.headers.get('ETag') ?? '';setData(value);setReady(true);}
    }).catch(() => {if (active) {setError('Preferences unavailable.');setReady(true);}});
    return () => {active=false;};
  },[id]);
  const change=useCallback(<K extends keyof Groups>(group:K, value:Groups[K]['value']) => {
    setData(previous => ({...previous,groups:{...previous.groups,[group]:{value,updated_at:Date.now()/1000,device_id:device.current}}}));setDirty(true);
  },[]);
  useEffect(() => {
    if (!ready || !dirty) return;
    const timer=window.setTimeout(() => {
      const payload=data; setDirty(false);
      chain.current=chain.current.then(async () => {
        if (conflict.current || !etag.current) return;
        try {
          const response=await fetch(`/api/preferences/${id}`,{method:'PUT',headers:{'Content-Type':'application/json','X-CSRF-Token':csrf,'If-Match':etag.current},body:JSON.stringify(payload)});
          if (!response.ok) {conflict.current=true;setError(response.status===409 ? 'Preferences changed elsewhere; local settings are preserved.' : 'Could not save preferences.');return;}
          etag.current=response.headers.get('ETag') ?? '';
        } catch {setError('Could not save preferences.');}
      });
    },500);
    return () => clearTimeout(timer);
  },[data,dirty,ready,id,csrf]);
  return {data,ready,error,change};
}
