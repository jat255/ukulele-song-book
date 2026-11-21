import {parseSource} from './parser';
import {applySourceEdits} from './source';
import type {SourceSpan} from './model';

export type EditableLine = {span: SourceSpan; lyrics:string; boundaries:number[]; chords:{id:number;offset:number;name:string}[]; editable:boolean; reason?:string};
type Edit = {kind:'add';offset:number;name:string}|{kind:'move';id:number;offset:number}|{kind:'rename';id:number;name:string}|{kind:'remove';id:number};

export function getEditableLines(source:string):EditableLine[] {
  return parseSource(source).blocks.filter(block => block.kind === 'lyric').map(block => {
    const raw = source.slice(block.span.start,block.span.end).replace(/\r\n$|[\r\n]$/, '');
    let lyrics = '', cursor = 0;
    const chords:EditableLine['chords'] = [];
    for (const match of raw.matchAll(/\[([^\]]+)\]/g)) {
      lyrics += raw.slice(cursor,match.index);
      chords.push({id:chords.length, offset:lyrics.length, name:match[1]});
      cursor = match.index! + match[0].length;
    }
    lyrics += raw.slice(cursor);
    const editable = !/[\[\]{}]/.test(lyrics) && !/^\s*(?:#|[A-Ga-g](?:#|b)?\s*\|)/.test(raw);
    const segmenter = new Intl.Segmenter(undefined,{granularity:'grapheme'});
    const boundaries = [...segmenter.segment(lyrics)].map(part => part.index);
    boundaries.push(lyrics.length);
    return {span:{start:block.span.start,end:block.span.start+raw.length},lyrics,boundaries,chords,editable,reason:editable ? undefined : 'Edit this line in ChordPro source.'};
  });
}

export function applyChordEdit(source:string, span:SourceSpan, edit:Edit):string {
  const line = getEditableLines(source).find(item => item.span.start===span.start && item.span.end===span.end);
  if (!line?.editable) throw new Error('Line cannot be edited graphically');
  const chords = line.chords.map(chord => ({...chord}));
  if ('offset' in edit && !line.boundaries.includes(edit.offset)) throw new Error('Invalid lyric position');
  if ('name' in edit && (!edit.name.trim() || /[\[\]{}\r\n]/.test(edit.name))) throw new Error('Invalid chord name');
  if (edit.kind === 'add') chords.push({id:chords.length,offset:edit.offset,name:edit.name});
  else {
    const index = chords.findIndex(chord => chord.id===edit.id);
    if (index<0) throw new Error('Chord no longer exists');
    if (edit.kind === 'remove') chords.splice(index,1);
    else if (edit.kind === 'move') chords[index].offset=edit.offset;
    else chords[index].name=edit.name;
  }
  chords.sort((a,b) => a.offset-b.offset || a.id-b.id);
  let text='', position=0;
  for (const chord of chords) { text += line.lyrics.slice(position,chord.offset)+`[${chord.name}]`; position=chord.offset; }
  text += line.lyrics.slice(position);
  return applySourceEdits(source,[{span,text}]);
}
