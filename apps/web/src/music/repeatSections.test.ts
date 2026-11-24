import {expect,it} from 'vitest';
import {parseSource} from '../../../../packages/music/src/parser';
import {repeatSections} from './repeatSections';

it('folds identical labeled sections and preserves changed chords and lyrics', () => {
  const verse=(line:string)=>'{start_of_verse: Verse 1}\n'+line+'\n{end_of_verse}\n';
  const document=parseSource(['[C]Sing','[C]Sing','[D]Sing','[C]Play'].map(verse).join(''));
  expect([...repeatSections(document)]).toEqual([[3,{end:5,label:'Verse 1'}]]);
});
