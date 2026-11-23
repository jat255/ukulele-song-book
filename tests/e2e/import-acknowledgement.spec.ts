import {test, expect} from '@playwright/test';

test('accepts a draft with warnings without a confirmation checkbox', async ({page}) => {
  const draft = {id:'draft', ordinal:0, source:'{title: Review}\n[C]Hello', revision:'rev', diagnostics:['Check the original'], uncertainties:[], pages:[], accepted_id:null};
  await page.route('**/api/imports', route => route.fulfill({json:[{id:'job', source_id:'source', state:'needs-review', method:'direct', drafts:[draft], selection:[{pages:[]}], error_code:null}]}));
  await page.route('**/api/imports/job/drafts/draft/suggestions', route => route.fulfill({json:[]}));
  let accepted: unknown;
  await page.route('**/api/imports/job/drafts/draft/accept', async route => {
    accepted = route.request().postDataJSON();
    await route.fulfill({json:{id:'arrangement'}});
  });
  await page.goto('/imports');
  await expect(page.getByText('Check the original')).toBeVisible();
  await expect(page.getByLabel('I reviewed the warnings and original')).toHaveCount(0);
  await page.getByRole('button', {name:'Accept draft'}).click();
  await expect(page.getByText('Arrangement accepted')).toBeVisible();
  expect(accepted).toEqual({revision:'rev', acknowledge:true});
});
