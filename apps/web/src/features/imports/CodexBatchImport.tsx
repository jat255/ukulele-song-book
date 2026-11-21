import React, {useState} from 'react';

type Model = {id:string;name:string;default:boolean};
export function CodexBatchImport({csrf,models,onImported}:{csrf:string;models:Model[];onImported:()=>void}) {
  const [files,setFiles]=useState<File[]>([]);
  const [model,setModel]=useState(models.find(item=>item.default)?.id ?? models[0]?.id ?? '');
  const [authorized,setAuthorized]=useState(false);
  const [busy,setBusy]=useState(false);
  const [message,setMessage]=useState('');
  async function submit(event:React.FormEvent) {
    event.preventDefault(); if(!authorized || !model || !files.length)return;
    setBusy(true); let queued=0; const errors:string[]=[];
    try {
      for(const file of files) {
        setMessage(`Queuing ${file.name}…`);
        try {
          const upload=await fetch(`/api/imports/sources?filename=${encodeURIComponent(file.name)}`,{method:'POST',headers:{'X-CSRF-Token':csrf},body:file});
          if(!upload.ok) throw new Error('upload failed');
          const source=await upload.json() as {id:string};
          const response=await fetch('/api/imports',{method:'POST',headers:{'X-CSRF-Token':csrf,'Content-Type':'application/json'},body:JSON.stringify({source_id:source.id,selection:[{pages:[],all_pages:true,provider:'codex',model,authorization:true}],method:'ai',idempotency_key:crypto.randomUUID()})});
          if(!response.ok) {const result=await response.json();throw new Error(result.message || 'could not queue');}
          queued++;
        } catch(error) {errors.push(`${file.name}: ${error instanceof Error ? error.message : 'failed'}`);}
      }
      setMessage(`Queued ${queued} of ${files.length}. ${errors.join(' ')}`); onImported();
    } finally {setBusy(false);}
  }
  return <form className="import-upload" onSubmit={event=>void submit(event)}><h3>Convert PDFs with Codex</h3><p>Choose single-song PDFs, up to five pages each. They will be sent to Codex and enter the review queue.</p><label>PDF files <input type="file" multiple accept=".pdf,application/pdf" onChange={event=>{setFiles(Array.from(event.target.files ?? []));setAuthorized(false);}} /></label><label>Batch Codex model <select value={model} onChange={event=>{setModel(event.target.value);setAuthorized(false);}}>{models.map(item=><option key={item.id} value={item.id}>{item.name}</option>)}</select></label><label><input type="checkbox" checked={authorized} onChange={event=>setAuthorized(event.target.checked)} /> Send these PDFs to Codex using my subscription</label><button disabled={!files.length || !authorized || busy}>{busy?'Queuing…':'Queue PDFs'}</button>{message && <p role="status">{message}</p>}</form>;
}
