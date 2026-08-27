import { env } from 'cloudflare:workers';
import {
  createLeadFilesIndex,
  createLeadFilesTable,
  createLeadsTable,
  createLeadStatusIndex,
} from '../../../db/schema';

const MAX_FILES = 6;
const MAX_FILE_SIZE = 10 * 1024 * 1024;
const MAX_TOTAL_SIZE = 30 * 1024 * 1024;
const blockedExtensions = /\.(exe|msi|bat|cmd|com|scr|ps1|jar)$/i;

function text(form: FormData, name: string, limit: number) {
  const value = form.get(name);
  return typeof value === 'string' ? value.trim().slice(0, limit) : '';
}

function safeFilename(filename: string) {
  return filename.replace(/[^a-zA-Z0-9._-]+/g, '-').replace(/^-+|-+$/g, '').slice(0, 120) || 'file';
}

async function ensureSchema() {
  await env.DB.batch([
    env.DB.prepare(createLeadsTable),
    env.DB.prepare(createLeadFilesTable),
    env.DB.prepare(createLeadStatusIndex),
    env.DB.prepare(createLeadFilesIndex),
  ]);
}

async function notifyTelegram(summary: string) {
  if (!env.TELEGRAM_BOT_TOKEN || !env.TELEGRAM_CHAT_ID) return;
  await fetch(`https://api.telegram.org/bot${env.TELEGRAM_BOT_TOKEN}/sendMessage`, {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify({ chat_id: env.TELEGRAM_CHAT_ID, text: summary, disable_web_page_preview: true }),
  });
}

export async function POST(request: Request) {
  try {
    const form = await request.formData();
    if (text(form, 'companyWebsite', 200)) return Response.json({ ok: true });

    const message = text(form, 'message', 5000);
    const contactMethod = text(form, 'contactMethod', 20);
    const contact = text(form, 'contact', 180);
    const name = text(form, 'name', 120);
    const productLink = text(form, 'productLink', 1000);
    const consent = text(form, 'consent', 10) === 'true';

    if (message.length < 12) return Response.json({ error: 'Tell us a little more about the situation.' }, { status: 400 });
    if (!['telegram', 'email'].includes(contactMethod) || !contact) return Response.json({ error: 'Add a Telegram username or email address.' }, { status: 400 });
    if (!consent) return Response.json({ error: 'Consent is required so we can review and reply.' }, { status: 400 });

    const files = form.getAll('files').filter((value): value is File => value instanceof File && value.size > 0);
    if (files.length > MAX_FILES) return Response.json({ error: `Attach no more than ${MAX_FILES} files.` }, { status: 400 });
    const totalSize = files.reduce((sum, file) => sum + file.size, 0);
    if (totalSize > MAX_TOTAL_SIZE) return Response.json({ error: 'Attachments must be 30 MB or less in total.' }, { status: 400 });
    for (const file of files) {
      if (file.size > MAX_FILE_SIZE) return Response.json({ error: `${file.name} is larger than 10 MB.` }, { status: 400 });
      if (blockedExtensions.test(file.name)) return Response.json({ error: `${file.name} is not an accepted file type.` }, { status: 400 });
    }

    await ensureSchema();
    const leadId = crypto.randomUUID();
    const createdAt = new Date().toISOString();

    await env.DB.prepare(`
      INSERT INTO leads (id, created_at, name, contact_method, contact, message, product_link, no_product, status)
      VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'new')
    `).bind(leadId, createdAt, name || null, contactMethod, contact, message, productLink || null, form.get('noProduct') === 'true' ? 1 : 0).run();

    const fileStatements: D1PreparedStatement[] = [];
    for (const file of files) {
      const fileId = crypto.randomUUID();
      const filename = safeFilename(file.name);
      const objectKey = `leads/${leadId}/${fileId}-${filename}`;
      await env.FILES.put(objectKey, file.stream(), {
        httpMetadata: { contentType: file.type || 'application/octet-stream' },
        customMetadata: { leadId, originalFilename: file.name },
      });
      fileStatements.push(env.DB.prepare(`
        INSERT INTO lead_files (id, lead_id, object_key, filename, content_type, size_bytes)
        VALUES (?, ?, ?, ?, ?, ?)
      `).bind(fileId, leadId, objectKey, file.name.slice(0, 240), file.type || null, file.size));
    }
    if (fileStatements.length) await env.DB.batch(fileStatements);

    const notification = [
      'New Refraction LAB brief',
      `${contactMethod}: ${contact}`,
      name ? `Name: ${name}` : '',
      productLink ? `Link: ${productLink}` : '',
      `Files: ${files.length}`,
      '',
      message.slice(0, 2500),
    ].filter(Boolean).join('\n');
    await notifyTelegram(notification).catch(() => undefined);

    return Response.json({ ok: true, id: leadId });
  } catch (error) {
    console.error('Brief submission failed', error);
    return Response.json({ error: 'The message could not be sent. Please try again.' }, { status: 500 });
  }
}
