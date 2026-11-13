import {test,expect} from '@playwright/test';

test('configures an OpenAI-compatible service in a keyboard-accessible dialog without exposing keys',async({page})=>{
 await page.goto('/settings');await page.getByLabel('Password').fill('synthetic test password');await page.getByRole('button',{name:'Sign in'}).click();
 await page.getByRole('button',{name:'Configure AI conversion'}).click();const dialog=page.getByRole('dialog',{name:'AI conversion settings'});await expect(dialog).toBeVisible();
 await dialog.getByRole('button',{name:'NVIDIA preset'}).click();await expect(dialog.getByLabel('Base URL')).toHaveValue('https://integrate.api.nvidia.com/v1');
 await dialog.getByLabel('Service name').fill('Synthetic NVIDIA');await dialog.getByLabel('Vision model').fill('synthetic-vision');await dialog.getByLabel('API key',{exact:true}).fill('synthetic-browser-secret');
 await dialog.getByRole('button',{name:'Save changes'}).click();await expect(dialog).toBeHidden();
 await page.getByRole('button',{name:'Configure AI conversion'}).click();await expect(dialog.getByLabel('API key',{exact:true})).toHaveValue('');await expect(dialog.getByText('A key is saved. Leave blank to keep it.')).toBeVisible();
 expect(await page.evaluate(()=>JSON.stringify(localStorage))).not.toContain('synthetic-browser-secret');
 const response=await page.request.get('/api/provider/settings');expect(await response.text()).not.toContain('synthetic-browser-secret');
 await page.keyboard.press('Escape');await expect(dialog).toBeHidden();await expect(page.getByRole('button',{name:'Configure AI conversion'})).toBeFocused();
 await page.getByRole('button',{name:'Configure AI conversion'}).click();
 await page.route('**/api/provider/test',async route=>{expect(route.request().postDataJSON().authorize_synthetic).toBe(true);expect(route.request().postData()).not.toContain('synthetic-browser-secret');await route.fulfill({status:502,contentType:'application/json',body:'{"detail":"AI service rejected the API credentials."}'});});
 await dialog.getByLabel('Authorize a synthetic image test').check();await dialog.getByRole('button',{name:'Test connection'}).click();await expect(dialog.getByRole('alert')).toContainText('AI service rejected the API credentials.');
 await dialog.evaluate(el=>el.scrollTop=0);await page.setViewportSize({width:390,height:844});expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);await page.screenshot({path:'.local/review/ai-settings-phone.png'});
 await page.setViewportSize({width:1280,height:900});await page.screenshot({path:'.local/review/ai-settings-desktop.png'});
});
