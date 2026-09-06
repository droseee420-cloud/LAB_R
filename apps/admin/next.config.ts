import type { NextConfig } from 'next';
import path from 'node:path';

const basePath = process.env.ADMIN_BASE_PATH ?? '/admin';
const config: NextConfig = {
  basePath, output: 'standalone', poweredByHeader: false,
  outputFileTracingRoot: path.resolve(process.cwd(), '../..'),
  env: { NEXT_PUBLIC_ADMIN_BASE_PATH: basePath },
  async headers() {
    return [{ source: '/:path*', headers: [
      { key: 'Cache-Control', value: 'no-store, private' },
      { key: 'X-Content-Type-Options', value: 'nosniff' },
      { key: 'X-Frame-Options', value: 'DENY' },
      { key: 'Referrer-Policy', value: 'no-referrer' },
    ] }];
  },
};
export default config;
