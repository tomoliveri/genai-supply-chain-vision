import type { Metadata } from 'next';
import { Inter } from 'next/font/google';
import './globals.css';

const inter = Inter({ subsets: ['latin'] });

export const metadata: Metadata = {
  title: 'SupplyWatch: Geospatial Supply Chain Intelligence',
  description:
    'Daily analysis of 70 major global ports using Sentinel-2 satellite imagery and Gemini Flash. Detects disruptions before they show up in shipment tracking. Built by Tom Oliveri.',
  openGraph: {
    title: 'SupplyWatch: Geospatial Supply Chain Intelligence',
    description:
      'Daily analysis of 70 major global ports using Sentinel-2 satellite imagery and Gemini Flash.',
    type: 'website',
  },
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
