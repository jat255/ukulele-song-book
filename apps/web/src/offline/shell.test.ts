import {afterEach,expect,it,vi} from 'vitest';
import {prepareShell} from './shell';

vi.mock('./downloads',()=>({registerStage:vi.fn(),discardStage:vi.fn()}));
afterEach(()=>vi.unstubAllGlobals());

it('prepares the offline shell even if the browser requested a missing fallback favicon',async()=>{
  const requests=vi.fn(async(path:string)=>new Response('',{status:path==='/favicon.ico' ? 404 : 200}));
  vi.stubGlobal('fetch',requests);
  vi.stubGlobal('navigator',{serviceWorker:{register:vi.fn(),ready:Promise.resolve()}});
  vi.stubGlobal('location',{origin:'https://songbook.test'});
  vi.stubGlobal('performance',{getEntriesByType:()=>[
    {name:'https://songbook.test/favicon.ico'},
    {name:'https://songbook.test/assets/index.js'},
  ]});
  vi.stubGlobal('caches',{open:async()=>({put:vi.fn()})});

  await expect(prepareShell()).resolves.toMatch(/^songbook-shell-data-/);
  expect(requests).not.toHaveBeenCalledWith('/favicon.ico');
  expect(requests).toHaveBeenCalledWith('/assets/index.js');
  expect(requests).toHaveBeenCalledWith('/icon.svg');
});
