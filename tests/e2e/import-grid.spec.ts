import {test, expect} from '@playwright/test';

test('review renders chord grid beats and bars without unsupported warnings', async ({page}) => {
  const source='{title: Grid song}\n{start_of_grid}\n| C . Gm7 . | F~Am . C . |\n{end_of_grid}\n';
  await page.route('**/api/imports', route => route.fulfill({json:[{id:'grid-job',source_id:'source',state:'needs-review',method:'direct',selection:[{pages:[]}],drafts:[{id:'grid-draft',ordinal:0,source,revision:'rev',diagnostics:[],uncertainties:[],pages:[],accepted_id:null}]}]}));
  await page.goto('/imports');
  const grid=page.locator('.import-preview .chord-grid-line');
  await expect(grid).toContainText('Gm7');
  await expect(grid.locator('.chord-grid-cell')).toHaveCount(8);
  await expect(grid.locator('.chord-grid-bar')).toHaveCount(3);
  const chord=grid.locator('.chord').filter({hasText:'Gm7'});
  await expect(chord).toHaveAttribute('tabindex', '0');
  await chord.focus();
  await expect(page.getByRole('tooltip')).toContainText('Gm7');
  await expect(grid.locator('.chord-grid-cell').filter({hasText:'F~Am'}).locator('.chord')).toHaveCount(2);
  await expect(grid.locator('.chord-grid-cell').filter({hasText:'.'}).locator('.chord')).toHaveCount(0);
  await expect(page.getByText('Unsupported environment: start_of_grid')).toHaveCount(0);
});
