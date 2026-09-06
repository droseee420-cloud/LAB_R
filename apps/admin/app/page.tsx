'use client';
import Link from 'next/link';
import { FormEvent, Suspense, useEffect, useState } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { api, Failure, Moment, Shell } from './components';

export type Lead = { id: string; created_at: string; name: string | null; contact_method: string; contact: string; language: string; message_preview: string; file_count: number };
function Requests() {
  const params = useSearchParams(), router = useRouter(), query = params.toString();
  const [result, setResult] = useState<{items: Lead[]; total: number; page: number; page_size: number} | null>(null);
  const [error, setError] = useState(''), [loading, setLoading] = useState(true);
  useEffect(() => {
    const controller = new AbortController();
    api('/leads?' + query, { signal: controller.signal }).then(setResult).catch(error => { if (error.name !== 'AbortError') setError(error.message); }).finally(() => { if (!controller.signal.aborted) setLoading(false); });
    return () => controller.abort();
  }, [query]);
  function search(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); const next = new URLSearchParams();
    for (const [key, value] of new FormData(event.currentTarget)) if (String(value)) next.set(key, String(value));
    setLoading(true); setError(''); router.push('/?' + next);
  }
  function page(number: number) { const next = new URLSearchParams(query); next.set('page', String(number)); return '/?' + next; }
  return <><div className="heading"><div><p className="eyebrow">INBOX</p><h1>Requests</h1></div>{result && <p>{result.total} requests</p>}</div>
    <form className="filters" onSubmit={search} key={query}><label className="search">Search<input name="q" defaultValue={params.get('q') || ''} placeholder="ID, name, contact or message" maxLength={200} /></label>
      <label>Contact<select name="contact_method" defaultValue={params.get('contact_method') || ''}><option value="">All contacts</option><option value="email">Email</option><option value="telegram">Telegram</option></select></label>
      <label>Language<select name="language" defaultValue={params.get('language') || ''}><option value="">All languages</option>{['en','es','ca'].map(l => <option key={l}>{l}</option>)}</select></label>
      <label>Files<select name="has_files" defaultValue={params.get('has_files') || ''}><option value="">Any</option><option value="true">With files</option><option value="false">Without files</option></select></label>
      <label>From (UTC)<input name="date_from" type="date" defaultValue={params.get('date_from') || ''} /></label><label>To (UTC)<input name="date_to" type="date" defaultValue={params.get('date_to') || ''} /></label>
      <label>Order<select name="sort" defaultValue={params.get('sort') || 'desc'}><option value="desc">Newest first</option><option value="asc">Oldest first</option></select></label>
      <label>Per page<select name="page_size" defaultValue={params.get('page_size') || '25'}>{[25,50,100].map(n => <option key={n}>{n}</option>)}</select></label>
      <button className="primary">Search</button><Link href="/">Reset filters</Link></form>
    <Failure message={error} />{loading && <p role="status">Loading requests…</p>}
    {result && !error && <><div className="table-scroll"><table><thead><tr><th>Received</th><th>Name / contact</th><th>Language</th><th>Message</th><th>Files</th></tr></thead><tbody>{result.items.map(lead => <tr key={lead.id}>
      <td><Link href={`/leads/${lead.id}`}><Moment value={lead.created_at} /></Link></td><td><Link href={`/leads/${lead.id}`}>{lead.name || 'Name not provided'}</Link><small>{lead.contact_method} · {lead.contact}</small></td><td>{lead.language}</td><td className="preview">{lead.message_preview}</td><td>{lead.file_count}</td></tr>)}</tbody></table></div>
      {!result.items.length && <p className="empty">No requests match these filters.</p>}<nav aria-label="Pagination">{result.page > 1 && <Link href={page(result.page - 1)}>Previous page</Link>}<span>Page {result.page} · {result.total} results</span>{result.page * result.page_size < result.total && <Link href={page(result.page + 1)}>Next page</Link>}</nav></>}
  </>;
}
export default function Page() { return <Shell><Suspense fallback={<p>Loading…</p>}><Requests /></Suspense></Shell>; }
