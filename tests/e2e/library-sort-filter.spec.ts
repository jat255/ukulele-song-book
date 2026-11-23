import {test, expect} from '@playwright/test';

test('sorts titles and artists and filters an exact artist on desktop and mobile', async ({page}) => {
  await page.route('**/api/library?*', route => route.fulfill({json:[
    {id:'1',song_id:'1',revision:'a',metadata_revision:0,source_only:false,title:"(You're the) Devil in Disguise",artist:'Elvis Presley',favorite:false,tags:[],notes:''},
    {id:'2',song_id:'2',revision:'a',metadata_revision:0,source_only:false,title:'Across the Universe',artist:'The Beatles',favorite:false,tags:[],notes:''},
    {id:'3',song_id:'3',revision:'a',metadata_revision:0,source_only:false,title:'Blue Moon',artist:'Elvis Presley',favorite:false,tags:[],notes:''},
    {id:'4',song_id:'4',revision:'a',metadata_revision:0,source_only:false,title:'Yesterday',artist:'Elvis Presley Jr',favorite:false,tags:[],notes:''},
  ]}));
  await page.goto('/');
  const titles=page.locator('.library-table tbody th a');
  await expect(titles).toHaveText(['Across the Universe','Blue Moon','Yesterday',"(You're the) Devil in Disguise"]);
  await page.getByRole('button',{name:'Sort by Artist'}).click();
  await expect(titles).toHaveText(['Blue Moon',"(You're the) Devil in Disguise",'Yesterday','Across the Universe']);
  await page.getByRole('button',{name:'Sort by Artist'}).click();
  await expect(titles.first()).toHaveText('Across the Universe');
  await page.getByRole('button',{name:'Filter by Elvis Presley',exact:true}).first().click();
  await expect(titles).toHaveCount(2);
  const searchField=page.locator('.library-search-field');
  await expect(searchField.getByText('Artist: Elvis Presley')).toBeVisible();
  await expect(searchField.getByRole('button',{name:'Clear artist filter'})).toHaveText('×');
  await page.getByLabel('Search').fill('Blue');
  await expect(page.getByLabel('Search')).toHaveValue('Blue');
  await expect(page.getByText('Yesterday',{exact:true})).toHaveCount(0);
  await page.getByRole('button',{name:'Clear artist filter'}).click();
  await expect(titles).toHaveCount(4);
  await page.setViewportSize({width:390,height:800});
  await page.getByLabel('Sort library').selectOption('title-asc');
  await expect(titles.first()).toHaveText('Across the Universe');
});

test('clicking a tag filters songs and shows a removable chip in the tag field', async ({page}) => {
  await page.route('**/api/library?*', route => {
    const tag=new URL(route.request().url()).searchParams.getAll('tag');
    const songs=[
      {id:'a',song_id:'a',revision:'a',metadata_revision:0,source_only:false,title:'Blue Moon',artist:'Elvis',favorite:false,tags:['Jazz'],notes:''},
      {id:'b',song_id:'b',revision:'a',metadata_revision:0,source_only:false,title:'Yesterday',artist:'Beatles',favorite:false,tags:['Pop'],notes:''},
    ];
    return route.fulfill({json:songs.filter(song=>tag.every(value=>song.tags.includes(value)))});
  });
  await page.goto('/');
  await page.getByRole('button',{name:'Filter by tag Jazz'}).click();
  await expect(page.getByRole('link',{name:'Yesterday',exact:true})).toHaveCount(0);
  const field=page.locator('.library-tag-field');
  await expect(field.getByText('Jazz',{exact:true})).toBeVisible();
  await expect(field.getByRole('button',{name:'Clear tag filter'})).toHaveText('×');
  await field.getByRole('button',{name:'Clear tag filter'}).click();
  await expect(page.getByRole('link',{name:'Yesterday',exact:true})).toBeVisible();
});
