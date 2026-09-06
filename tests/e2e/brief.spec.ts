import { expect, test, type Page } from '@playwright/test';
import { execFileSync } from 'node:child_process';
import { createHash, randomUUID } from 'node:crypto';
import { readFileSync } from 'node:fs';

const fixture = (name: string) => readFileSync(`tests/fixtures/${name}`);
type Upload = { name: string; mimeType: string; buffer: Buffer };

async function openForm(page: Page) {
  await page.goto('/', { waitUntil: 'domcontentloaded' });
  await expect(page.locator('.hero h1')).toContainText('There is no universal solution');
  await page.locator('.nav-cta').click();
  await expect(page.getByRole('dialog')).toBeVisible();
}

async function toReply(page: Page, message: string, files: Upload[] = [], productLink = 'https://example.org/product?q=1') {
  await page.getByLabel('Your message', { exact: true }).fill(message);
  await page.getByRole('button', { name: 'Continue' }).click();
  if (productLink) await page.getByLabel('Product or company link · optional').fill(productLink);
  await page.getByLabel('There is no product yet.').check();
  if (files.length) await page.locator('#files').setInputFiles(files);
  await page.getByRole('button', { name: 'Continue' }).click();
  // Reproduces the old bug: DOM FormData at step 3 cannot contain step 1/2 fields.
  expect(await page.locator('form').evaluate(form => new FormData(form as HTMLFormElement).has('message'))).toBe(false);
}

async function contact(page: Page, method: 'email' | 'telegram') {
  await page.getByRole('button', { name: method === 'email' ? 'Email' : 'Telegram', exact: true }).click();
  await page.getByLabel('Name · optional').fill('Synthetic E2E client');
  await page.getByLabel(method === 'email' ? 'Email address' : 'Telegram username').fill(method === 'email' ? 'E2E.Name+lab@Example.org' : '@Example_User');
  await page.getByRole('checkbox', { name: 'I agree that Refraction LAB' }).check();
}

async function submit(page: Page) {
  const response = page.waitForResponse(r => r.url().endsWith('/api/brief') && r.request().method() === 'POST');
  await page.getByRole('button', { name: 'Send to the lab' }).click();
  const result = await response;
  expect(result.status()).toBe(200);
  await expect(page.getByRole('heading', { name: 'Your message is with the lab.' })).toBeVisible();
  const payload = await page.evaluate(async () => {
    const observed = (window as unknown as { briefResponse?: Promise<{ id: string }> }).briefResponse;
    return observed ? await observed : null;
  }) ?? await result.json();
  return payload.id as string;
}

function verify(id: string, message: string, method: 'email' | 'telegram', files: Upload[] = [], productLink: string | null = 'https://example.org/product?q=1') {
  const input = JSON.stringify({
    fields: { message, product_link: productLink, no_product: true, name: 'Synthetic E2E client',
      contact_method: method, contact_normalized: method === 'email' ? 'e2e.name+lab@example.org' : 'example_user',
      language: 'en', consent: true, consent_version: 'brief-en-v1' },
    files: files.map(file => ({ filename: file.name, size: file.buffer.length, sha256: createHash('sha256').update(file.buffer).digest('hex') })),
    unique_message: true,
  });
  if (process.env.E2E_COMPOSE === 'true') {
    // Pipe only synthetic assertions into the container; never expose a DB port.
    execFileSync('docker', ['compose', '--project-directory', '.', '--env-file', '.env', '-f', 'infra/compose/compose.yaml', 'exec', '-T', 'api', 'python', '-c', readFileSync('scripts/verify/assert-brief.py', 'utf8'), id], { input, stdio: ['pipe', 'pipe', 'pipe'] });
  } else {
    execFileSync(process.env.PYTHON_BIN || 'python', ['scripts/verify/assert-brief.py', id], { input, stdio: ['pipe', 'pipe', 'pipe'] });
  }
}

for (const method of ['telegram', 'email'] as const) {
  test(`all three steps reach PostgreSQL: ${method}`, async ({ page }) => {
    const message = `A complete ${method} request ${randomUUID()}`;
    const files: Upload[] = method === 'email' ? [{ name: 'image.png', mimeType: 'image/png', buffer: fixture('image.png') }] : [];
    await openForm(page);
    const productLink = method === 'email' ? '' : 'https://example.org/product?q=1';
    await toReply(page, message, files, productLink);
    await contact(page, method);
    const id = await submit(page);
    verify(id, message, method, files, productLink || null);
    await page.getByRole('button', { name: 'Return to the website' }).click();
    await expect(page.getByRole('dialog')).toBeHidden();
    await page.locator('.nav-cta').click();
    await expect(page.getByRole('heading', { name: 'Your message is with the lab.' })).toBeVisible();
    await page.reload({ waitUntil: 'domcontentloaded' });
    await page.locator('.nav-cta').click();
    await expect(page.getByRole('heading', { name: 'Your message is with the lab.' })).toBeVisible();
  });
}

test('validation guidance is English and the material link is optional', async ({ page }) => {
  await openForm(page);
  await page.getByRole('button', { name: 'Continue' }).click();
  await expect(page.locator('#message-error')).toHaveText('Please enter a message.');
  await page.getByLabel('Your message', { exact: true }).fill('Too short');
  await page.getByRole('button', { name: 'Continue' }).click();
  await expect(page.locator('#message-error')).toHaveText('Please enter at least 12 characters.');
  await page.getByLabel('Your message', { exact: true }).fill('A sufficiently detailed request.');
  await page.getByRole('button', { name: 'Continue' }).click();
  await page.getByLabel('Product or company link · optional').fill('not a link');
  await page.getByRole('button', { name: 'Continue' }).click();
  await expect(page.locator('#product-link-error')).toHaveText('Please enter a valid link starting with http:// or https://.');
  await page.getByLabel('Product or company link · optional').fill('');
  await page.getByRole('button', { name: 'Continue' }).click();
  await page.getByRole('button', { name: 'Email', exact: true }).click();
  await page.getByRole('button', { name: 'Send to the lab' }).click();
  await expect(page.getByText('Please enter your email address.')).toBeVisible();
  await expect(page.getByText('Please confirm that we may use the submitted information to reply.')).toBeVisible();
});

test('return from the received screen closes immediately', async ({ page }) => {
  await page.route('**/api/brief/session', route => route.fulfill({
    status: 200,
    contentType: 'application/json',
    body: JSON.stringify({ submitted: true }),
  }));
  await openForm(page);
  await expect(page.getByRole('heading', { name: 'Your message is with the lab.' })).toBeVisible();
  const started = Date.now();
  await page.getByRole('button', { name: 'Return to the website' }).click();
  await expect(page.getByRole('dialog')).toBeHidden();
  expect(Date.now() - started).toBeLessThan(1000);
  await expect(page.locator('.nav-cta')).toBeEnabled();
});

test('previews stay local, removal revokes URLs, retry retains attachments', async ({ page }) => {
  const files: Upload[] = [
    { name: 'image.png', mimeType: 'image/png', buffer: fixture('image.png') },
    { name: 'document.pdf', mimeType: 'application/pdf', buffer: fixture('document.pdf') },
    { name: 'document.docx', mimeType: 'application/octet-stream', buffer: fixture('document.docx') },
    { name: 'sheet.xlsx', mimeType: 'application/octet-stream', buffer: fixture('sheet.xlsx') },
  ];
  let posts = 0;
  page.on('request', request => { if (request.url().endsWith('/api/brief') && request.method() === 'POST') posts++; });
  await page.addInitScript(() => {
    const create = URL.createObjectURL.bind(URL), revoke = URL.revokeObjectURL.bind(URL);
    const tracking = { created: [] as string[], revoked: [] as string[] };
    Object.assign(window, { urlTracking: tracking });
    URL.createObjectURL = blob => { const url = create(blob); tracking.created.push(url); return url; };
    URL.revokeObjectURL = url => { tracking.revoked.push(url); revoke(url); };
  });
  await openForm(page);
  const message = `Preview and retry ${randomUUID()}`;
  await page.getByLabel('Your message', { exact: true }).fill(message);
  await page.getByRole('button', { name: 'Continue' }).click();
  await page.getByLabel('Product or company link · optional').fill('https://example.org/product?q=1');
  await page.getByLabel('There is no product yet.').check();
  await page.locator('#files').setInputFiles(files);
  await expect(page.getByAltText('Preview of image.png')).toBeVisible();
  expect(await page.getByAltText('Preview of image.png').evaluate(img => (img as HTMLImageElement).naturalWidth)).toBeGreaterThan(0);
  const popupPromise = page.waitForEvent('popup');
  await page.getByRole('link', { name: 'Open PDF' }).click();
  const popup = await popupPromise;
  await expect.poll(() => popup.url()).toMatch(/^blob:/);
  await popup.close();
  const downloadPromise = page.waitForEvent('download');
  await page.locator('li').filter({ has: page.getByText('document.docx', { exact: true }) }).getByRole('link', { name: 'Download' }).click();
  expect((await downloadPromise).suggestedFilename()).toBe('document.docx');
  await page.getByRole('button', { name: 'Remove sheet.xlsx' }).click();
  expect(posts).toBe(0);
  await page.getByRole('button', { name: 'Continue' }).click();
  await contact(page, 'email');
  let first = true;
  const keys: string[] = [];
  await page.route('**/api/brief', async route => {
    keys.push(route.request().headers()['idempotency-key']);
    if (first) {
      first = false;
      await route.fetch(); // Save for real, then simulate losing the response.
      await route.abort('failed');
    } else { await route.continue(); }
  });
  await page.getByRole('button', { name: 'Send to the lab' }).click();
  await expect(page.getByRole('alert')).toBeVisible();
  const id = await submit(page);
  expect(keys).toHaveLength(2);
  expect(keys[0]).toBe(keys[1]);
  verify(id, message, 'email', files.slice(0, 3));
  const tracking = await page.evaluate(() => (window as unknown as { urlTracking: { created: string[]; revoked: string[] } }).urlTracking);
  expect(new Set(tracking.revoked)).toEqual(new Set(tracking.created));
});

test('blocked browser storage and cookies still allow independent submissions', async ({ page }) => {
  await page.addInitScript(() => Object.defineProperty(window, 'sessionStorage', { get() { throw new DOMException('Blocked', 'SecurityError'); } }));
  await page.route('**/api/brief/session', async route => {
    // Node fetch has no browser cookie jar; route.fetch would store Set-Cookie itself.
    const response = await fetch(route.request().url());
    const headers = Object.fromEntries(response.headers.entries());
    delete headers['set-cookie'];
    await route.fulfill({ status: response.status, body: await response.text(), headers });
  });
  for (let index = 0; index < 2; index++) {
    await openForm(page);
    const message = `Cookie-free request ${randomUUID()}`;
    await toReply(page, message);
    await contact(page, 'email');
    const id = await submit(page);
    verify(id, message, 'email');
  }
  expect((await page.context().cookies()).filter(c => c.name === 'lab_browser')).toHaveLength(0);
});

test('the full 30 MiB limit passes multipart and proxy', async ({ page }) => {
  test.setTimeout(180000);
  await page.addInitScript(() => {
    const nativeFetch = window.fetch.bind(window);
    window.fetch = async (...args) => {
      const response = await nativeFetch(...args);
      if (String(args[0]).endsWith('/api/brief')) {
        // Observe a clone in the page: Chromium may evict large uploads from its inspector cache.
        Object.assign(window, { briefResponse: response.clone().json() });
      }
      return response;
    };
  });
  const message = `Boundary request ${randomUUID()}`;
  const files = Array.from({ length: 3 }, (_, index) => {
    const buffer = Buffer.alloc(10 * 1024 * 1024);
    fixture('image.png').copy(buffer);
    return { name: `limit-${index}.png`, mimeType: 'image/png', buffer };
  });
  await openForm(page);
  await toReply(page, message, files);
  await contact(page, 'email');
  const id = await submit(page);
  verify(id, message, 'email', files);
});

test('mobile layout and private routes', async ({ page, request }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await openForm(page);
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await expect(page.locator('.brand img').first()).toHaveAttribute('src', /logo.svg/);
  for (const path of ['/api/leads', '/api/admin', '/api/files/123', '/uploads/123', '/objects/123']) {
    expect((await request.get(path)).status()).toBe(404);
  }
});
