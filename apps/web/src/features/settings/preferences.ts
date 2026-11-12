import {useCallback, useEffect, useRef, useState} from 'react';
import {fromServerEnvelope,toServerEnvelope,mergeLocalPreference,readLocalPreference,writeLocalPreference,mergePreferenceGroup} from '../../offline/preferences';
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
  const etag=useRef(''); const chain=useRef<Promise<void>>(Promise.resolve()); const conflict=useRef(false);const changes=useRef<Record<string,number>>({});
  useEffect(() => {
    let active=true; setReady(false); setDirty(false); conflict.current=false;
    void (async()=>{
      let result:Preferences=structuredClone(defaults);let needsSync=false;
      try{
        if(csrf){const response=await fetch(`/api/preferences/${id}`);if(!response.ok)throw new Error();result=await response.json() as Preferences;etag.current=response.headers.get('ETag') ?? '';const remote=JSON.stringify(result);
          for(const group of ['play','performance','print'] as const){const winner=await mergeLocalPreference(id,group,fromServerEnvelope<unknown>(result.groups[group] as Envelope<unknown>));(result.groups[group] as Envelope<unknown>)=toServerEnvelope(winner);}
          needsSync=JSON.stringify(result)!==remote;
        }else{
          for(const group of ['play','performance','print'] as const){const saved=await readLocalPreference<unknown>(id,group);if(saved)(result.groups[group] as Envelope<unknown>)=toServerEnvelope(saved);}
        }
        if(active){setData(result);setError('');setReady(true);setDirty(needsSync);}
      }catch{etag.current='';try{for(const group of ['play','performance','print'] as const){const saved=await readLocalPreference<unknown>(id,group);if(saved)(result.groups[group] as Envelope<unknown>)=toServerEnvelope(saved);}}catch{/* keep defaults if browser storage also fails */}if(active){setData(result);setError(csrf?'Preferences unavailable.':'Offline preferences unavailable.');setReady(true);}}
    })();
    return () => {active=false;};
  },[id,csrf]);
  const change=useCallback(<K extends keyof Groups>(group:K, value:Groups[K]['value']) => {
    const sequence=(changes.current[group] ?? 0)+1;changes.current[group]=sequence;
    setData(previous=>({...previous,groups:{...previous.groups,[group]:{...previous.groups[group],value}}}));
    void writeLocalPreference(id,group,value).then(envelope=>{if(changes.current[group]!==sequence)return;setData(previous => ({...previous,groups:{...previous.groups,[group]:toServerEnvelope(envelope)}}));setDirty(true);}).catch(()=>setError('Could not save local preferences.'));
  },[id]);
  useEffect(() => {
    if (!ready || !dirty) return;
    const timer=window.setTimeout(() => {
      const payload=data; setDirty(false);
      chain.current=chain.current.then(async () => {
        if (!csrf || !etag.current) return;
        try {
          let candidate=payload;
          for(let attempt=0;attempt<4;attempt++){
            const response=await fetch(`/api/preferences/${id}`,{method:'PUT',headers:{'Content-Type':'application/json','X-CSRF-Token':csrf,'If-Match':etag.current},body:JSON.stringify(candidate)});
            if(response.ok){etag.current=response.headers.get('ETag') ?? '';setError('');return;}
            if(response.status!==409)throw new Error('Preference save failed');
            const latest=await fetch(`/api/preferences/${id}`);if(!latest.ok)throw new Error('Preference refresh failed');
            const remote=await latest.json() as Preferences;etag.current=latest.headers.get('ETag') ?? '';
            for(const group of ['play','performance','print'] as const){const winner=await mergeLocalPreference(id,group,fromServerEnvelope<unknown>(remote.groups[group] as Envelope<unknown>));(remote.groups[group] as Envelope<unknown>)=toServerEnvelope(winner);}
            candidate=remote;
            setData(previous=>{const next=structuredClone(previous);for(const group of ['play','performance','print'] as const){const winner=mergePreferenceGroup(fromServerEnvelope<unknown>(previous.groups[group] as Envelope<unknown>),fromServerEnvelope<unknown>(candidate.groups[group] as Envelope<unknown>));(next.groups[group] as Envelope<unknown>)=toServerEnvelope(winner);}return next;});
          }
          setError('Preferences changed repeatedly; local settings are preserved.');
        } catch {setError('Could not save preferences.');}
      });
    },500);
    return () => clearTimeout(timer);
  },[data,dirty,ready,id,csrf]);
  return {data,ready,error,change};
}
