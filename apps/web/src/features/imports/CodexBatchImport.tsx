import React, {useState} from 'react';

type Model = {id:string;name:string;default:boolean};
export function CodexBatchImport({csrf,models,onImported}:{csrf:string;models:Model[];onImported:()=>void}) {
  const [files,setFiles]=useState<File[]>([]);
  const [model,setModel]=useState([...models].filter(item=>/terra/i.test(item.id)).sort((a,b)=>b.id.localeCompare(a.id,undefined,{numeric:true}))[0]?.id ?? models.find(item=>item.default)?.id ?? models[0]?.id ?? '');
  const [dragging,setDragging]=useState(false);
  const [fileError,setFileError]=useState('');
  function chooseFiles(incoming:File[]) {
    const pdfs=incoming.filter(file=>file.name.toLowerCase().endsWith('.pdf'));
    setFiles(pdfs);
    setFileError(pdfs.length === incoming.length ? '' : 'Only PDF files can be added.');
  }
  const [busy,setBusy]=useState(false);
  const [message,setMessage]=useState('');
  async function submit(event:React.FormEvent) {
    event.preventDefault(); if(!model || !files.length)return;
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
  return <form className="import-upload" onSubmit={event=>void submit(event)}>
    <h3>Convert PDFs with Codex</h3>
    <p>Choose single-song PDFs, up to five pages each. They will be sent to Codex and enter the review queue.</p>
    <div className={`pdf-dropzone${dragging ? ' pdf-dropzone--active' : ''}`} role="group" aria-label="Drop PDF files here"
      onDragEnter={event=>{event.preventDefault();setDragging(true);}}
      onDragOver={event=>{event.preventDefault();event.dataTransfer.dropEffect='copy';}}
      onDragLeave={event=>{if(!event.currentTarget.contains(event.relatedTarget as Node | null))setDragging(false);}}
      onDrop={event=>{event.preventDefault();setDragging(false);chooseFiles(Array.from(event.dataTransfer.files));}}>
      <span className="pdf-dropzone-icon" aria-hidden="true">↑</span>
      <strong>Drag and drop PDF files here</strong>
      <span>or</span>
      <label className="pdf-browse" htmlFor="pdf-files">Browse files</label>
      <input className="pdf-input" id="pdf-files" aria-label="PDF files" type="file" multiple accept=".pdf,application/pdf" onChange={event=>chooseFiles(Array.from(event.target.files ?? []))} />
      <small>One song per PDF · Up to 5 pages each</small>
    </div>
    {fileError && <p className="pdf-file-error" role="alert">{fileError}</p>}
    {files.length > 0 && <div className="pdf-selection"><strong>{files.length} {files.length === 1 ? 'file' : 'files'} selected</strong><ul>{files.map((file,index)=><li key={`${file.name}-${file.lastModified}-${index}`}>{file.name}</li>)}</ul></div>}
    <label className="import-form-field">Codex model <select value={model} onChange={event=>setModel(event.target.value)}>{models.map(item=><option key={item.id} value={item.id}>{item.name}</option>)}</select></label>
    <button disabled={!files.length || !model || busy}>{busy?'Queuing…':'Queue PDFs'}</button>{message && <p role="status">{message}</p>}
  </form>;
}
