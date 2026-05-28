import type { Metadata } from 'next';
import { Inter } from 'next/font/google';
import './globals.css';

const inter = Inter({ subsets: ['latin'] });

export const metadata: Metadata = {
  metadataBase: new URL('https://supplywatch.tomoliveri.com'),
  title: {
    default: 'SupplyWatch — Port Disruption Intelligence',
    template: '%s | SupplyWatch',
  },
  description:
    'Daily analysis of 68 major global ports using Sentinel-2 satellite imagery and Gemini Flash. Detects disruptions before they show up in shipment tracking.',
  openGraph: {
    title: 'SupplyWatch — Port Disruption Intelligence',
    description:
      'Daily analysis of 68 major global ports using Sentinel-2 satellite imagery and Gemini Flash. Detects disruptions before they show up in shipment tracking.',
    url: 'https://supplywatch.tomoliveri.com',
    siteName: 'SupplyWatch',
    locale: 'en_US',
    type: 'website',
  },
  twitter: {
    card: 'summary',
    title: 'SupplyWatch — Port Disruption Intelligence',
    description:
      'Daily satellite imagery analysis of 68 global ports. Detects disruptions before they show up in shipment tracking.',
  },
  robots: {
    index: true,
    follow: true,
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className={inter.className}>
      <body className="bg-slate-950">{children}</body>
    </html>
  );
}
