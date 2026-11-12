import {expect,test} from 'vitest';
import {resolveDiagram} from '../src/diagrams';
test('chromatic common qualities have validated shapes',()=>{
 for(const root of ['C','C#','Db','D','D#','Eb','E','F','F#','Gb','G','G#','Ab','A','A#','Bb','B'])
 for(const quality of ['','m','7','m7','maj7','dim','aug','sus2','sus4','6','m6'])
 expect(resolveDiagram(root+quality,'high-g',[]).status,root+quality).toBe('known');
});
