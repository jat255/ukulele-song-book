import React, {useEffect, useState} from 'react';
import {parseSource} from '../../../../../packages/music/src/parser';
import type {PrintSettings} from '../../../../../packages/music/src/model';
import {usePreferences} from '../settings/preferences';
import {PrintDocument} from '../../print/PrintDocument';
import {getOfflineSnapshot} from '../../offline/downloads';
import './print.css';

type Snapshot={id:string; revision:string; source:string};
type Job={id:string;state:string;source_revision:string;fingerprint:string;page_count:number|null;columns:number|null;diagnostics:string[];error_code:string|null};
const errorMessages:Record<string,string> = {tab_too_wide:'Tab is too wide for the selected page and text size.',tab_too_tall:'Tab is taller than the available page; split it into complete string groups.',content_too_wide:'Music is too wide for the selected page and text size.',render_failed:'PDF generation failed. Try again.',render_interrupted:'PDF generation was interrupted. Try again.',render_timeout:'PDF generation timed out. Try again.'};
export function PrintWorkspace({id,csrf}:{id:string;csrf:string}) {
  const prefs=usePreferences(id,csrf);
  const [snapshot,setSnapshot]=useState<Snapshot|null>(null);
  const [job,setJob]=useState<Job|null>(null);
  const [status,setStatus]=useState('Loading arrangement…');
  const [attempt,setAttempt]=useState(0);
  useEffect(() => {let active=true;void fetch(`/api/arrangements/${id}`).then(async response => {if (!response.ok) throw new Error();const data=await response.json() as Snapshot;if(active)setSnapshot(data);}).catch(() => {void getOfflineSnapshot(id).then(saved=>{if(active){if(saved)setSnapshot(saved);else setStatus('Arrangement unavailable offline.');}});});return () => {active=false;};},[id]);
  const print=prefs.data.groups.print.value, storedPerformance=prefs.data.groups.performance.value;
  const capoDirective=snapshot ? parseSource(snapshot.source).blocks.find(block => block.kind === 'directive' && block.name === 'capo') : undefined;
  const sourceCapo=capoDirective?.kind === 'directive' ? Number(capoDirective.value) : 0;
  const performance=prefs.data.groups.performance.updated_at === 0 && Number.isInteger(sourceCapo) && sourceCapo >= 0 && sourceCapo <= 12 ? {...storedPerformance,capo:sourceCapo} : storedPerformance;
  useEffect(() => {
    if (!snapshot || !prefs.ready) return;
    if (!csrf) {setStatus('Server PDF generation requires a connection.');return;}
    let active=true; let timer=0; const controller=new AbortController();
    setJob(null);setStatus('Generating current PDF…');
    const start=window.setTimeout(() => {
      void (async () => {
        try {
          const response=await fetch('/api/pdfs',{method:'POST',headers:{'Content-Type':'application/json','X-CSRF-Token':csrf},body:JSON.stringify({arrangement_id:id,revision:snapshot.revision,performance,settings:print}),signal:controller.signal});
          if (response.status===409) {if(active)setStatus('Arrangement changed. Reload to choose the current revision.');return;}
          if (!response.ok) throw new Error();
          let current=await response.json() as Job;
          while(active && (current.state==='queued' || current.state==='processing')) {
            await new Promise<void>(resolve => {timer=window.setTimeout(resolve,500);});
            if (!active) return;
            const poll=await fetch(`/api/pdfs/${current.id}`,{signal:controller.signal});
            if (!poll.ok) throw new Error();
            current=await poll.json() as Job;
          }
          if (!active) return;
          if (current.state!=='complete' || current.source_revision!==snapshot.revision) {setStatus(errorMessages[current.error_code ?? ''] ?? 'PDF generation failed. Try again.');return;}
          setJob(current);setStatus('');
        } catch {if(active)setStatus('PDF generation failed. Try again.');}
      })();
    },350);
    return () => {active=false;clearTimeout(start);clearTimeout(timer);controller.abort();};
  },[id,csrf,snapshot,prefs.ready,JSON.stringify(print),JSON.stringify(performance),attempt]);
  function change(part:Partial<PrintSettings>) {setJob(null);setStatus('Generating current PDF…');prefs.change('print',{...print,...part});}
  return <section className="print-workspace"><h2>Print preview</h2><p>Preview and download use the same generated PDF. Browser printing uses browser pagination, which can differ.</p><div className="print-controls"><label htmlFor="paper">Paper</label><select id="paper" value={print.paper} onChange={event => change({paper:event.target.value as PrintSettings['paper']})}><option>Letter</option><option>A4</option></select><label htmlFor="print-font">Text size (pt)</label><input id="print-font" type="number" min="8" max="24" value={print.fontPt} onChange={event => change({fontPt:Math.max(8,Math.min(24,Number(event.target.value)))})}/><label htmlFor="print-density">Density</label><select id="print-density" value={print.density} onChange={event => change({density:event.target.value as PrintSettings['density']})}><option value="tight">Tight</option><option value="compact">Compact</option><option value="relaxed">Relaxed</option></select><label htmlFor="margins">Margins (mm)</label><input id="margins" type="number" min="3" max="25" value={print.marginsMm} onChange={event => change({marginsMm:Math.max(3,Math.min(25,Number(event.target.value)))})}/><label htmlFor="print-columns">Columns</label><select id="print-columns" value={print.columns} onChange={event => change({columns:event.target.value === 'auto' ? 'auto' : Number(event.target.value) as 1|2})}><option value="auto">Automatic</option><option value="1">1</option><option value="2">2</option></select><label><input type="checkbox" checked={print.diagrams} onChange={event => change({diagrams:event.target.checked})}/>Chord diagrams</label><button disabled={!snapshot} onClick={() => window.print()}>Browser print</button></div>{prefs.error && <p role="alert">{prefs.error}</p>}{status && <p role="status">{status}</p>}{(status.includes('failed') || status.includes('Try again')) && <button onClick={() => setAttempt(attempt+1)}>Retry PDF</button>}{job && <><p>Actual page count: {job.page_count}; columns: {job.columns}</p><ul>{job.diagnostics.map((diagnostic,index)=><li key={index}>{diagnostic}</li>)}</ul><a href={`/api/pdfs/${job.id}/file`}>Download PDF</a><div className="pdf-pages">{Array.from({length:job.page_count ?? 0},(_,index)=><img key={index} alt={`PDF page ${index+1}`} src={`/api/pdfs/${job.id}/pages/${index+1}.png`}/>)}</div></>}{snapshot && <PrintDocument source={snapshot.source} performance={performance} settings={print}/>}</section>;
}
