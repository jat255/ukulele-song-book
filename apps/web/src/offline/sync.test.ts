import {describe,expect,it} from 'vitest';
import {mergePreferenceGroup,nextPreferenceTimestamp,fromServerEnvelope,toServerEnvelope} from './preferences';

describe('preference reconciliation',()=>{
  it('converges by integer milliseconds then device id',()=>{
    const a={schemaVersion:1 as const,value:'a',updatedAtMs:1700000000001,deviceId:'a'};
    const b={schemaVersion:1 as const,value:'b',updatedAtMs:1700000000001,deviceId:'b'};
    expect(mergePreferenceGroup(a,b)).toEqual(b);
    expect(mergePreferenceGroup(b,a)).toEqual(b);
    expect(mergePreferenceGroup(b,b)).toEqual(b);
    expect(nextPreferenceTimestamp(1000,999)).toBe(1001);
  });
  it('converts existing seconds at the wire boundary',()=>{
    const converted=fromServerEnvelope({value:'x',updated_at:1700000000.123,device_id:'phone'});
    expect(converted.updatedAtMs).toBe(1700000000123);
    expect(toServerEnvelope(converted)).toEqual({value:'x',updated_at:1700000000.123,device_id:'phone'});
  });
});
