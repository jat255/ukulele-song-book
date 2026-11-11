import React, {useEffect, useState} from 'react';

import type {components} from './api/generated';
import {ImportQueue} from './features/imports/ImportQueue';
import {Library} from './features/library/Library';
import {ArrangementEditor} from './features/library/ArrangementEditor';
import {Player} from './features/player/Player';
import {Settings} from './features/settings/Settings';
import {PrintWorkspace} from './features/print/PrintWorkspace';
import {Setlists} from './features/setlists/Setlists';
import {SetlistPlayer} from './features/setlists/SetlistPlayer';
import {SetlistPrint} from './features/setlists/SetlistPrint';

type Session = components['schemas']['SessionResponse'];

export function App() {
  const [session, setSession] = useState<Session | null>(null);
  const [loading, setLoading] = useState(true);
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  useEffect(() => {
    fetch('/api/session').then(async response => {
      if (response.ok) setSession(await response.json() as Session);
    }).catch(() => setError('Unable to reach the server.')).finally(() => setLoading(false));
  }, []);
  async function login(event: React.FormEvent) {
    event.preventDefault();
    setError('');
    try {
      const response = await fetch('/api/session', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({password})});
      setPassword('');
      if (!response.ok) { setError('Unable to sign in.'); return; }
      setSession(await response.json() as Session);
    } catch { setError('Unable to reach the server.'); }
  }
  async function logout() {
    if (!session) return;
    const response = await fetch('/api/session', {method:'DELETE', headers:{'X-CSRF-Token':session.csrf}});
    if (response.ok) setSession(null); else setError('Unable to sign out.');
  }
  if (loading) return <main>Loading…</main>;
  if (!session) return <main><h1>Sign in</h1><form onSubmit={login}><label htmlFor="password">Password</label> <input id="password" type="password" autoComplete="current-password" value={password} onChange={e => setPassword(e.target.value)} required /><button type="submit">Sign in</button></form>{error && <p role="alert">{error}</p>}</main>;
  const id = new URLSearchParams(location.search).get('id');
  if (location.pathname === '/set-player' && id) return <SetlistPlayer id={id} csrf={session.csrf} />;
  if (location.pathname === '/player' && id) return <Player id={id} csrf={session.csrf} />;
  return <main><h1>Songbook</h1><nav aria-label="Songbook"><a href="/">Library</a> <a href="/imports">Imports</a> <a href="/setlists">Setlists</a> <a href="/player">Player</a> <a href="/print">Print</a> <a href="/settings">Settings</a></nav>{location.pathname === "/set-print" && id ? <SetlistPrint id={id} csrf={session.csrf} /> : location.pathname === "/setlists" ? <Setlists csrf={session.csrf} id={id} /> : location.pathname === "/print" && id ? <PrintWorkspace id={id} csrf={session.csrf} /> : location.pathname === "/settings" ? <Settings csrf={session.csrf} /> : location.pathname === "/imports" ? <ImportQueue csrf={session.csrf} /> : location.pathname === "/edit" && id ? <ArrangementEditor id={id} csrf={session.csrf} /> : <Library csrf={session.csrf} />}<button onClick={() => void logout()}>Sign out</button>{error && <p role="alert">{error}</p>}</main>;
}
