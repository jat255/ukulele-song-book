import React, {useEffect, useState} from 'react';

type Status = {connected:boolean; email:string|null; plan:string|null; models:{id:string;name:string;default:boolean}[]};
type Usage = {primary:{used_percent:number;window_minutes:number|null;resets_at:number|null}|null;secondary:{used_percent:number;window_minutes:number|null;resets_at:number|null}|null};

export function CodexSettings({csrf}:{csrf:string}) {
  const [status,setStatus]=useState<Status|null>(null);
  const [usage,setUsage]=useState<Usage|null>(null);
  const [login,setLogin]=useState<{verification_url:string;user_code:string}|null>(null);
  const [message,setMessage]=useState('');
  const [busy,setBusy]=useState(false);
  async function refresh() {
    try {
      const attempt=await fetch('/api/codex/login-status');
      if(attempt.ok){const state=await attempt.json();if(state.state==='pending' && state.verification_url && state.user_code)setLogin({verification_url:state.verification_url,user_code:state.user_code});else if(state.state==='failed'){setLogin(null);setMessage('Codex sign-in did not complete. Please try again.');}}
      const response=await fetch('/api/codex/status');
      if(!response.ok) throw new Error('Codex connection is unavailable.');
      const value=await response.json() as Status;
      setStatus(value);
      if(value.connected) {
        setLogin(null);
        const result=await fetch('/api/codex/usage');
        setUsage(result.ok ? await result.json() as Usage : null);
      }
    } catch(error) {setMessage(error instanceof Error?error.message:'Could not check Codex.');}
  }
  useEffect(()=>{void refresh();},[]);
  useEffect(()=>{if(!login)return;const id=setInterval(()=>void refresh(),5000);return ()=>clearInterval(id);},[login]);
  async function action(path:string) {
    setBusy(true);setMessage('');
    try {
      const response=await fetch(`/api/codex/${path}`,{method:'POST',headers:{'X-CSRF-Token':csrf}});
      const result=await response.json();
      if(!response.ok) throw new Error(result.message || result.detail || 'Codex request failed.');
      if(path==='login')setLogin(result); else if(path==='cancel-login'){setLogin(null);setMessage('Sign-in cancelled.');} else {setStatus(null);setUsage(null);await refresh();}
    } catch(error){setMessage(error instanceof Error?error.message:'Codex request failed.');} finally {setBusy(false);}
  }
  return <section className="ai-settings"><h3>Codex subscription</h3><p>Use a signed-in ChatGPT account to convert PDF pages. Submitted pages use your plan and require review.</p>{status?.connected ? <><p>Connected{status.email ? ` as ${status.email}` : ''}{status.plan ? ` · ${status.plan}` : ''}</p><button disabled={busy} onClick={()=>void action('logout')}>Sign out of Codex</button>{usage ? <ul>{(['primary','secondary'] as const).map(key=>usage[key] && <li key={key}>{key==='primary'?'Primary':'Secondary'} usage: {usage[key]!.used_percent}%{usage[key]!.window_minutes ? ` of ${usage[key]!.window_minutes}-minute window` : ''}{usage[key]!.resets_at ? `, resets ${new Date(usage[key]!.resets_at!*1000).toLocaleString()}` : ''}</li>)}</ul> : <p>Usage details are unavailable.</p>}</> : <button disabled={busy || !!login} onClick={()=>void action('login')}>Sign in to Codex</button>}{login && <><p>Open <a href={login.verification_url} target="_blank" rel="noreferrer">Codex device sign-in</a> and enter <strong>{login.user_code}</strong>. This page will check for completion.</p><button disabled={busy} onClick={()=>void action('cancel-login')}>Cancel sign-in</button></>}{message && <p role="alert">{message}</p>}<button disabled={busy} onClick={()=>void refresh()}>Refresh Codex status</button></section>;
}
