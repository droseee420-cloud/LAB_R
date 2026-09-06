'use client';
import { FormEvent, Suspense, useState } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { api, base } from '../components';

function Login() {
  const [busy, setBusy] = useState(false), [error, setError] = useState('');
  const router = useRouter(), params = useSearchParams();
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); if (busy) return;
    setBusy(true); setError('');
    const fields = new FormData(event.currentTarget);
    try {
      await api('/login', { method: 'POST', body: JSON.stringify(Object.fromEntries(fields)) });
      const next = params.get('next') || base + '/';
      const url = new URL(next, location.origin);
      const safe = url.origin === location.origin && (url.pathname === base || url.pathname.startsWith(base + '/')) && !next.includes('\\');
      router.replace(safe ? url.pathname.slice(base.length) + url.search || '/' : '/');
    } catch (error) { setError((error as Error).message); setBusy(false); }
  }
  return <main className="login"><p className="eyebrow">REFRACTION LAB</p><h1>Sign in to the lab</h1><p>Private workspace for submitted requests.</p>
    <form onSubmit={submit}><fieldset disabled={busy}><label>Username<input name="username" autoComplete="username" required maxLength={80} autoFocus /></label>
      <label>Password<input name="password" type="password" autoComplete="current-password" required maxLength={1024} /></label>
      {error && <p role="alert">{error}</p>}<button className="primary" type="submit">{busy ? 'Signing in…' : 'Sign in'}</button></fieldset></form></main>;
}
export default function Page() { return <Suspense fallback={<p>Loading…</p>}><Login /></Suspense>; }
