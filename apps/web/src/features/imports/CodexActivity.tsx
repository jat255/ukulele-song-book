import React, {useEffect, useState} from 'react';

type Activity = {text:string;truncated:boolean};
export function CodexActivity({jobId,state}:{jobId:string;state:string}) {
  const [open,setOpen]=useState(false);
  const [activity,setActivity]=useState<Activity|null>(null);
  const [error,setError]=useState('');
  const [copied,setCopied]=useState(false);
  useEffect(()=>{
    if(!open)return;
    let stopped=false;
    async function load() {
      try {
        const response=await fetch(`/api/imports/${encodeURIComponent(jobId)}/activity`);
        if(!response.ok)throw new Error('Could not load the Codex log.');
        const data=await response.json() as Activity;
        if(!stopped){setActivity(data);setError('');}
      } catch(err){if(!stopped)setError(err instanceof Error ? err.message : 'Could not load the Codex log.');}
    }
    void load();
    const timer=state==='queued' || state==='processing' ? setInterval(()=>void load(),1500) : null;
    return ()=>{stopped=true;if(timer)clearInterval(timer);};
  },[open,jobId,state]);
  function download(){
    if(!activity)return;
    const url=URL.createObjectURL(new Blob([activity.text],{type:'text/plain;charset=utf-8'}));
    const link=document.createElement('a');link.href=url;link.download=`codex-${jobId}.txt`;link.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
  }
  async function copy(){try{await navigator.clipboard.writeText(activity?.text ?? '');setCopied(true);}catch{setError('Copy failed; select and copy the log text instead.');}}
  return <details className="codex-activity" onToggle={event=>setOpen(event.currentTarget.open)}><summary>View Codex conversation and logs</summary><p>Includes the prompt, available reasoning summaries, response and error details. Logs can contain song content.</p>{error && <p role="alert">{error}</p>}{!activity && !error && <p>Loading log…</p>}{activity && <><div className="codex-activity-actions"><button type="button" disabled={!activity.text} onClick={download}>Download log</button><button type="button" disabled={!activity.text} onClick={()=>void copy()}>{copied?'Copied':'Copy log'}</button></div>{activity.truncated && <p>Log reached its 1,000,000-character limit; earlier output was not retained.</p>}<pre aria-label="Codex conversation log">{activity.text || 'No details were recorded for this attempt.'}</pre></>}</details>;
}
