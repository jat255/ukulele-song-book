import React, {useState} from 'react';

type Model = {id:string;name:string;default:boolean};
export function CodexBatchImport({csrf,models,onImported}:{csrf:string;models:Model[];onImported:()=>void}) {
  const [files,setFiles]=useState<File[]>([]);
  const [selectedModel,setModel]=useState('');
  const model = models.some(item=>item.id===selectedModel) ? selectedModel : ([...models].filter(item=>/terra/i.test(item.id)).sort((a,b)=>b.id.localeCompare(a.id,undefined,{numeric:true}))[0]?.id ?? models.find(item=>item.default)?.id ?? models[0]?.id ?? '');
  const [dragging,setDragging]=useState(false);
  const [fileError,setFileError]=useState('');
  function chooseFiles(incoming:File[]) {
    const supported=incoming.filter(file=>/\.(pdf|cho|chordpro)$/i.test(file.name));
    setFiles(supported);
    setFileError(supported.length === incoming.length ? '' : 'Only PDF and ChordPro files can be added.');
  }
  const [busy,setBusy]=useState(false);
  const [message,setMessage]=useState('');
  async function submit(event:React.FormEvent) {
    event.preventDefault(); if(!files.length)return;
    setBusy(true); let queued=0; const errors:string[]=[];
    try {
      for(const file of files) {
        setMessage(`Queuing ${file.name}…`);
        try {
          const pdf=/\.pdf$/i.test(file.name);
          if(pdf && !model) throw new Error('Connect Codex in Settings to convert PDFs');
          const upload=await fetch(`/api/imports/sources?filename=${encodeURIComponent(file.name)}`,{method:'POST',headers:{'X-CSRF-Token':csrf},body:file});
          if(!upload.ok) throw new Error('upload failed');
          const source=await upload.json() as {id:string};
          const response=await fetch('/api/imports',{method:'POST',headers:{'X-CSRF-Token':csrf,'Content-Type':'application/json'},body:JSON.stringify({source_id:source.id,selection:pdf ? [{pages:[],all_pages:true,provider:'codex',model,authorization:true}] : [{pages:[]}],method:pdf ? 'ai' : 'direct',idempotency_key:crypto.randomUUID()})});
          if(!response.ok) {const result=await response.json();throw new Error(result.message || 'could not queue');}
          queued++;
        } catch(error) {errors.push(`${file.name}: ${error instanceof Error ? error.message : 'failed'}`);}
      }
      setMessage(`Queued ${queued} of ${files.length}. ${errors.join(' ')}`); onImported();
    } finally {setBusy(false);}
  }
  return <form className="import-upload" onSubmit={event=>void submit(event)}>
    <h3>Import songs</h3>
    <p>ChordPro files are imported directly. Single-song PDFs of up to five pages are sent to Codex for conversion. All imports enter the review queue.</p>
    <div className={`pdf-dropzone${dragging ? ' pdf-dropzone--active' : ''}`} role="group" aria-label="Drop song files here"
      onDragEnter={event=>{event.preventDefault();setDragging(true);}}
      onDragOver={event=>{event.preventDefault();event.dataTransfer.dropEffect='copy';}}
      onDragLeave={event=>{if(!event.currentTarget.contains(event.relatedTarget as Node | null))setDragging(false);}}
      onDrop={event=>{event.preventDefault();setDragging(false);chooseFiles(Array.from(event.dataTransfer.files));}}>
      <span className="pdf-dropzone-icon" aria-hidden="true">↑</span>
      <strong>Drag and drop song files here</strong>
      <span>or</span>
      <label className="pdf-browse" htmlFor="pdf-files">Browse files</label>
      <input className="pdf-input" id="pdf-files" aria-label="Song files" type="file" multiple accept=".pdf,application/pdf,.cho,.chordpro" onChange={event=>chooseFiles(Array.from(event.target.files ?? []))} />
      <small>PDF, .cho or .chordpro · One song per PDF, up to 5 pages</small>
    </div>
    {fileError && <p className="pdf-file-error" role="alert">{fileError}</p>}
    {files.length > 0 && <div className="pdf-selection"><strong>{files.length} {files.length === 1 ? 'file' : 'files'} selected</strong><ul>{files.map((file,index)=><li key={`${file.name}-${file.lastModified}-${index}`}>{file.name}</li>)}</ul></div>}
    {models.length > 0 ? <label className="import-form-field">Codex model <select value={model} onChange={event=>setModel(event.target.value)}>{models.map(item=><option key={item.id} value={item.id}>{item.name}</option>)}</select></label> : <p>Connect Codex in <a href="/settings">Settings</a> to convert PDFs.</p>}
    <button disabled={!files.length || busy}>{busy?'Queuing…':'Queue files'}</button>{message && <p role="status">{message}</p>}
  </form>;
}
