import type { MetadataRoute } from 'next';

export default function sitemap(): MetadataRoute.Sitemap {
  const base = 'https://supplywatch.tomoliveri.com';
  const now = new Date();
  return [
    { url: base, lastModified: now, changeFrequency: 'daily', priority: 1 },
    { url: `${base}/how-it-works`, lastModified: now, changeFrequency: 'weekly', priority: 0.8 },
    { url: `${base}/demo`, lastModified: now, changeFrequency: 'daily', priority: 0.7 },
  ];
}
