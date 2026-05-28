import type { Metadata } from 'next';
import { DashboardContent } from '@/components/DashboardContent';

export const metadata: Metadata = {
  title: 'Live Dashboard',
  description:
    'Live port disruption dashboard monitoring 68 major global ports. Satellite imagery analysis updated daily.',
  alternates: { canonical: '/demo' },
};

interface DemoPageProps {
  searchParams: Promise<{ port?: string }>;
}

/**
 * Server component: reads the `port` query param and passes it to the
 * client-side dashboard.  This avoids the `useSearchParams()` Suspense
 * boundary requirement.
 */
export default async function DemoPage({ searchParams }: DemoPageProps) {
  const params = await searchParams;
  return <DashboardContent portSlug={params.port ?? null} />;
}
