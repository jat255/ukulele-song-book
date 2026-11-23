import {test, expect} from '@playwright/test';
import {readFileSync} from 'node:fs';

test('the full chord label can be clicked without stretching lyrics', async ({page}) => {
  const css = readFileSync('apps/web/src/workspace.css', 'utf8');
  await page.setContent(`<style>${css}</style><main class="workspace"><div class="chord-editor-lyrics"><span class="chord-editor-cell"><span class="chord-editor-chords"><button type="button">C#dim</button></span><span class="chord-editor-character">A</span></span>${'bcdefg'.split('').map(c => `<span class="chord-editor-cell"><span class="chord-editor-chords"></span><span class="chord-editor-character">${c}</span></span>`).join('')}</div></main>`);
  const button = page.getByRole('button', {name:'C#dim'});
  const box = (await button.boundingBox())!;
  const cells = page.locator('.chord-editor-cell');
  const first = (await cells.nth(0).boundingBox())!;
  const second = (await cells.nth(1).boundingBox())!;
  expect(first.width).toBeCloseTo(second.width, 1);
  for (const fraction of [0.2, 0.5, 0.8]) {
    const hitsButton = await page.evaluate(({x,y}) => document.elementFromPoint(x,y)?.closest('button')?.textContent === 'C#dim', {x:box.x + box.width * fraction,y:box.y + box.height / 2});
    expect(hitsButton).toBe(true);
  }
});
