import type { Metadata } from 'next';
import localFont from 'next/font/local';
import './globals.css';

const geistSans = localFont({
  src: [{ path: '../public/fonts/Geist-Regular.woff2', weight: '400', style: 'normal' }],
  variable: '--font-geist-sans',
  display: 'swap'
});

const geistMono = localFont({
  src: [{ path: '../public/fonts/GeistMono-Regular.woff2', weight: '400', style: 'normal' }],
  variable: '--font-geist-mono',
  display: 'swap'
});

export const metadata: Metadata = {
  title: 'Job Radar',
  description: 'Search dev jobs from curated lists and ATS feeds.',
  icons: {
    icon: '/favicon.png',
    shortcut: '/favicon.png',
    apple: '/favicon.png'
  },
  openGraph: {
    title: 'Job Radar',
    description: 'Search dev jobs from curated lists and ATS feeds.',
    url: 'https://jobradar.zacknelson.dev',
    siteName: 'Job Radar',
    images: [
      {
        url: '/og-preview.jpg',
        width: 1200,
        height: 630,
        alt: 'Job Radar dashboard preview'
      }
    ]
  },
  twitter: {
    card: 'summary_large_image',
    title: 'Job Radar',
    description: 'Search dev jobs from curated lists and ATS feeds.',
    images: ['/og-preview.jpg']
  }
};

export default function RootLayout({
  children
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang='en' suppressHydrationWarning>
      <body
        className={`${geistSans.variable} ${geistMono.variable} antialiased bg-surface text-text min-h-screen`}
      >
        {children}
      </body>
    </html>
  );
}
