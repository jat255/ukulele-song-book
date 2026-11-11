import React, {useEffect,useState} from 'react';
import type {PerformanceSettings,PrintSettings} from '../../../../../packages/music/src/model';
import {PrintDocument} from '../../print/PrintDocument';
import {usePreferences} from '../settings/preferences';
import type {Setlist} from './Setlists';

type Job={id:string;state:string;source_revision:string;page_count:number|null;columns:number|null;diagnostics:string[];error_code:string|null};
type PrintSong={source:string;performance:PerformanceSettings};

export function SetlistPrint({id,csrf}:{id:string;csrf:string}) {
  const defaults=usePreferences('defaults',csrf);
  const [set,setSet]=useState<Setlist|null>(null);
  const [settings,setSettings]=useState<PrintSettings|null>(null);
  const [mode,setMode]=useState<'new-page'|'pack'>('new-page');
  const [job,setJob]=useState<Job|null>(null);
  const [songs,setSongs]=useState<PrintSong[]>([]);
  const [status,setStatus]=useState('Loading setlist…');
  const [attempt,setAttempt]=useState(0);
  useEffect(()=>{let active=true;void fetch(`/api/setlists/${id}`).then(async response=>{if(!response.ok)throw new Error();const data=await response.json() as Setlist;if(active)setSet(data);}).catch(()=>{if(active)setStatus('Setlist unavailable.');});return()=>{active=false;};},[id]);
  useEffect(()=>{if(defaults.ready && !settings)setSettings(defaults.data.groups.print.value);},[defaults.ready,defaults.data,settings]);
  useEffect(()=>{
    if(!set || !settings)return;
    let active=true;let timer=0;const controller=new AbortController();setJob(null);setStatus('Generating current PDF…');
    const start=window.setTimeout(()=>{void (async()=>{
      try {
        const response=await fetch('/api/pdfs/setlist',{method:'POST',headers:{'Content-Type':'application/json','X-CSRF-Token':csrf},body:JSON.stringify({setlist_id:id,revision:set.revision,settings,songBreak:mode}),signal:controller.signal});
        if(response.status===409){if(active)setStatus('Setlist changed or contains an unavailable song. Reload to review it.');return;}
        if(!response.ok){const body=await response.json() as {message?:string};if(active)setStatus(body.message || 'PDF generation failed. Try again.');return;}
        let current=await response.json() as Job;
        while(active && (current.state==='queued' || current.state==='processing')) {await new Promise<void>(resolve=>{timer=window.setTimeout(resolve,500);});if(!active)return;const poll=await fetch(`/api/pdfs/${current.id}`,{signal:controller.signal});if(!poll.ok)throw new Error();current=await poll.json() as Job;}
        if(!active)return;
        if(current.state!=='complete' || current.source_revision!==set.revision){setStatus(current.error_code==='tab_too_wide' ? 'Tab is too wide for the selected page.' : 'PDF generation failed. Try again.');return;}
        setJob(current);setStatus('');
      } catch {if(active)setStatus('PDF generation failed. Try again.');}
    })();},350);
    return()=>{active=false;clearTimeout(start);clearTimeout(timer);controller.abort();};
  },[set,settings,mode,id,csrf,attempt]);
  useEffect(()=>{
    if(!set)return;let active=true;
    void Promise.all(set.items.map(async item=>{
      const [snapshotResponse,prefResponse]=await Promise.all([fetch(`/api/arrangements/${item.arrangementId}`),fetch(`/api/preferences/${item.arrangementId}`)]);
      if(!snapshotResponse.ok || !prefResponse.ok)throw new Error();
      const snapshot=await snapshotResponse.json() as {source:string};const preferences=await prefResponse.json() as {groups:{performance:{value:PerformanceSettings}}};return {source:snapshot.source,performance:preferences.groups.performance.value};
    })).then(result=>{if(active)setSongs(result);}).catch(()=>{if(active)setSongs([]);});
    return()=>{active=false;};
  },[set]);
  function change(part:Partial<PrintSettings>){if(!settings)return;setJob(null);setStatus('Generating current PDF…');setSettings({...settings,...part});}
  if(!settings)return <section>{status}</section>;
  return <section className="print-workspace"><h2>Print setlist</h2><p>Generated PDF pages are authoritative; browser print pagination can differ.</p><div className="print-controls"><label htmlFor="set-paper">Paper</label><select id="set-paper" value={settings.paper} onChange={event=>change({paper:event.target.value as PrintSettings['paper']})}><option>Letter</option><option>A4</option></select><label htmlFor="set-font">Text size (pt)</label><input id="set-font" type="number" min="8" max="24" value={settings.fontPt} onChange={event=>change({fontPt:Math.max(8,Math.min(24,Number(event.target.value)))})}/><label htmlFor="set-density">Density</label><select id="set-density" value={settings.density} onChange={event=>change({density:event.target.value as PrintSettings['density']})}><option value="tight">Tight</option><option value="compact">Compact</option><option value="relaxed">Relaxed</option></select><label htmlFor="set-margins">Margins (mm)</label><input id="set-margins" type="number" min="3" max="25" value={settings.marginsMm} onChange={event=>change({marginsMm:Math.max(3,Math.min(25,Number(event.target.value)))})}/><label htmlFor="set-columns">Columns</label><select id="set-columns" value={settings.columns} onChange={event=>change({columns:event.target.value==='auto'?'auto':Number(event.target.value) as 1|2})}><option value="auto">Automatic</option><option value="1">1</option><option value="2">2</option></select><label htmlFor="song-break">Song placement</label><select id="song-break" value={mode} onChange={event=>{setJob(null);setStatus('Generating current PDF…');setMode(event.target.value as 'new-page'|'pack');}}><option value="new-page">New page per song</option><option value="pack">Pack songs</option></select><label><input type="checkbox" checked={settings.diagrams} onChange={event=>change({diagrams:event.target.checked})}/>Chord diagrams</label><button disabled={!set || songs.length!==set.items.length} onClick={()=>window.print()}>Browser print</button></div>{status && <p role="status">{status}</p>}{status.includes('Try again') && <button onClick={()=>setAttempt(attempt+1)}>Retry PDF</button>}{job && <><p>Actual page count: {job.page_count}; columns: {job.columns}</p><ul>{job.diagnostics.map((item,index)=><li key={index}>{item}</li>)}</ul><a href={`/api/pdfs/${job.id}/file`}>Download PDF</a><div className="pdf-pages">{Array.from({length:job.page_count ?? 0},(_,index)=><img key={index} alt={`PDF page ${index+1}`} src={`/api/pdfs/${job.id}/pages/${index+1}.png`}/>)}</div></>}<div className="set-browser-print">{songs.map((song,index)=><div key={set?.items[index]?.id ?? index} className={index>0 && mode==='new-page' ? 'set-print-song--page':''}><PrintDocument source={song.source} performance={song.performance} settings={settings}/></div>)}</div></section>;
}
