export type PreferenceEnvelope<T>={schemaVersion:1;value:T;updatedAtMs:number;deviceId:string};
export type ServerEnvelope<T>={value:T;updated_at:number;device_id:string};
export function mergePreferenceGroup<T>(local:PreferenceEnvelope<T>,remote:PreferenceEnvelope<T>):PreferenceEnvelope<T>{
  if(local.updatedAtMs!==remote.updatedAtMs)return local.updatedAtMs>remote.updatedAtMs?local:remote;
  return local.deviceId>=remote.deviceId?local:remote;
}
export function nextPreferenceTimestamp(previous:number,now=Date.now()):number{return Math.max(now,previous+1);}
export function fromServerEnvelope<T>(server:ServerEnvelope<T>):PreferenceEnvelope<T>{return {schemaVersion:1,value:server.value,updatedAtMs:Math.round(server.updated_at*1000),deviceId:server.device_id};}
export function toServerEnvelope<T>(local:PreferenceEnvelope<T>):ServerEnvelope<T>{return {value:local.value,updated_at:local.updatedAtMs/1000,device_id:local.deviceId};}

import {openDb} from './db';
function scope(){return localStorage.getItem('songbook-current-scope') ?? localStorage.getItem('songbook-offline-scope');}
function deviceId(){let id=localStorage.getItem('songbook-device-id');if(!id){id=crypto.randomUUID();localStorage.setItem('songbook-device-id',id);}return id;}
function prefKey(scopeId:string,id:string,group:string){return `preference:${scopeId}:${id}:${group}`;}
export async function readLocalPreference<T>(id:string,group:string):Promise<PreferenceEnvelope<T>|null>{
  const scopeId=scope();if(!scopeId)return null;const db=await openDb();
  return new Promise((resolve,reject)=>{const tx=db.transaction('meta','readonly'),req=tx.objectStore('meta').get(prefKey(scopeId,id,group));tx.oncomplete=()=>{db.close();resolve(req.result?.envelope ?? null);};tx.onerror=()=>{db.close();reject(tx.error);};});
}
export async function mergeLocalPreference<T>(id:string,group:string,incoming:PreferenceEnvelope<T>):Promise<PreferenceEnvelope<T>>{
  const scopeId=scope();if(!scopeId)return incoming;const db=await openDb();
  return new Promise((resolve,reject)=>{const tx=db.transaction('meta','readwrite'),store=tx.objectStore('meta'),key=prefKey(scopeId,id,group),req=store.get(key);let winner=incoming;
    req.onsuccess=()=>{if(req.result)winner=mergePreferenceGroup(req.result.envelope,incoming);store.put({key,envelope:winner});};
    tx.oncomplete=()=>{db.close();resolve(winner);};tx.onerror=()=>{db.close();reject(tx.error);};tx.onabort=()=>{db.close();reject(tx.error);};});
}
export async function writeLocalPreference<T>(id:string,group:string,value:T):Promise<PreferenceEnvelope<T>>{
  const scopeId=scope(),device=deviceId();if(!scopeId)return {schemaVersion:1,value,updatedAtMs:Date.now(),deviceId:device};const db=await openDb();
  return new Promise((resolve,reject)=>{const tx=db.transaction('meta','readwrite'),store=tx.objectStore('meta'),clockKey=`clock:${scopeId}:${device}`,req=store.get(clockKey);let envelope:PreferenceEnvelope<T>;
    req.onsuccess=()=>{const timestamp=nextPreferenceTimestamp(req.result?.value ?? 0);envelope={schemaVersion:1,value,updatedAtMs:timestamp,deviceId:device};store.put({key:clockKey,value:timestamp});store.put({key:prefKey(scopeId,id,group),envelope});};
    tx.oncomplete=()=>{db.close();resolve(envelope);};tx.onerror=()=>{db.close();reject(tx.error);};tx.onabort=()=>{db.close();reject(tx.error);};});
}
