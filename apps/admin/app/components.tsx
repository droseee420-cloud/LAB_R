'use client';
import Link from 'next/link';
import { usePathname, useRouter } from 'next/navigation';
import { createContext, useContext, useEffect, useState } from 'react';

export const base = process.env.NEXT_PUBLIC_ADMIN_BASE_PATH ?? '/admin';
export class ApiError extends Error { constructor(public status: number, message: string) { super(message); } }
export async function api(path: string, options: RequestInit = {}) {
  const response = await fetch(`/api/admin${path}`, { ...options, cache: 'no-store', credentials: 'same-origin', headers: { 'Content-Type': 'application/json', ...options.headers } });
  if (!response.ok) {
    const data = await response.json().catch(() => null);
    throw new ApiError(response.status, data?.error || 'Service unavailable. Please try again.');
  }
  return response.status === 204 ? null : response.json();
}
const Session = createContext('');
export const useCsrf = () => useContext(Session);
export function Moment({ value }: { value: string }) {
  return <time dateTime={value} title={new Date(value).toISOString()}>{new Date(value).toLocaleString()}</time>;
}
export function Shell({ children }: { children: React.ReactNode }) {
  const [session, setSession] = useState<{ user: { username: string }; csrf_token: string } | null>(null);
  const [error, setError] = useState(''); const [busy, setBusy] = useState(false);
  const router = useRouter(); const pathname = usePathname();
  useEffect(() => {
    let active = true;
    api('/session').then(value => { if (active) setSession(value); }).catch(error => {
      if (!active) return;
      if (error.status === 401) router.replace(`/login?next=${encodeURIComponent(base + pathname)}`);
      else setError(error.message);
    });
    return () => { active = false; };
  }, [pathname, router]);
  async function logout() {
    setBusy(true);
    try { await api('/logout', { method: 'POST', headers: { 'X-CSRF-Token': session!.csrf_token } }); router.replace('/login'); }
    catch (error) { setError((error as Error).message); setBusy(false); }
  }
  return <><header><Link href="/" className="brand">REFRACTION <span>LAB / REQUESTS</span></Link>{session && <div>{session.user.username} <button onClick={logout} disabled={busy}>Sign out</button></div>}</header>
    <main>{error && <p role="alert">{error} <button onClick={() => location.reload()}>Reload</button></p>}
      {!session ? <p role="status">Checking your session…</p> : <Session.Provider value={session.csrf_token}>{children}</Session.Provider>}
    </main></>;
}
export function Failure({ message }: { message: string }) {
  return message ? <p role="alert" className="error">{message} <Link href="/login">Sign in</Link></p> : null;
}
