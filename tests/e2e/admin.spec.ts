import { test, expect, type Page, type APIRequestContext } from '@playwright/test';
import { readFileSync } from 'node:fs';
import { randomUUID } from 'node:crypto';

const bytes = readFileSync('tests/fixtures/image.png');
async function seed(request: APIRequestContext) {
  const message = `Admin browser test ${randomUUID()} <script>window.xssExecuted=true</script>`;
  const response = await request.post('/api/brief', {headers: {'Idempotency-Key': randomUUID().replaceAll('-','')}, multipart: {
    message, contactMethod:'email', contact:'synthetic-admin-test@example.org', name:'<b>Synthetic client</b>', language:'en',
    consent:'true', consentVersion:'brief-en-v1', noProduct:'true',
    files:{name:'Тест.png',mimeType:'image/png',buffer:bytes},
  }});
  expect(response.status()).toBe(200); return {...await response.json(),message};
}
async function login(page: Page) {
  await page.goto('/admin/login');
  await page.getByLabel('Username').fill('synthetic_admin_one');
  await page.getByLabel('Password', {exact:true}).fill(process.env.E2E_ADMIN_PASSWORD!);
  await page.getByRole('button',{name:'Sign in',exact:true}).click();
  await expect(page.getByRole('heading',{name:'Requests',exact:true})).toBeVisible();
}

test('admin real login, URL filters, note conflict, download, confirmed file/request deletion and logout', async ({page,request}) => {
  const record=await seed(request);
  await login(page);
  await page.getByLabel('Search',{exact:true}).fill(record.id);
  await page.getByRole('button',{name:'Search',exact:true}).click();
  await expect(page).toHaveURL(new RegExp('q='+record.id));
  await expect(page.locator('tbody tr')).toHaveCount(1);
  await page.reload();
  await expect(page.getByLabel('Search',{exact:true})).toHaveValue(record.id);
  await page.getByRole('link',{name:'<b>Synthetic client</b>'}).click();
  await expect(page.getByRole('heading',{name:'<b>Synthetic client</b>'})).toBeVisible();
  await expect(page.getByText(record.message,{exact:true})).toBeVisible();
  expect(await page.evaluate(()=>Object.hasOwn(window,'xssExecuted'))).toBe(false);
  await page.getByLabel('Internal note',{exact:true}).fill('First internal note');
  await page.getByRole('button',{name:'Save note'}).click();
  await expect(page.getByRole('status')).toHaveText('Saved');
  const session=await (await page.context().request.get('/api/admin/session')).json();
  const updated=await page.context().request.patch(`/api/admin/leads/${record.id}/notes`,{headers:{Origin:process.env.E2E_BASE_URL!,'X-CSRF-Token':session.csrf_token},data:{notes:'Saved by another editor',notes_version:1}});
  expect(updated.status()).toBe(200);
  await page.getByLabel('Internal note',{exact:true}).fill('Stale local note');
  await page.getByRole('button',{name:'Save note'}).click();
  await expect(page.locator('p.error')).toContainText('Another administrator');
  await page.getByRole('button',{name:'Reload latest note'}).click();
  await expect(page.getByLabel('Internal note',{exact:true})).toHaveValue('Saved by another editor');
  const pending=page.waitForEvent('download');
  await page.getByRole('link',{name:'Download',exact:true}).click();
  const download=await pending;
  expect(download.suggestedFilename()).toBe('Тест.png');
  expect(readFileSync((await download.path())!)).toEqual(bytes);
  await page.getByRole('button',{name:'Delete file',exact:true}).click();
  await expect(page.getByRole('dialog')).toContainText('Тест.png');
  await page.keyboard.press('Escape');
  await expect(page.getByRole('dialog')).toHaveCount(0);
  await page.getByRole('button',{name:'Delete file',exact:true}).click();
  await page.getByRole('button',{name:'Confirm permanent deletion'}).click();
  await expect(page.getByText('No attachments.',{exact:true})).toBeVisible();
  await page.getByRole('button',{name:'Delete request',exact:true}).click();
  await expect(page.getByRole('button',{name:'Confirm permanent deletion'})).toBeDisabled();
  await page.getByRole('dialog').getByRole('textbox').fill(record.id);
  await page.getByRole('button',{name:'Confirm permanent deletion'}).click();
  await expect(page.getByRole('heading',{name:'Requests',exact:true})).toBeVisible();
  expect((await page.context().request.get('/api/admin/leads/'+record.id)).status()).toBe(404);
  await page.getByRole('button',{name:'Sign out'}).click();
  await expect(page.getByRole('heading',{name:'Sign in to the lab'})).toBeVisible();
  expect((await page.context().request.get('/api/admin/leads')).status()).toBe(401);
});

test('admin anonymous refresh, safe redirects, empty/error states and mobile keyboard',async({page})=>{
  await page.goto('/admin/leads/'+randomUUID());
  await expect(page.getByRole('heading',{name:'Sign in to the lab'})).toBeVisible();
  await page.goto('/admin/login?next=https://evil.example');
  await page.getByLabel('Username').fill('synthetic_admin_one');
  await page.getByLabel('Password',{exact:true}).fill('incorrect');
  await page.getByRole('button',{name:'Sign in',exact:true}).click();
  await expect(page.locator('form [role="alert"]')).toHaveText('Incorrect username or password.');
  await page.getByLabel('Password',{exact:true}).fill(process.env.E2E_ADMIN_PASSWORD!);
  await page.keyboard.press('Enter');
  await expect(page).toHaveURL(/\/admin\/?$/);
  await page.setViewportSize({width:390,height:844});
  await page.getByLabel('Search',{exact:true}).fill('no-such-request-'+randomUUID());
  await page.getByRole('button',{name:'Search',exact:true}).click();
  await expect(page.getByText('No requests match these filters.')).toBeVisible();
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);
  const response=await page.request.get('/admin/login');
  expect(response.headers()['cache-control']).toContain('no-store');
  expect(response.headers()['x-frame-options']).toBe('DENY');
});
