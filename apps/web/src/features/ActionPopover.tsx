import React,{useId,useRef} from 'react';

/** Native light-dismiss popover, positioned without changing its trigger's layout. */
export function ActionPopover({label,className='',children,onOpen,icon}:{label:string;className?:string;children:React.ReactNode;onOpen?:()=>void;icon?:React.ReactNode}) {
 const id=useId(), panel=useRef<HTMLDivElement>(null);
 return <span className={`action-popover ${className}`}><button type="button" aria-label={label} title={icon ? label : undefined} popoverTarget={id} onClick={event=>{
  if(!panel.current?.matches(':popover-open'))onOpen?.();
  const rect=event.currentTarget.getBoundingClientRect();
  if(panel.current){panel.current.style.left=`${Math.max(8,Math.min(rect.right-300,window.innerWidth-316))}px`;panel.current.style.top=`${Math.max(8,Math.min(rect.bottom+8,window.innerHeight-320))}px`;}
 }}>{icon ?? <>{label}<span aria-hidden="true"> ▾</span></>}</button><div ref={panel} id={id} popover="auto" aria-label={`${label} options`} className="action-popover-panel">{children}</div></span>;
}
