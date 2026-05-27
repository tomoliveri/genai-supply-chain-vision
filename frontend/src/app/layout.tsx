import type { Metadata } from 'next';
import { Inter } from 'next/font/google';
import './globals.css';

const inter = Inter({ subsets: ['latin'] });

export const metadata: Metadata = {
  title: 'SupplyWatch — Geospatial Supply Chain Intelligence',
  description: 'Real-time geospatial AI monitoring for supply chain disruption detection.',
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className={`${inter.className} h-full bg-slate-950`}>
      <body className="h-full bg-slate-950">{children}</body>
    </html>
  );
}
