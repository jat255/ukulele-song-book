import {AISettings} from './AISettings';
import {CodexSettings} from './CodexSettings';
import React from 'react';
import {usePreferences} from './preferences';

export function Settings({csrf}:{csrf:string}) {
  const prefs=usePreferences('defaults',csrf);
  if (!prefs.ready) return <section className="settings-page">Loading defaults…</section>;
  const play=prefs.data.groups.play.value, print=prefs.data.groups.print.value;
  return <section className="settings-page"><h2>Default settings</h2><p>These defaults apply to arrangements without saved settings.</p><div className="settings-grid"><fieldset><legend>Playing defaults</legend><p>Text and scrolling for new songs.</p><label htmlFor="default-font">Playing text size</label><input id="default-font" type="number" min="12" max="40" value={play.fontPx} onChange={event => prefs.change('play',{...play,fontPx:Math.max(12,Math.min(40,Number(event.target.value)))})}/><label htmlFor="default-speed">Scroll speed</label><input id="default-speed" type="number" min="1" max="100" value={play.scrollPxPerSecond} onChange={event => prefs.change('play',{...play,scrollPxPerSecond:Math.max(1,Math.min(100,Number(event.target.value)))})}/></fieldset><fieldset><legend>Printing defaults</legend><p>Paper and type size for printed arrangements.</p><label htmlFor="default-paper">Print paper</label><select id="default-paper" value={print.paper} onChange={event => prefs.change('print',{...print,paper:event.target.value as 'Letter'|'A4'})}><option>Letter</option><option>A4</option></select><label htmlFor="default-print-font">Print text size</label><input id="default-print-font" type="number" min="8" max="24" value={print.fontPt} onChange={event => prefs.change('print',{...print,fontPt:Math.max(8,Math.min(24,Number(event.target.value)))})}/></fieldset></div><CodexSettings csrf={csrf}/><AISettings csrf={csrf}/>{prefs.error && <p role="alert">{prefs.error}</p>}</section>;
}
