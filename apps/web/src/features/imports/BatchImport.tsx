import React, {useState} from 'react';

export function BatchImport({csrf,onImported}:{csrf:string;onImported:()=>void}) {
  const [file,setFile]=useState<File|null>(null);
  const [busy,setBusy]=useState(false);
  const [message,setMessage]=useState('');
  async function upload(event:React.FormEvent) {
    event.preventDefault(); if(!file)return;
    setBusy(true);setMessage('');
    try {
      const response=await fetch('/api/imports/batches',{method:'POST',headers:{'X-CSRF-Token':csrf,'Content-Type':'application/zip'},body:file});
      const data=await response.json();
      if(!response.ok) throw new Error(data.detail || 'Could not import batch');
      setMessage(`Imported ${data.imported.length}; already imported ${data.existing.length}; skipped ${data.skipped.length}. Review each draft before accepting.`);
      onImported();
    } catch(error) {setMessage(error instanceof Error ? error.message : 'Could not import batch');} finally {setBusy(false);}
  }
  return <form className="import-upload" onSubmit={event=>void upload(event)}><h3>Import converted batch</h3><label>Batch ZIP <input type="file" accept=".zip" onChange={event=>setFile(event.target.files?.[0] ?? null)}/></label><button disabled={!file || busy}>{busy?'Importing…':'Import converted batch'}</button>{message && <p role="status">{message}</p>}</form>;
}
