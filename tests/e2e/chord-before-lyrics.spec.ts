import {test, expect} from '@playwright/test';

test('moves a chord before the first lyric and preserves the spacing in the draft and preview', async ({page}) => {
  const source="{title: Song}\n[Em]It's [G]bigger";
  await page.route('**/api/imports', route => route.fulfill({json:[{id:'job',source_id:'source',state:'needs-review',method:'direct',selection:[{pages:[]}],drafts:[{id:'draft',ordinal:0,source,revision:'rev',diagnostics:[],uncertainties:[],pages:[],accepted_id:null}]}]}));
  await page.goto('/imports');
  const line=page.getByLabel('Lyric line 1');
  await expect(line.getByRole('button',{name:/spaces? before lyrics/})).toHaveCount(0);
  await line.getByRole('button',{name:'Em',exact:true}).click();
  await expect(line.getByRole('button',{name:/spaces? before lyrics/})).toHaveCount(4);
  await expect(page.getByLabel('ChordPro draft')).toHaveValue(source);
  await line.getByRole('button',{name:'Place chord 4 spaces before lyrics'}).click();
  await expect(page.getByLabel('ChordPro draft')).toHaveValue("{title: Song}\n[Em]    It's [G]bigger");
  await expect(line.getByRole('button',{name:/spaces? before lyrics/})).toHaveCount(0);
  await expect(page.locator('.import-preview .segment').first().locator('span').last()).toHaveText("    It's");
  const em=await line.getByRole('button',{name:'Em',exact:true}).boundingBox();
  const lyric=await line.locator('.chord-editor-character').filter({hasText:/^I$/}).boundingBox();
  expect(em!.x).toBeLessThan(lyric!.x);
});

test('the nearest temporary space is selectable and cancel leaves the draft unchanged', async ({page}) => {
  const source="{title: Song}\n[Em]It's bigger";
  await page.route('**/api/imports', route => route.fulfill({json:[{id:'job',source_id:'source',state:'needs-review',method:'direct',selection:[{pages:[]}],drafts:[{id:'draft',ordinal:0,source,revision:'rev',diagnostics:[],uncertainties:[],pages:[],accepted_id:null}]}]}));
  await page.goto('/imports');
  const line=page.getByLabel('Lyric line 1');
  await line.getByRole('button',{name:'Em',exact:true}).click();
  await page.getByRole('button',{name:'Cancel'}).click();
  await expect(page.getByLabel('ChordPro draft')).toHaveValue(source);
  await expect(line.getByRole('button',{name:/spaces? before lyrics/})).toHaveCount(0);
  await line.getByRole('button',{name:'Em',exact:true}).click();
  await line.getByRole('button',{name:'Place chord 1 space before lyrics'}).click({timeout:5000});
  await expect(page.getByLabel('ChordPro draft')).toHaveValue("{title: Song}\n[Em] It's bigger");
});
