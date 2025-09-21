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
  description: 'Search dev jobs from curated lists and ATS feeds.'
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
