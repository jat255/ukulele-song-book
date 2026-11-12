import React,{useEffect,useId,useLayoutEffect,useRef,useState} from 'react';
import {createPortal} from 'react-dom';
import type {DiagramResult} from '../../../../../packages/music/src/diagrams';
import {ChordDiagram} from './ChordDiagram';

/** Keep chord help outside music clipping/column contexts and within the viewport. */
export function ChordHint({chord,diagram}:{chord:string;diagram:DiagramResult}) {
 const id=useId(),anchor=useRef<HTMLSpanElement>(null),panel=useRef<HTMLDivElement>(null);
 const timer=useRef<ReturnType<typeof setTimeout>|undefined>(undefined);
 const [open,setOpen]=useState(false),[position,setPosition]=useState({left:-10000,top:0});
 const cancel=()=>{if(timer.current)clearTimeout(timer.current);};
 const show=()=>{cancel();setOpen(true);};
 const hide=()=>{cancel();timer.current=setTimeout(()=>setOpen(false),120);};
 useEffect(()=>()=>{if(timer.current)clearTimeout(timer.current);},[]);
 useLayoutEffect(()=>{
  if(!open || !anchor.current || !panel.current)return;
  const rect=anchor.current.getBoundingClientRect(),size=panel.current.getBoundingClientRect();
  setPosition({left:Math.max(8,Math.min(rect.left,innerWidth-size.width-8)),top:Math.max(8,rect.bottom+size.height+8<=innerHeight ? rect.bottom+6 : rect.top-size.height-6)});
 },[open,chord,diagram]);
 useEffect(()=>{
  if(!open)return;
  const dismiss=()=>setOpen(false),key=(event:KeyboardEvent)=>{if(event.key==='Escape')dismiss();};
  window.addEventListener('scroll',dismiss,true);window.addEventListener('resize',dismiss);window.addEventListener('keydown',key);
  return()=>{window.removeEventListener('scroll',dismiss,true);window.removeEventListener('resize',dismiss);window.removeEventListener('keydown',key);};
 },[open]);
 return <span className="chord" tabIndex={0} ref={anchor} aria-describedby={open?id:undefined} onPointerEnter={show} onPointerLeave={hide} onFocus={show} onBlur={hide}>{chord}{open && createPortal(<div ref={panel} id={id} role="tooltip" className="chord-popover" style={position} onPointerEnter={cancel} onPointerLeave={hide}><ul><ChordDiagram chord={chord} diagram={diagram}/></ul></div>,document.body)}</span>;
}
