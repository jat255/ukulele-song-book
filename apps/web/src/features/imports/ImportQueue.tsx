import React, {useCallback, useEffect, useState} from 'react';
import {parseSource} from '../../../../../packages/music/src/parser';
import {MusicBlocks} from '../../music/MusicBlocks';

type Draft = {id:string; source:string; revision:string; diagnostics:string[]; uncertainties:{start:number;end:number;reason:string}[]; pages:number[]; accepted_id:string|null};
type Job = {id:string; source_id:string; state:string; drafts:Draft[]; error_code:string|null; selection:{paired_source_id?:string;paired_pages?:number[]}[]};

export function ImportQueue({csrf}: {csrf:string}) {
  const [file, setFile] = useState<File|null>(null);
  const [sources, setSources] = useState<{id:string;original_name:string;kind:string}[]>([]);
  const [paired, setPaired] = useState('');
  const [pairedPages, setPairedPages] = useState('1');
  const [jobs, setJobs] = useState<Job[]>([]);
  const [selected, setSelected] = useState<{job:Job; draft:Draft}|null>(null);
  const [text, setText] = useState('');
  const [acknowledge, setAcknowledge] = useState(false);
  const [message, setMessage] = useState('');
  const [acceptedId, setAcceptedId] = useState('');
  const [pageGroups, setPageGroups] = useState('1');
  const [crop, setCrop] = useState('');
  const [useAi, setUseAi] = useState(false);
  const [roots, setRoots] = useState<string[]>([]);
  const [root, setRoot] = useState('');
  const [files, setFiles] = useState<string[]>([]);
  const [suggestions, setSuggestions] = useState<{id:string;title:string}[]>([]);
  const [provider, setProvider] = useState<{provider:string; model:string|null; available:boolean}|null>(null);
  const document = parseSource(text);
  const parserWarnings = document.diagnostics.filter(d => d.severity !== 'info');
  const headers = {'X-CSRF-Token':csrf};
  const refresh = useCallback(async () => {
    const response = await fetch('/api/imports');
    if (response.ok) setJobs(await response.json() as Job[]);
  }, []);
  useEffect(() => { void fetch('/api/imports/sources').then(r => r.ok ? r.json() : []).then(setSources).catch(() => undefined); }, []);
  useEffect(() => { void fetch('/api/imports/roots').then(r => r.ok ? r.json() : {roots:[]}).then(data => setRoots(data.roots as string[])).catch(() => undefined); }, []);
  useEffect(() => { void fetch('/api/provider').then(r => r.ok ? r.json() : null).then(setProvider).catch(() => undefined); }, []);
  useEffect(() => { void refresh(); const timer = setInterval(() => void refresh(), 1500); return () => clearInterval(timer); }, [refresh]);
  useEffect(() => {
    if (!selected) {
      const job = jobs.find(j => j.state === 'needs-review' && j.drafts.some(d => !d.accepted_id));
      const draft = job?.drafts.find(d => !d.accepted_id);
      if (job && draft) { setSelected({job,draft}); setText(draft.source); }
    }
  }, [jobs, selected]);
  function pageSelection(pdf:boolean) {
    if (!pdf) {
      if (!paired) return [{pages:[]}];
      const pages = pairedPages.split(',').map(value => Number(value.trim()));
      if (pages.some(page => !Number.isInteger(page) || page < 1 || page > 500)) throw new Error('Invalid paired pages');
      return [{pages:[], paired_source_id:paired, paired_pages:pages}];
    }
    const coordinates = crop.trim() ? crop.split(',').map(value => Number(value.trim())) : null;
    if (coordinates && (coordinates.length !== 4 || coordinates.some(value => !Number.isFinite(value)) || coordinates[0] < 0 || coordinates[1] < 0 || coordinates[2] > 1 || coordinates[3] > 1 || coordinates[0] >= coordinates[2] || coordinates[1] >= coordinates[3])) throw new Error('Invalid crop');
    return pageGroups.split(';').map(group => {
      const pages = group.split(',').map(value => Number(value.trim()));
      if (pages.some(page => !Number.isInteger(page) || page < 1 || page > 500)) throw new Error('Invalid page');
      return {pages, rectangles:coordinates ? Object.fromEntries(pages.map(page => [String(page), coordinates])) : {}};
    });
  }
  useEffect(() => {
    if (!selected) {setSuggestions([]); return;}
    const controller = new AbortController();
    void fetch(`/api/imports/${selected.job.id}/drafts/${selected.draft.id}/suggestions`, {signal:controller.signal}).then(r => r.ok ? r.json() : []).then(setSuggestions).catch(() => undefined);
    return () => controller.abort();
  }, [selected]);
  async function upload(event:React.FormEvent) {
    event.preventDefault(); if (!file) return;
    setMessage('');
    const source = await fetch(`/api/imports/sources?filename=${encodeURIComponent(file.name)}`, {method:'POST',headers,body:file});
    if (!source.ok) {setMessage('Could not upload source.'); return;}
    const data = await source.json() as {id:string;kind:string};
    const pdf = data.kind === 'pdf';
    let selection; try {selection = pageSelection(pdf);} catch {setMessage('Enter valid page numbers and crop coordinates.'); return;}
    if (useAi && pdf) {
      if (!provider?.available || !provider.model || selection.length !== 1 || selection[0].pages.length > 5 || crop.trim()) {setMessage('AI requires an available provider and one group of at most five full pages.'); return;}
      selection = selection.map(group => ({...group, provider:provider.provider, model:provider.model, authorization:true}));
    }
    const queued = await fetch('/api/imports', {method:'POST',headers:{...headers,'Content-Type':'application/json'},body:JSON.stringify({source_id:data.id,selection,method:pdf?(useAi?'ai':'local'):'direct',idempotency_key:crypto.randomUUID()})});
    if (!queued.ok) setMessage('Could not queue import.'); else await refresh();
  }
  async function scan() {
    if (!root) return;
    const response = await fetch(`/api/imports/scan/${encodeURIComponent(root)}`);
    if (!response.ok) {setMessage('Input folder unavailable.'); return;}
    const result = await response.json() as {files:string[]}; setFiles(result.files);
  }
  async function importScanned(path:string) {
    const response = await fetch(`/api/imports/scan/${encodeURIComponent(root)}`, {method:'POST',headers:{...headers,'Content-Type':'application/json'},body:JSON.stringify({path})});
    if (!response.ok) {setMessage('Could not register source.'); return;}
    const data = await response.json() as {id:string;kind:string};
    const pdf = data.kind === 'pdf';
    let selection; try {selection = pageSelection(pdf);} catch {setMessage('Enter valid page numbers and crop coordinates.'); return;}
    if (useAi && pdf) {
      if (!provider?.available || !provider.model || selection.length !== 1 || selection[0].pages.length > 5 || crop.trim()) {setMessage('AI requires an available provider and one group of at most five full pages.'); return;}
      selection = selection.map(group => ({...group, provider:provider.provider, model:provider.model, authorization:true}));
    }
    const queued = await fetch('/api/imports', {method:'POST',headers:{...headers,'Content-Type':'application/json'},body:JSON.stringify({source_id:data.id,selection,method:pdf?(useAi?'ai':'local'):'direct',idempotency_key:crypto.randomUUID()})});
    if (!queued.ok) setMessage('Could not queue import.'); else await refresh();
  }
  async function retry(job:Job) {
    const response = await fetch(`/api/imports/${job.id}/retry`, {method:'POST',headers:{...headers,'Content-Type':'application/json'},body:JSON.stringify({authorize_ai:useAi})});
    if (!response.ok) setMessage('Retry unavailable.'); else await refresh();
  }
  async function save() {
    if (!selected) return;
    const response = await fetch(`/api/imports/${selected.job.id}/drafts/${selected.draft.id}`, {method:'PUT',headers:{...headers,'Content-Type':'application/json'},body:JSON.stringify({source:text,revision:selected.draft.revision})});
    if (!response.ok) {setMessage('Draft changed elsewhere. Your text remains here.'); return;}
    const draft = await response.json() as Draft;
    setSelected({...selected,draft}); setMessage('Draft saved.');
  }
  async function accept() {
    if (!selected) return;
    if (text !== selected.draft.source) {setMessage('Save the draft before accepting.'); return;}
    const response = await fetch(`/api/imports/${selected.job.id}/drafts/${selected.draft.id}/accept`, {method:'POST',headers:{...headers,'Content-Type':'application/json'},body:JSON.stringify({revision:selected.draft.revision,acknowledge})});
    if (!response.ok) {setMessage('Could not accept draft. Review its warnings and content.'); return;}
    const result = await response.json() as {id:string}; setAcceptedId(result.id);
    await refresh(); setSelected(null); setMessage('Arrangement accepted');
  }
  return <section><h2>Imports</h2><form onSubmit={event => void upload(event)}><label htmlFor="source">Choose source</label> <input id="source" type="file" accept=".pdf,.cho,.chordpro" onChange={event => setFile(event.target.files?.[0] ?? null)} />{file?.name.toLowerCase().endsWith('.pdf') && <><label htmlFor="pages">Pages per song (commas between pages, semicolons between songs)</label><input id="pages" value={pageGroups} onChange={event => setPageGroups(event.target.value)} /><label htmlFor="crop">Optional crop x0,y0,x1,y1 (each from 0 to 1)</label><input id="crop" value={crop} onChange={event => setCrop(event.target.value)} /></>}{file && !file.name.toLowerCase().endsWith('.pdf') && sources.some(source => source.kind === 'pdf') && <><label htmlFor="paired">Link an existing PDF for review</label><select id="paired" value={paired} onChange={event => setPaired(event.target.value)}><option value="">No linked PDF</option>{sources.filter(source => source.kind === 'pdf').map(source => <option key={source.id} value={source.id}>{source.original_name}</option>)}</select>{paired && <><label htmlFor="paired-pages">PDF pages</label><input id="paired-pages" value={pairedPages} onChange={event => setPairedPages(event.target.value)} /></>}</>}<button disabled={!file}>Import source</button></form>
    {roots.length > 0 && <section><h3>Configured input folders</h3><label htmlFor="root">Input folder</label><select id="root" value={root} onChange={event => setRoot(event.target.value)}><option value="">Choose a folder</option>{roots.map(id => <option key={id} value={id}>{id}</option>)}</select><button onClick={() => void scan()} disabled={!root}>Scan folder</button><label htmlFor="scanned-pages">Pages per PDF song (commas and semicolons)</label><input id="scanned-pages" value={pageGroups} onChange={event => setPageGroups(event.target.value)} /><ul>{files.map(path => <li key={path}>{path} <button onClick={() => void importScanned(path)}>Import</button></li>)}</ul></section>}
    {provider?.available && <label><input type="checkbox" checked={useAi} onChange={event => setUseAi(event.target.checked)} />Explicitly submit selected full PDF pages to {provider.provider} using {provider.model}; cost is unknown</label>}
    <p>Vision conversion: {provider?.available ? `${provider.provider} ${provider.model ?? ""}` : "unavailable"}. Cost estimate is unknown.</p><ul>{jobs.map(job => <li key={job.id}>{job.state}{job.error_code && `: ${job.error_code}`}{job.state === "failed" && <button onClick={() => void retry(job)}>Retry</button>}{job.drafts.filter(d => !d.accepted_id).map(draft => <button key={draft.id} onClick={() => {setSelected({job,draft}); setText(draft.source);}}>Review</button>)}</li>)}</ul>
    {selected && <section><h3>Review draft</h3>{suggestions.length > 0 && <p>Similar titles already in the library: {suggestions.map(item => item.title).join(", ")}. These will not be merged automatically.</p>}<a href={`/api/sources/${selected.job.source_id}/original`} target="_blank" rel="noreferrer">Open original</a>{selected.job.selection[0]?.paired_source_id && <><a href={`/api/sources/${selected.job.selection[0].paired_source_id}/original`} target="_blank" rel="noreferrer">Open linked PDF</a>{selected.job.selection[0].paired_pages?.map(page => <img key={`paired-${page}`} src={`/api/sources/${selected.job.selection[0].paired_source_id}/pages/${page}.png`} alt={`Linked PDF page ${page}`} style={{maxWidth:'100%'}} />)}</>}{selected.draft.pages.map(page => <img key={page} src={`/api/sources/${selected.job.source_id}/pages/${page}.png`} alt={`Original page ${page}`} style={{maxWidth:'100%'}} />)}<label htmlFor="draft">ChordPro draft</label><textarea id="draft" value={text} onChange={event => setText(event.target.value)} rows={15} /><div><button onClick={() => void save()}>Save draft</button> <button disabled={text !== selected.draft.source} onClick={() => void accept()}>Accept draft</button></div>{(selected.draft.diagnostics.length > 0 || selected.draft.uncertainties.length > 0 || parserWarnings.length > 0 || Boolean(selected.job.selection[0]?.paired_source_id)) && <><ul>{selected.draft.uncertainties.map((span,index) => <li key={`uncertain-${index}`}>Uncertain source offsets {span.start}–{span.end}: {span.reason}</li>)}{selected.draft.diagnostics.map((warning,index) => <li key={index}>{warning}</li>)}{parserWarnings.map((warning,index) => <li key={`parser-${index}`}>{warning.message}</li>)}</ul><label><input type="checkbox" checked={acknowledge} onChange={event => setAcknowledge(event.target.checked)} />I reviewed the warnings and original</label></>}<h4>Preview</h4><MusicBlocks document={document} performance={{semitones:0,spelling:'auto',capo:0,tuning:'high-g'}} mode="play" /></section>}{message && <p role="status">{message}{acceptedId && message === "Arrangement accepted" && <> <a href={`/player?id=${encodeURIComponent(acceptedId)}`}>Open arrangement</a></>}</p>}</section>;
}
