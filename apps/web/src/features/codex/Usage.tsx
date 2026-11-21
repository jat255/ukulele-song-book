import {useCallback, useState} from 'react';
import {ActionPopover} from '../ActionPopover';

type Window = {used_percent:number;window_minutes:number|null;resets_at:number|null};
export type Usage = {primary:Window|null;secondary:Window|null};

function windowLabel(window:Window|null, fallback:string):string {
  if (!window?.window_minutes) return fallback;
  if (window.window_minutes === 300) return '5-hour limit';
  if (window.window_minutes === 10080) return 'Weekly limit';
  return `${window.window_minutes}-minute limit`;
}

export function UsageBars({usage}:{usage:Usage|null}) {
  if (!usage) return <p className="codex-usage-unavailable">Usage details are unavailable.</p>;
  return <div className="codex-usage">{(['primary','secondary'] as const).map(key=>{
    const window=usage[key];
    const label=windowLabel(window,window ? (key==='primary'?'Primary limit':'Secondary limit') : (key==='primary'?'5-hour limit':'Weekly limit'));
    if (!window || !Number.isFinite(window.used_percent)) return <div className="codex-usage-row" key={key}><span>{label} unavailable</span></div>;
    const percent=Math.max(0,Math.min(100,window.used_percent));
    return <div className="codex-usage-row" key={key}>
      <div className="codex-usage-heading"><strong>{label}</strong><span>{window.used_percent}% used</span></div>
      <progress aria-label={label} value={percent} max={100}>{percent}%</progress>
      <small>{window.resets_at ? `Resets ${new Date(window.resets_at*1000).toLocaleString()}` : 'Reset time unavailable'}</small>
    </div>;
  })}</div>;
}

export function UsagePopover() {
  const [usage,setUsage]=useState<Usage|null>(null);
  const [loading,setLoading]=useState(false);
  const refresh=useCallback(async()=>{
    setLoading(true);
    try {const response=await fetch('/api/codex/usage');setUsage(response.ok ? await response.json() as Usage : null);}
    catch {setUsage(null);} finally {setLoading(false);}
  },[]);
  return <ActionPopover label="Usage" className="usage-popover" onOpen={()=>void refresh()} icon={<svg aria-hidden="true" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"><path d="M4 19h16M6 16v-4m6 4V6m6 10V9"/></svg>}>
    <strong>Codex usage</strong>
    {loading ? <p>Loading usage…</p> : <UsageBars usage={usage}/>}
    <button type="button" disabled={loading} onClick={()=>void refresh()}>Refresh usage</button>
  </ActionPopover>;
}
