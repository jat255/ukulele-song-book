import {test,expect} from '@playwright/test';
test('renders chord anchors and literal tab after mounting', async ({page}) => {
  await page.setViewportSize({width:390,height:844});
  await page.goto('/?feasibility');
  await page.waitForFunction(() => typeof (window as any).renderSong === 'function');
  await expect(page.locator('[data-testid="song"]')).toBeVisible();
  const segment=page.locator('[data-chord="C"]');
  await expect(segment).toContainText('Lan');
  await expect(page.locator('[data-chord="D/F#"]')).toContainText('tern');
  await expect(page.locator('[data-testid="tab"]')).toHaveCSS('white-space','pre');
});
test('long lyric segments wrap within a narrow screen', async ({page}) => {
  await page.setViewportSize({width:320,height:844});
  await page.goto('/?feasibility');
  await page.waitForFunction(() => typeof (window as any).renderSong === 'function');
  await page.evaluate(() => (window as any).renderSong('[C]A long line of words that should wrap naturally within a narrow screen without any horizontal clipping','play',20,1));
  await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
});
test('shows artist and capo from the source', async ({page}) => {
  await page.goto('/?feasibility');
  await page.waitForFunction(() => typeof (window as any).renderSong === 'function');
  await page.evaluate(() => (window as any).renderSong('{title: Example}\n{artist: Example Artist}\n{capo: 2}\n[C]Music','play',20,1));
  await expect(page.getByText('Example Artist')).toBeVisible();
  await expect(page.getByText('Capo 2')).toBeVisible();
});
test('shows unsupported source constructs as warnings', async ({page}) => {
  await page.goto('/?feasibility');
  await page.waitForFunction(() => typeof (window as any).renderSong === 'function');
  await page.evaluate(() => (window as any).renderSong('{future: keep}\n[C]Hi','play',20,1));
  await expect(page.getByText('{future: keep}')).toBeVisible();
});
test('does not execute source markup', async ({page}) => {
  await page.goto('/?feasibility');
  await page.waitForFunction(() => typeof (window as any).renderSong === 'function');
  await page.evaluate(() => (window as any).renderSong('[C]<img src=x onerror="window.pwned=1">','play',20,1));
  await expect(page.locator('img')).toHaveCount(0);
  expect(await page.evaluate(() => (window as any).pwned)).toBeUndefined();
});
test('adjacent chord-only anchors remain visually distinct', async ({page}) => {
  await page.goto('/?feasibility');
  await page.waitForFunction(() => typeof (window as any).renderSong === 'function');
  await page.evaluate(() => (window as any).renderSong('[D][Em][G][A]','play',20,1));
  const boxes=await page.locator('.chord').evaluateAll(nodes=>nodes.map(n=>{const r=n.getBoundingClientRect();return {left:r.left,right:r.right}}));
  expect(boxes.length).toBe(4);
  for(let i=1;i<boxes.length;i++) expect(boxes[i].left-boxes[i-1].right).toBeGreaterThan(2);
});
test('chords with only whitespace between them stay distinct', async ({page}) => {
  await page.goto('/?feasibility');
  await page.waitForFunction(() => typeof (window as any).renderSong === 'function');
  await page.evaluate(() => (window as any).renderSong('[D] [Em] [G] [A]','play',20,1));
  const boxes=await page.locator('.chord').evaluateAll(nodes=>nodes.map(n=>{const r=n.getBoundingClientRect();return {left:r.left,right:r.right}}));
  for(let i=1;i<boxes.length;i++) expect(boxes[i].left-boxes[i-1].right).toBeGreaterThan(2);
});
test('print render honors the requested font size', async ({page}) => {
  await page.goto('/?feasibility');
  await page.waitForFunction(() => typeof (window as any).renderSong === 'function');
  await page.evaluate(() => (window as any).renderSong('[C]Example','print',14,1));
  await expect(page.locator('[data-testid="song"]')).toHaveCSS('font-size','18.6667px');
});
test('shows source subtitle', async ({page}) => {
  await page.goto('/?feasibility');
  await page.waitForFunction(() => typeof (window as any).renderSong === 'function');
  await page.evaluate(() => (window as any).renderSong('{title: Example}\n{subtitle: Arrangement note}\n[C]Music','play',20,1));
  await expect(page.getByText('Arrangement note')).toBeVisible();
});
