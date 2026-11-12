import {ActionPopover} from '../ActionPopover';
import React, {useState} from 'react';

type Kind = 'library' | 'chordpro' | 'arrangement';

export function ExportButtons({csrf, id}: {csrf:string; id?:string}) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [ready, setReady] = useState<{id:string; kind:Kind}|null>(null);
  async function start(kind:Kind) {
    setBusy(true); setError(''); setReady(null);
    try {
      const response = await fetch('/api/exports', {method:'POST', headers:{'Content-Type':'application/json','X-CSRF-Token':csrf}, body:JSON.stringify({kind,...(id ? {arrangement_id:id} : {})})});
      if (!response.ok) throw new Error();
      const job = await response.json() as {id:string};
      for (let attempts=0; attempts<120; attempts++) {
        await new Promise(resolve=>setTimeout(resolve, 500));
        const status = await fetch(`/api/exports/${encodeURIComponent(job.id)}`, {cache:'no-store'});
        if (!status.ok) throw new Error();
        const result = await status.json() as {state:string};
        if (result.state === 'complete') {const link=document.createElement('a');link.href='/api/exports/'+encodeURIComponent(job.id)+'/file';link.download='';link.click();setReady({id:job.id,kind}); return;}
        if (result.state === 'failed') throw new Error();
      }
      throw new Error();
    } catch {setError('Export could not be prepared. Please try again.');}
    finally {setBusy(false);}
  }
  return <ActionPopover label="Export" className="export-actions">{id ? <><button disabled={busy} onClick={()=>void start('chordpro')}>Export ChordPro</button><button disabled={busy} onClick={()=>void start('arrangement')}>Export with sources</button></> : <button disabled={busy} onClick={()=>void start('library')}>Export library</button>}{busy && <span role="status">Preparing export…</span>}{error && <span role="alert">{error}</span>}{ready && <a href={`/api/exports/${encodeURIComponent(ready.id)}/file`}>Download {ready.kind === 'library' ? 'library export' : ready.kind === 'chordpro' ? 'ChordPro' : 'arrangement export'}</a>}</ActionPopover>;
}
