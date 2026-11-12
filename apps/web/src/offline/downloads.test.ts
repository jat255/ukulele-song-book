import {describe,expect,it} from 'vitest';
import {verifySnapshot} from './downloads';

describe('snapshot integrity',()=>{
  it('rejects changed bytes and wrong length even when metadata claims a revision',async()=>{
    const source='[C]Line';
    const hash=Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',new TextEncoder().encode(source))),b=>b.toString(16).padStart(2,'0')).join('');
    const snapshot={id:'a',song_id:'s',revision:hash,source,sha256:hash,size:source.length,mime:'text/plain'};
    expect(await verifySnapshot(snapshot)).toBe(true);
    expect(await verifySnapshot({...snapshot,source:'[D]Line'})).toBe(false);
    expect(await verifySnapshot({...snapshot,size:source.length+1})).toBe(false);
  });
});
