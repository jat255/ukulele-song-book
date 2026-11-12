import {getScopedSelections,metaRequest,verifyAvailability,downloadSelection} from './downloads';
import type {DownloadManifest,Selection} from './downloads';
import {prepareShell} from './shell';

type State='current'|'outdated'|'deleted'|'unavailable';
type Result={id:string;revision:string|null;state:State};
type SyncResult={arrangements:Result[];setlists:Result[]};
type SyncRecord={key:string;signature:string;available:boolean;arrangements:Result[];setlists:Result[]};
function signature(row:Selection){const set=row.manifest.setlist as {id:string;revision:string}|null;return JSON.stringify([row.manifest.snapshots.map(s=>[s.id,s.revision]),set && [set.id,set.revision]]);}
async function readRecord(row:Selection):Promise<SyncRecord|null>{const record=await metaRequest<SyncRecord|undefined>('readonly',store=>store.get(`sync:${row.key}`));return record?.signature===signature(row)?record:null;}
export async function checkDownloads(csrf:string):Promise<void>{
  const rows=await getScopedSelections();
  for(const row of rows){
    const set=row.manifest.setlist as {id:string;revision:string}|null;
    let result:SyncResult|null=null;
    try{const response=await fetch('/api/sync/check',{method:'POST',headers:{'Content-Type':'application/json','X-CSRF-Token':csrf},body:JSON.stringify({arrangements:row.manifest.snapshots.map(s=>({id:s.id,revision:s.revision})),setlists:set?[{id:set.id,revision:set.revision}]:[]})});if(response.ok)result=await response.json() as SyncResult;}catch{/* retain prior state when offline */}
    const previous=await readRecord(row);
    const record:SyncRecord={key:`sync:${row.key}`,signature:signature(row),available:!!result,arrangements:result?.arrangements ?? previous?.arrangements ?? [],setlists:result?.setlists ?? previous?.setlists ?? []};
    await metaRequest<IDBValidKey>('readwrite',store=>store.put(record));
  }
}
export async function arrangementSyncStatus(id:string):Promise<{state:State|null;available:boolean}>{
  const rows=await getScopedSelections();
  rows.sort((a,b)=>Number(b.manifest.selectionId===`arrangement:${id}`)-Number(a.manifest.selectionId===`arrangement:${id}`));
  for(const row of rows){if(!row.manifest.snapshots.some(snapshot=>snapshot.id===id) || await verifyAvailability(row.manifest.selectionId)!=='downloaded')continue;const record=await readRecord(row);return {state:record?.arrangements.find(entry=>entry.id===id)?.state ?? null,available:!!record?.available};}
  return {state:null,available:false};
}
export async function refreshDownloads(ids:string[]):Promise<{refreshed:string[];failed:string[]}>{
  const rows=(await getScopedSelections()).filter(row=>ids.includes(row.manifest.selectionId));const report={refreshed:[] as string[],failed:[] as string[]};
  for(const row of rows){try{const [kind,id]=row.manifest.selectionId.split(':');if(!id || !['arrangement','setlist'].includes(kind))throw new Error('Invalid selection');const response=await fetch(`/api/downloads/${kind==='arrangement'?'arrangements':'setlists'}/${encodeURIComponent(id)}`);if(!response.ok)throw new Error('Refresh unavailable');const manifest=await response.json() as DownloadManifest;const shell=await prepareShell();await downloadSelection(manifest,row.includeOriginals,shell);report.refreshed.push(row.manifest.selectionId);}catch{report.failed.push(row.manifest.selectionId);}}
  return report;
}
export async function setlistSyncStatus(id:string):Promise<{partial:boolean;outdated:boolean;deleted:boolean;available:boolean}>{
  const row=(await getScopedSelections()).find(item=>item.manifest.selectionId===`setlist:${id}`);if(!row)return {partial:false,outdated:false,deleted:false,available:false};
  const record=await readRecord(row);return {deleted:!!record?.setlists.some(item=>item.state==='deleted'),partial:!!record?.arrangements.some(item=>item.state==='deleted'||item.state==='unavailable'),outdated:!!record?.setlists.some(item=>item.state==='outdated') || !!record?.arrangements.some(item=>item.state==='outdated'),available:!!record?.available};
}
