import type { Metadata } from 'next';
import { Geist, Geist_Mono } from 'next/font/google';
import './globals.css';

const geistSans = Geist({
  variable: '--font-geist-sans',
  subsets: ['latin'],
});

const geistMono = Geist_Mono({
  variable: '--font-geist-mono',
  subsets: ['latin'],
});

export const metadata: Metadata = {
  metadataBase: new URL('https://refraction-lab.denisdevatkin6033.chatgpt.site'),
  title: 'Refraction LAB — Digital Product Laboratory',
  description: 'We examine digital product problems, model the right solution and take it through implementation.',
  openGraph: {
    title: 'Refraction LAB — Digital Product Laboratory',
    description: 'We examine digital product problems, model the right solution and take it through implementation.',
    url: '/',
    siteName: 'Refraction LAB',
    images: [
      {
        url: '/og.png',
        width: 1200,
        height: 630,
        alt: 'Refraction LAB — Digital Product Laboratory',
      },
    ],
    type: 'website',
  },
  twitter: {
    card: 'summary_large_image',
    title: 'Refraction LAB — Digital Product Laboratory',
    description: 'We examine digital product problems, model the right solution and take it through implementation.',
    images: ['/og.png'],
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body
        className={`${geistSans.variable} ${geistMono.variable} antialiased`}
      >
        {children}
      </body>
    </html>
  );
}
