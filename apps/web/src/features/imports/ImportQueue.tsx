import {useCallback, useEffect, useState} from 'react';
import {parseSource} from '../../../../../packages/music/src/parser';
import {MusicBlocks} from '../../music/MusicBlocks';
import {CodexBatchImport} from './CodexBatchImport';
import {CodexActivity} from './CodexActivity';
import {ChordPlacementEditor} from './ChordPlacementEditor';

type Draft = {provider_metadata?:{model?:string;usage?:{total?:{inputTokens?:number;outputTokens?:number;cachedInputTokens?:number}}};ordinal:number;id:string; source:string; revision:string; diagnostics:string[]; uncertainties:{start:number;end:number;reason:string}[]; pages:number[]; accepted_id:string|null};
type Selection={provider?:string;model?:string;pages:number[];all_pages?:boolean;crop?:number[];rectangles?:Record<string,number[]>;paired_source_id?:string;paired_pages?:number[]};
type Job = {method:string;id:string; source_id:string; state:string; drafts:Draft[]; error_code:string|null;error_details?:{message:string;hint:string;retryable:boolean}|null; selection:Selection[]};

export function ImportQueue({csrf}: {csrf:string}) {
  const [sources, setSources] = useState<{id:string;original_name:string;kind:string}[]>([]);
  const [jobs, setJobs] = useState<Job[]>([]);
  const [selected, setSelected] = useState<{job:Job; draft:Draft}|null>(null);
  const [text, setText] = useState('');
  const [acknowledge, setAcknowledge] = useState(false);
  const [message, setMessage] = useState('');
  const [acceptedId, setAcceptedId] = useState('');
  const [suggestions, setSuggestions] = useState<{id:string;title:string}[]>([]);
  const [codexModels,setCodexModels]=useState<{id:string;name:string;default:boolean}[]>([]);
  const [codexLoading,setCodexLoading]=useState(true);
  const document = parseSource(text);
  const parserWarnings = document.diagnostics.filter(d => d.severity !== 'info');
  const headers = {'X-CSRF-Token':csrf};
  const refresh = useCallback(async () => {
    const response = await fetch('/api/imports');
    if (response.ok) setJobs(await response.json() as Job[]);
    const sourceResponse=await fetch('/api/imports/sources');
    if(sourceResponse.ok)setSources(await sourceResponse.json());
  }, []);
  useEffect(() => { void fetch('/api/imports/sources').then(r => r.ok ? r.json() : []).then(setSources).catch(() => undefined); }, []);
  useEffect(() => {void fetch('/api/codex/status').then(r=>r.ok?r.json():null).then(data=>{if(data?.connected)setCodexModels(data.models ?? []);}).catch(()=>undefined).finally(()=>setCodexLoading(false));}, []);
  useEffect(() => { void refresh(); const timer = setInterval(() => void refresh(), 1500); return () => clearInterval(timer); }, [refresh]);
  useEffect(() => {
    if (!selected) {
      const job = jobs.find(j => j.state === 'needs-review' && j.drafts.some(d => !d.accepted_id));
      const draft = job?.drafts.find(d => !d.accepted_id);
      if (job && draft) { setSelected({job,draft}); setText(draft.source);setAcknowledge(false); }
    }
  }, [jobs, selected]);
  useEffect(() => {
    if (!selected) {setSuggestions([]); return;}
    const controller = new AbortController();
    void fetch(`/api/imports/${selected.job.id}/drafts/${selected.draft.id}/suggestions`, {signal:controller.signal}).then(r => r.ok ? r.json() : []).then(setSuggestions).catch(() => undefined);
    return () => controller.abort();
  }, [selected]);
  async function discard(job:Job) {
    if(!window.confirm('Discard the unaccepted drafts in this attempt? The original file and accepted songs will be kept.'))return;
    const pending=job.drafts.filter(draft=>!draft.accepted_id);
    const response=await fetch(`/api/imports/${job.id}`,{method:'DELETE',headers:{...headers,'Content-Type':'application/json'},body:JSON.stringify({state:job.state,drafts:Object.fromEntries(pending.map(draft=>[draft.id,draft.revision]))})});
    if(!response.ok){setMessage(response.status===409?'Import changed or is still processing. Refresh and try again.':'Could not discard import.');return;}
    await refresh();if(selected?.job.id===job.id){setSelected(null);setText('');setAcknowledge(false);}
    setMessage('Unaccepted drafts discarded. Originals and accepted songs were kept.');
  }
  async function retry(job:Job) {
    const response = await fetch(`/api/imports/${job.id}/retry`, {method:'POST',headers:{...headers,'Content-Type':'application/json'},body:JSON.stringify({authorize_ai:job.method==='ai'})});
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
  const hasOriginalPages=!!selected && (selected.draft.pages.length>0 || !!selected.job.selection[selected.draft.ordinal]?.paired_pages?.length);
  return <section className="imports-page"><h2>Imports</h2><p className="imports-intro">Convert PDFs with Codex, then review each draft before adding it to your library.</p>{codexModels.length > 0 ? <CodexBatchImport csrf={csrf} models={codexModels} onImported={()=>void refresh()}/> : <p>{codexLoading ? 'Checking Codex connection…' : <>Connect Codex in <a href="/settings">Settings</a> to convert PDFs.</>}</p>}
    {message && <p role="status" className="import-message">{message}{acceptedId && message === "Arrangement accepted" && <> <a href={`/player?id=${encodeURIComponent(acceptedId)}`}>Open arrangement</a></>}</p>}
    <section className="import-queue"><div className="import-queue-heading"><h3>Import queue</h3><span>{jobs.length} {jobs.length===1?'import':'imports'}</span></div><div className="import-table-scroll"><table aria-label="Import queue"><thead><tr><th scope="col">Source</th><th scope="col">Status</th><th scope="col">Actions</th></tr></thead><tbody>{jobs.map(job => <tr key={job.id}><th scope="row">{sources.find(source=>source.id===job.source_id)?.original_name ?? parseSource(job.drafts[0]?.source ?? '').metadata.title?.[0] ?? 'Untitled source'}</th><td><span className={`import-state import-state--${job.state}`}>{({'needs-review':'Needs review',queued:'Queued',processing:'Processing',accepted:'Accepted',failed:'Failed'} as Record<string,string>)[job.state] ?? job.state}</span>{job.selection.some(part=>part.provider==='codex') && <CodexActivity jobId={job.id} state={job.state}/>}{job.error_code && <div className="import-failure"><strong>{job.error_details?.message ?? 'Conversion failed; no specific cause was recorded.'}</strong><p>{job.error_details?.hint ?? 'Retry the conversion or choose the PDF again.'}</p><small>Reference: {job.error_code}</small></div>}</td><td>{job.state === "failed" && (job.error_details?.retryable!==false || job.selection.some(part=>part.provider==='codex')) && <button onClick={() => void retry(job)}>Retry</button>}{job.state!=='processing' && job.state!=='accepted' && <button onClick={()=>void discard(job)}>Discard attempt</button>}{job.drafts.map(draft=>draft.accepted_id ? <a key={draft.id} href={`/player?id=${encodeURIComponent(draft.accepted_id)}`}>Open song</a> : <button key={draft.id} onClick={() => {setSelected({job,draft}); setText(draft.source);setAcknowledge(false);}}>Review</button>)}</td></tr>)}</tbody></table>{!jobs.length && <p>No imports yet. Choose a source file to get started.</p>}</div></section>
    {selected && <section className="import-review"><h3>Review draft</h3><p>Compare the source with the editable draft. Save corrections before accepting.</p>{selected.draft.provider_metadata?.usage?.total && <p>Codex usage ({selected.draft.provider_metadata.model}): {selected.draft.provider_metadata.usage.total.inputTokens ?? 'unavailable'} input tokens, {selected.draft.provider_metadata.usage.total.outputTokens ?? 'unavailable'} output tokens, {selected.draft.provider_metadata.usage.total.cachedInputTokens ?? 'unavailable'} cached input tokens.</p>}{suggestions.length > 0 && <p>Similar titles already in the library: {suggestions.map(item => item.title).join(", ")}. These will not be merged automatically.</p>}<div className="import-source-links"><a href={`/api/sources/${selected.job.source_id}/original`} target="_blank" rel="noreferrer">Open original</a>{selected.job.selection[selected.draft.ordinal]?.paired_source_id && <a href={`/api/sources/${selected.job.selection[selected.draft.ordinal].paired_source_id}/original`} target="_blank" rel="noreferrer">Open linked PDF</a>}</div><div className={`import-review-grid${hasOriginalPages?'':' import-review-grid--text'}`}>{hasOriginalPages && <aside className="import-originals" aria-label="Original pages">{selected.job.selection[selected.draft.ordinal]?.paired_pages?.map(page => <img key={`paired-${page}`} src={`/api/sources/${selected.job.selection[selected.draft.ordinal].paired_source_id}/pages/${page}.png`} alt={`Linked PDF page ${page}`} />)}{selected.draft.pages.map(page => <img key={page} src={`/api/sources/${selected.job.source_id}/pages/${page}.png`} alt={`Original page ${page}`} />)}</aside>}<div className="import-workbench"><ChordPlacementEditor key={selected.draft.id} source={text} onChange={setText}/><div className="import-field"><label htmlFor="draft">ChordPro draft</label><textarea id="draft" value={text} onChange={event => setText(event.target.value)} rows={15} /></div><div className="import-review-actions"><button onClick={() => void save()}>Save draft</button><button disabled={text !== selected.draft.source} onClick={() => void accept()}>Accept draft</button></div>{(selected.draft.diagnostics.length > 0 || selected.draft.uncertainties.length > 0 || parserWarnings.length > 0 || Boolean(selected.job.selection[selected.draft.ordinal]?.paired_source_id)) && <div className="import-warnings"><ul>{selected.draft.uncertainties.map((span,index) => <li key={`uncertain-${index}`}>Uncertain source offsets {span.start}–{span.end}: {span.reason}</li>)}{selected.draft.diagnostics.map((warning,index) => <li key={index}>{warning}</li>)}{parserWarnings.map((warning,index) => <li key={`parser-${index}`}>{warning.message}</li>)}</ul><label><input type="checkbox" checked={acknowledge} onChange={event => setAcknowledge(event.target.checked)} />I reviewed the warnings and original</label></div>}<section className="import-preview"><h4>Preview</h4><MusicBlocks document={document} performance={{semitones:0,spelling:'auto',capo:0,tuning:'high-g'}} mode="play" /></section></div></div></section>}</section>;
}
