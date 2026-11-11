import {test,expect} from '@playwright/test';
import {readFileSync} from 'node:fs';

test('transposes without changing canonical source and scrolls slowly', async ({page}) => {
  const id = readFileSync('/private/tmp/songbook-auth-e2e-performance-id','utf8');
  await page.setViewportSize({width:390,height:500});
  await page.goto(`/player?id=${id}`);
  await page.getByLabel('Password').fill('synthetic test password');
  await page.getByRole('button',{name:'Sign in'}).click();
  await expect(page.getByTestId('song')).toBeVisible();
  const before = await page.evaluate(async id => (await (await fetch(`/api/arrangements/${id}`)).json()).source, id);
  await page.getByRole('button',{name:'Tools'}).click();
  await page.getByLabel('Transpose semitones').fill('2');
  await expect(page.locator('[data-chord="D"]').first()).toBeVisible();
  await page.getByLabel('Scroll speed').fill('5');
  await page.getByRole('button',{name:'Start scrolling'}).click();
  await page.getByRole('button',{name:'Close tools'}).click();
  await page.waitForTimeout(2200);
  expect(await page.evaluate(() => window.scrollY)).toBeGreaterThan(5);
  await page.getByRole('button',{name:'Tools'}).click();
  await page.getByRole('button',{name:'Pause scrolling'}).click();
  const after = await page.evaluate(async id => (await (await fetch(`/api/arrangements/${id}`)).json()).source, id);
  expect(after).toBe(before);
});

test('restores saved preferences but never restarts scrolling', async ({page}) => {
  const id = readFileSync('/private/tmp/songbook-auth-e2e-performance-id','utf8');
  await page.setViewportSize({width:390,height:500});
  await page.goto(`/player?id=${id}`);
  await page.getByLabel('Password').fill('synthetic test password');
  await page.getByRole('button',{name:'Sign in'}).click();
  await page.getByRole('button',{name:'Tools'}).click();
  await page.getByLabel('Transpose semitones').fill('3');
  await page.getByLabel('Scroll speed').fill('7');
  await page.waitForTimeout(1100);
  await page.reload();
  await page.getByRole('button',{name:'Tools'}).click();
  await expect(page.getByLabel('Transpose semitones')).toHaveValue('3');
  await expect(page.getByLabel('Scroll speed')).toHaveValue('7');
  await expect(page.getByRole('button',{name:'Start scrolling'})).toBeVisible();
  await page.getByLabel('Scroll speed').focus();
  await page.keyboard.press('Space');
  await expect(page.getByRole('button',{name:'Start scrolling'})).toBeVisible();
});

test('shows an unavailable wake lock without blocking controls', async ({page}) => {
  const id = readFileSync('/private/tmp/songbook-auth-e2e-performance-id','utf8');
  await page.addInitScript(() => Object.defineProperty(navigator,'wakeLock',{configurable:true,value:{request:async () => {throw new Error('denied');}}}));
  await page.setViewportSize({width:390,height:500});
  await page.goto(`/player?id=${id}`);
  await page.getByLabel('Password').fill('synthetic test password');
  await page.getByRole('button',{name:'Sign in'}).click();
  await page.getByRole('button',{name:'Tools'}).click();
  await page.getByRole('button',{name:'Keep screen awake'}).click();
  await expect(page.getByText('Screen wake lock is unavailable.')).toBeVisible();
  await expect(page.getByLabel('Scroll speed')).toBeVisible();
});

test('saves an explicit transposed variant while retaining original tab', async ({page}) => {
  const id = readFileSync('/private/tmp/songbook-auth-e2e-performance-id','utf8');
  await page.setViewportSize({width:390,height:500});
  await page.goto(`/player?id=${id}`);
  await page.getByLabel('Password').fill('synthetic test password');
  await page.getByRole('button',{name:'Sign in'}).click();
  await expect(page.getByTestId('song')).toBeVisible();
  await page.getByRole('button',{name:'Tools'}).click();
  await page.getByLabel('Transpose semitones').fill('2');
  page.once('dialog', dialog => void dialog.accept());
  await page.getByRole('button',{name:'Save transposed variant'}).click();
  await expect.poll(() => new URL(page.url()).searchParams.get('id')).not.toBe(id);
  const newId=new URL(page.url()).searchParams.get('id');
  const result=await page.evaluate(async value => (await (await fetch(`/api/arrangements/${value}`)).json()),newId);
  expect(result.source).toContain('[D]Music');
  expect(result.source).toContain('{start_of_tab}');
});

test('keeps adjacent transposed chords distinct at phone width', async ({page}) => {
  const id = readFileSync('/private/tmp/songbook-auth-e2e-performance-id','utf8');
  await page.setViewportSize({width:320,height:700});
  await page.goto(`/player?id=${id}`);
  await page.getByLabel('Password').fill('synthetic test password');
  await page.getByRole('button',{name:'Sign in'}).click();
  await page.getByRole('button',{name:'Tools'}).click();
  await page.getByLabel('Transpose semitones').fill('1');
  await page.getByRole('button',{name:'Close tools'}).click();
  const boxes=await page.locator('.lyric-line').nth(1).locator('.chord').evaluateAll(nodes=>nodes.map(node=>{const box=node.getBoundingClientRect();return {left:box.left,right:box.right,top:box.top}}));
  expect(boxes).toHaveLength(4);
  for(let index=1;index<boxes.length;index++) if (Math.abs(boxes[index].top-boxes[index-1].top)<2) expect(boxes[index].left).toBeGreaterThan(boxes[index-1].right);
});

test('manual scrolling and a layout change pause automatic scrolling', async ({page}) => {
  const id=readFileSync('/private/tmp/songbook-auth-e2e-performance-id','utf8');
  await page.setViewportSize({width:390,height:500});
  await page.goto(`/player?id=${id}`);
  await page.getByLabel('Password').fill('synthetic test password');
  await page.getByRole('button',{name:'Sign in'}).click();
  await page.getByRole('button',{name:'Tools'}).click();
  await page.getByRole('button',{name:'Start scrolling'}).click();
  await page.getByLabel(/Text size/).fill('25');
  await expect(page.getByRole('button',{name:'Start scrolling'})).toBeVisible();
  await page.getByRole('button',{name:'Start scrolling'}).click();
  await page.getByRole('button',{name:'Close tools'}).click();
  await page.mouse.wheel(0,80);
  await page.getByRole('button',{name:'Tools'}).click();
  await expect(page.getByRole('button',{name:'Start scrolling'})).toBeVisible();
});
