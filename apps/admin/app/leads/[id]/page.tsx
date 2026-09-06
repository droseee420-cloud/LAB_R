'use client';
import Link from 'next/link';
import { useParams, useRouter } from 'next/navigation';
import { useCallback, useEffect, useRef, useState } from 'react';
import { api, Failure, Moment, Shell, useCsrf } from '../../components';
import type { Lead } from '../../page';

type Attachment = {id: string; filename: string; content_type: string; size_bytes: number; sha256: string; created_at: string};
type Detail = Lead & {message: string; product_link: string | null; no_product: boolean; contact_normalized: string; consent: boolean; consent_at: string; consent_version: string; notes: string | null; notes_version: number; files: Attachment[]; related: Lead[]};
function RequestDetail() {
  const {id} = useParams<{id: string}>(), router = useRouter(), csrf = useCsrf();
  const [lead, setLead] = useState<Detail | null>(null), [error, setError] = useState('');
  const [note, setNote] = useState(''), [noteState, setNoteState] = useState(''), [busy, setBusy] = useState(false);
  const [deleting, setDeleting] = useState<Attachment | 'lead' | null>(null), [confirmation, setConfirmation] = useState('');
  const deleteTrigger = useRef<HTMLButtonElement | null>(null);
  function askDelete(value: Attachment | 'lead', trigger: HTMLButtonElement) { deleteTrigger.current = trigger; setDeleting(value); setConfirmation(''); }
  function cancelDelete() { setDeleting(null); setTimeout(() => deleteTrigger.current?.focus()); }
  const load = useCallback(async () => { const value = await api('/leads/' + id); setLead(value); setNote(value.notes || ''); setNoteState(''); setError(''); }, [id]);
  useEffect(() => { let active = true; api('/leads/' + id).then(value => { if (active) { setLead(value); setNote(value.notes || ''); } }).catch(error => { if (active) setError(error.message); }); return () => { active = false; }; }, [id]);
  async function save() {
    if (!lead || busy) return; setBusy(true); setNoteState('Saving…'); setError('');
    try { const value = await api(`/leads/${id}/notes`, {method: 'PATCH', headers: {'X-CSRF-Token': csrf}, body: JSON.stringify({notes: note, notes_version: lead.notes_version})}); setLead({...lead, ...value}); setNoteState('Saved'); }
    catch (error) { setNoteState('Not saved'); setError((error as Error).message); } finally { setBusy(false); }
  }
  async function remove() {
    if (!deleting || busy) return; setBusy(true); setError('');
    try { await api(deleting === 'lead' ? `/leads/${id}` : `/files/${deleting.id}`, {method: 'DELETE', headers: {'X-CSRF-Token': csrf}}); if (deleting === 'lead') router.push('/'); else { setDeleting(null); await load(); } }
    catch (error) { setError((error as Error).message); } finally { setBusy(false); }
  }
  return <><Link href="/">← All requests</Link><Failure message={error} />{!lead ? <p role="status">Loading request…</p> : <>
    <div className="heading"><div><p className="eyebrow">REQUEST</p><h1>{lead.name || 'Name not provided'}</h1><p className="mono">{lead.id}</p></div><Moment value={lead.created_at} /></div>
    <div className="detail-grid"><section><h2>Submitted information</h2><dl><dt>Contact</dt><dd>{lead.contact_method} · {lead.contact}</dd><dt>Normalized contact</dt><dd>{lead.contact_normalized}</dd><dt>Language</dt><dd>{lead.language}</dd><dt>Product link</dt><dd>{lead.product_link || 'Not provided'}</dd><dt>No product yet</dt><dd>{lead.no_product ? 'Yes' : 'No'}</dd></dl><h3>Message</h3><p className="message">{lead.message}</p><h3>Consent</h3><p>{lead.consent ? 'Accepted' : 'Not accepted'} · {lead.consent_version}</p><Moment value={lead.consent_at} /></section>
    <section><h2>Internal note</h2><label className="sr-only" htmlFor="note">Internal note</label><textarea id="note" value={note} maxLength={10000} rows={10} disabled={busy} onChange={event => {setNote(event.target.value); setNoteState('Changed');}} /><div className="actions"><button className="primary" onClick={save} disabled={busy || note === (lead.notes || '')}>Save note</button><span role="status">{noteState}</span></div>{noteState === 'Not saved' && <button onClick={() => load().catch(error => setError(error.message))}>Reload latest note</button>}<small>{note.length} / 10,000 characters</small></section></div>
    <section><h2>Attachments · {lead.files.length}</h2>{!lead.files.length && <p>No attachments.</p>}<ul className="files">{lead.files.map(file => <li key={file.id}><div><strong>{file.filename}</strong><small>{file.content_type} · {file.size_bytes.toLocaleString()} bytes · <Moment value={file.created_at} /></small><details><summary>SHA256</summary><code>{file.sha256}</code></details></div><div className="actions"><a href={`/api/admin/files/${file.id}/download`}>Download</a><button disabled={busy} onClick={event => askDelete(file, event.currentTarget)}>Delete file</button></div></li>)}</ul></section>
    <section><h2>Other requests with this contact</h2>{!lead.related.length ? <p>No other requests with this normalized contact.</p> : <ul>{lead.related.map(other => <li key={other.id}><Link href={`/leads/${other.id}`}><Moment value={other.created_at} /> · {other.message_preview}</Link></li>)}</ul>}</section>
    <section className="danger"><h2>Delete this request</h2><p>Permanently removes this request and all {lead.files.length} attachments. There is no backup or undo.</p><button disabled={busy} onClick={event => askDelete('lead', event.currentTarget)}>Delete request</button></section>
    {deleting && <div className="modal"><div role="dialog" aria-modal="true" aria-labelledby="delete-title" onKeyDown={event => {
      if (event.key === 'Escape' && !busy) cancelDelete();
      if (event.key === 'Tab') {
        const elements = Array.from(event.currentTarget.querySelectorAll<HTMLElement>('button:not(:disabled), input:not(:disabled), a[href]'));
        const first = elements[0], last = elements[elements.length - 1];
        if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last?.focus(); }
        else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first?.focus(); }
      }
    }}><h2 id="delete-title">{deleting === 'lead' ? 'Delete request permanently?' : 'Delete attachment permanently?'}</h2>
      <p>{deleting === 'lead' ? `${lead.contact} · ${lead.files.length} attachments. This cannot be undone.` : deleting.filename}</p>{deleting === 'lead' && <label>Type request ID to confirm: <code>{id}</code><input autoFocus value={confirmation} onChange={event => setConfirmation(event.target.value)} /></label>}
      <div className="actions"><button autoFocus={deleting !== 'lead'} disabled={busy} onClick={cancelDelete}>Cancel</button><button className="destructive" disabled={busy || (deleting === 'lead' && confirmation !== id)} onClick={remove}>{busy ? 'Deleting…' : 'Confirm permanent deletion'}</button></div>{error && <p role="alert">{error}</p>}</div></div>}
  </>}</>;
}
export default function Page() { return <Shell><RequestDetail /></Shell>; }
