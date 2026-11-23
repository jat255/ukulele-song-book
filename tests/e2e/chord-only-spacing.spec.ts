import {test, expect} from '@playwright/test';

test('chord-only lines show separately selectable chords in order', async ({page}) => {
  const source = '{title: Song}\n[Dsus2] [Bb] [Dsus2] [Bb]\n[C][G]\n[C]Hello';
  await page.route('**/api/imports', route => route.fulfill({json:[{id:'job',source_id:'source',state:'needs-review',method:'direct',selection:[{pages:[]}],drafts:[{id:'draft',ordinal:0,source,revision:'rev',diagnostics:[],uncertainties:[],pages:[],accepted_id:null}]}]}));
  await page.goto('/imports');
  for (const label of ['Lyric line 1', 'Lyric line 2']) {
    const line = page.getByLabel(label);
    const buttons = line.locator('button[aria-pressed]');
    const count = label === 'Lyric line 1' ? 4 : 2;
    await expect(buttons).toHaveCount(count);
    let previousRight = 0;
    for (let i=0; i<count; i++) {
      const button = buttons.nth(i);
      const box = (await button.boundingBox())!;
      expect(box.x).toBeGreaterThanOrEqual(previousRight);
      previousRight = box.x + box.width;
    }
    for (let i=0; i<count; i++) {
      const button = buttons.nth(i);
      await button.click();
      await expect(button).toHaveAttribute('aria-pressed', 'true');
      await page.getByRole('button', {name:'Cancel'}).click();
    }
  }
});
