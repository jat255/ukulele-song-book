import {useEffect, useState} from 'react';
import './workspace.css';
import {reconcileStaging,selectAuthenticatedScope} from './offline/downloads';
import {checkDownloads} from './offline/sync';

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
  const [error, setError] = useState('');
  async function selectScope(){try{const response=await fetch('/api/downloads/identity');if(!response.ok)throw new Error();const identity=await response.json() as {libraryId:string;principalId:string};await selectAuthenticatedScope(identity.libraryId,identity.principalId);}catch{localStorage.removeItem('songbook-offline-scope');localStorage.removeItem('songbook-current-scope');}}
  useEffect(() => {
    void reconcileStaging().catch(()=>{});
    fetch('/api/session').then(async response => {
      if (response.ok) {const current=await response.json() as Session;await selectScope();setSession(current);}
    }).catch(() => {if(localStorage.getItem('songbook-offline-scope'))setSession({csrf:''});else setError('Unable to reach the server.');}).finally(() => setLoading(false));
  }, []);
  useEffect(()=>{const reconnect=()=>{void fetch('/api/session').then(async response=>{if(response.ok){const current=await response.json() as Session;await selectScope();setSession(current);await checkDownloads(current.csrf);window.dispatchEvent(new Event('songbook-sync-complete'));}}).catch(()=>{});};window.addEventListener('online',reconnect);return()=>window.removeEventListener('online',reconnect);},[]);
  if (loading) return <main className="workspace auth-page"><div className="auth-card"><p className="auth-brand">Songbook</p><p role="status">Loading…</p></div></main>;
  if (!session) return <main className="workspace auth-page"><div className="auth-card"><p className="auth-brand">Songbook</p><p role="alert">{error || 'Unable to reach the server.'}</p></div></main>;
  const id = new URLSearchParams(location.search).get('id');
  if ((location.pathname === '/player' || location.pathname === '/print') && !id) history.replaceState(null, '', '/');
  if(!session.csrf && (location.pathname==='/edit' || location.pathname==='/imports' || location.pathname==='/set-print'))return <main><p>{location.pathname==='/edit' ? 'A connection is required for editing.' : 'A connection is required for this action.'}</p></main>;
  if (location.pathname === '/set-player' && id) return <SetlistPlayer id={id} csrf={session.csrf} />;
  if (location.pathname === '/player' && id) return <Player id={id} csrf={session.csrf} />;
  return <main className="workspace"><header className="workspace-header"><h1>Songbook</h1></header><nav aria-label="Songbook"><a href="/">Library</a> <a href="/imports">Imports</a> <a href="/setlists">Setlists</a> <a href="/settings">Settings</a></nav>{location.pathname === "/set-print" && id ? <SetlistPrint id={id} csrf={session.csrf} /> : location.pathname === "/setlists" ? <Setlists csrf={session.csrf} id={id} /> : location.pathname === "/print" && id ? <PrintWorkspace id={id} csrf={session.csrf} /> : location.pathname === "/settings" ? <Settings csrf={session.csrf} /> : location.pathname === "/imports" ? <ImportQueue csrf={session.csrf} /> : location.pathname === "/edit" && id ? <ArrangementEditor id={id} csrf={session.csrf} /> : <Library csrf={session.csrf} />}{error && <p role="alert">{error}</p>}</main>;
}
